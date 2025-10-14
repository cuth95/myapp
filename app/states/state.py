import reflex as rx
import PyPDF2
import os
import logging
import random
import string
import time
import base64
import json
import re
import httpx
from typing import Optional, Any
from app.states.ai_state import AIState


class State(rx.State):
    """The app state."""

    uploaded_file: Optional[str] = None
    uploading: bool = False
    upload_progress: int = 0
    document_text: str = ""
    active_tab: str = "reader"
    voices: list[dict] = [
        {"name": "Charon (Male)", "id": "en-US-Chirp3-HD-Charon"},
        {"name": "Zephyr (Female)", "id": "en-US-Chirp3-HD-Zephyr"},
        {"name": "Puck (Male)", "id": "en-US-Chirp3-HD-Puck"},
        {"name": "Vindemiatrix (Female)", "id": "en-US-Chirp3-HD-Vindemiatrix"},
    ]
    selected_voice: str = "en-US-Chirp3-HD-Charon"
    audio_url: Optional[str] = None
    is_generating_audio: bool = False
    is_generating_preview: bool = False
    preview_voice_id: str = ""
    preview_audio_url: Optional[str] = None
    is_playing: bool = False
    audio_progress: float = 0
    current_time_str: str = "00:00"
    duration: float = 0
    duration_str: str = "00:00"
    zoom_level: int = 100
    sentences: list[tuple[str, int]] = []
    timepoints: list[dict[str, str | float]] = []
    current_sentence_index: int = -1
    original_filename: str = ""
    show_summarizer: bool = False
    show_glossary: bool = False
    show_quiz: bool = False
    show_chat: bool = False

    @rx.event
    def zoom_in(self):
        self.zoom_level += 10

    @rx.event
    def zoom_out(self):
        self.zoom_level = max(50, self.zoom_level - 10)

    def _reset_audio_state(self):
        self.audio_url = None
        self.is_playing = False
        self.audio_progress = 0
        self.current_time_str = "00:00"
        self.duration = 0
        self.duration_str = "00:00"
        self.timepoints = []
        self.current_sentence_index = -1

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        if not files:
            yield rx.toast.error("No file selected.")
            return
        self.uploading = True
        self.upload_progress = 0
        yield
        file = files[0]
        upload_data = await file.read()
        for i in range(101):
            self.upload_progress = i
            if i % 10 == 0:
                yield
            time.sleep(0.01)
        upload_dir = rx.get_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)
        unique_name = (
            "".join(random.choices(string.ascii_letters + string.digits, k=10))
            + "_"
            + file.name
        )
        file_path = upload_dir / unique_name
        with file_path.open("wb") as f:
            f.write(upload_data)
        self.uploaded_file = unique_name
        self.original_filename = file.name
        self.document_text = self._extract_text_from_pdf(file_path)
        self._prepare_sentences()
        self._reset_audio_state()
        self.uploading = False
        ai_state = await self.get_state(AIState)
        ai_state.clear_ai_states()
        yield rx.toast.success(f"Uploaded {file.name}")

    def _extract_text_from_pdf(self, file_path: str) -> str:
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted
                return " ".join(text.split())
        except Exception as e:
            logging.exception(f"Error extracting text from PDF: {e}")
            return "Error extracting text from the document."

    def _prepare_sentences(self):
        """Splits the document text into sentences for highlighting."""
        sentence_ends = re.compile("(?<!\\w\\.\\w.)(?<![A-Z][a-z]\\.)(?<=\\.|\\?|!)\\s")
        raw_sentences = sentence_ends.split(self.document_text)
        self.sentences = [
            (sentence.strip(), i)
            for i, sentence in enumerate(raw_sentences)
            if sentence.strip()
        ]

    def _prepare_ssml(self) -> str:
        """Wraps sentences in SSML <mark> tags."""
        ssml_parts = ["<speak>"]
        for sentence, i in self.sentences:
            escaped_sentence = (
                sentence.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;")
            )
            ssml_parts.append(f'<mark name="s{i}"/>{escaped_sentence} ')
        ssml_parts.append("</speak>")
        return "".join(ssml_parts)

    @rx.event
    def set_active_tab(self, tab: str):
        self.active_tab = tab

    @rx.event
    def set_selected_voice(self, voice_id: str):
        self.selected_voice = voice_id
        self._reset_audio_state()

    async def _synthesize_speech_api(
        self, ssml: str, voice_id: str, with_timepoints: bool
    ) -> httpx.Response:
        api_key = os.getenv("GOOGLE_CLOUD_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_CLOUD_API_KEY secret not set.")
        url = (
            f"https://texttospeech.googleapis.com/v1beta1/text:synthesize?key={api_key}"
        )
        headers = {"Content-Type": "application/json"}
        data = {
            "input": {"ssml": ssml},
            "voice": {"languageCode": "en-US", "name": voice_id},
            "audioConfig": {"audioEncoding": "MP3"},
        }
        if with_timepoints:
            data["enableTimePointing"] = ["SSML_MARK"]
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        return response

    @rx.event(background=True)
    async def generate_audio(self):
        async with self:
            if not self.document_text:
                yield rx.toast.error("No document text to convert.")
                return
            self.is_generating_audio = True
            self.audio_url = None
        yield
        try:
            ssml_text = self._prepare_ssml()
            response = await self._synthesize_speech_api(
                ssml=ssml_text, voice_id=self.selected_voice, with_timepoints=True
            )
            response_data = response.json()
            audio_content = base64.b64decode(response_data["audioContent"])
            timepoints_data = response_data.get("timepoints", [])
            upload_dir = rx.get_upload_dir()
            upload_dir.mkdir(parents=True, exist_ok=True)
            filename = f"audio_{random.randint(1000, 9999)}.mp3"
            save_file_path = upload_dir / filename
            with open(save_file_path, "wb") as out:
                out.write(audio_content)
            async with self:
                self.audio_url = filename
                self.timepoints = timepoints_data
                self.is_generating_audio = False
            yield rx.toast.success("Audio generated successfully.")
            yield State.play_generated_audio
        except Exception as e:
            logging.exception(f"Error generating audio: {e}")
            async with self:
                self.is_generating_audio = False
            yield rx.toast.error(
                "Failed to generate audio. Check API key and that the API is enabled."
            )

    @rx.event(background=True)
    async def generate_preview_audio(self, voice_id: str):
        async with self:
            if self.is_generating_preview:
                return
            self.is_generating_preview = True
            self.preview_voice_id = voice_id
        yield
        try:
            preview_text = "<speak>Hello, this is a preview of my voice.</speak>"
            response = await self._synthesize_speech_api(
                ssml=preview_text, voice_id=voice_id, with_timepoints=False
            )
            response_data = response.json()
            audio_content = base64.b64decode(response_data["audioContent"])
            upload_dir = rx.get_upload_dir()
            upload_dir.mkdir(parents=True, exist_ok=True)
            filename = f"preview_{random.randint(1000, 9999)}.mp3"
            save_file_path = upload_dir / filename
            with open(save_file_path, "wb") as out:
                out.write(audio_content)
            async with self:
                self.preview_audio_url = filename
                self.is_generating_preview = False
            yield rx.call_script(
                f"var p_audio = document.getElementById('preview-player'); p_audio.src = '/_upload/{filename}'; p_audio.play();"
            )
        except Exception as e:
            logging.exception(f"Error generating preview audio: {e}")
            async with self:
                self.is_generating_preview = False
            yield rx.toast.error("Failed to generate preview.")

    @rx.event
    def handle_play_click(self):
        if self.is_generating_audio:
            return
        if self.audio_url:
            return State.toggle_play_pause
        if self.document_text:
            return State.generate_audio

    @rx.event
    def play_generated_audio(self):
        self.is_playing = True
        return rx.call_script(
            "setTimeout(() => { var audio = document.getElementById('audio-player'); if (audio) audio.play(); }, 100);"
        )

    @rx.event
    def toggle_play_pause(self):
        script = rx.call_script(
            f"document.getElementById('audio-player').{('play' if not self.is_playing else 'pause')}()"
        )
        self.is_playing = not self.is_playing
        return script

    @rx.event
    def on_time_update_callback(self, current_time: float):
        if not isinstance(current_time, (int, float)):
            current_time = 0
        self.current_time_str = self._format_time(current_time)
        if self.duration > 0:
            self.audio_progress = current_time / self.duration * 100
        else:
            self.audio_progress = 0
        current_index = -1
        for i, tp in enumerate(self.timepoints):
            if tp["time_seconds"] <= current_time:
                try:
                    current_index = int(tp["mark_name"].replace("s", ""))
                except (ValueError, TypeError) as e:
                    logging.exception(f"Error parsing timepoint mark name: {e}")
                    continue
            else:
                break
        if current_index != self.current_sentence_index:
            self.current_sentence_index = current_index
            if current_index != -1:
                return rx.scroll_to(
                    f"sentence-{current_index}", block="center", behavior="smooth"
                )

    @rx.event
    def on_time_update(self) -> rx.event.EventSpec:
        return rx.call_script(
            "document.getElementById('audio-player').currentTime",
            callback=State.on_time_update_callback,
        )

    @rx.event
    def on_duration_change_callback(self, duration: float):
        self.duration = duration
        self.duration_str = self._format_time(duration)

    @rx.event
    def on_duration_change(self) -> rx.event.EventSpec:
        return rx.call_script(
            "document.getElementById('audio-player').duration",
            callback=State.on_duration_change_callback,
        )

    @rx.event
    def on_ended(self):
        self.is_playing = False
        self.audio_progress = 100
        self.current_sentence_index = -1

    @rx.event
    def on_slider_change(self, value):
        return rx.call_script(
            f"\n            var audio = document.getElementById('audio-player');\n            if (audio.duration) {{\n                var newTime = audio.duration * ({value[0]} / 100);\n                audio.currentTime = newTime;\n            }}\n            "
        )

    @rx.event
    def seek_audio(self, seconds: int):
        return rx.call_script(
            f"\n            var audio = document.getElementById('audio-player');\n            audio.currentTime += {seconds};\n            "
        )

    def _format_time(self, seconds: float) -> str:
        if not isinstance(seconds, (int, float)) or seconds < 0:
            return "00:00"
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"