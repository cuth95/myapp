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
    is_processing_pdf: bool = False
    pdf_page_count: int = 0
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
    sentence_to_page: dict[int, int] = {}
    timepoints: list[dict[str, str | float]] = []
    current_sentence_index: int = -1
    original_filename: str = ""
    show_summarizer: bool = False
    show_glossary: bool = False
    show_quiz: bool = False
    show_chat: bool = False
    minimized_chat: bool = False

    @rx.event
    def zoom_in(self):
        self.zoom_level += 10
        yield self._render_pdf_script()

    @rx.event
    def zoom_out(self):
        self.zoom_level = max(50, self.zoom_level - 10)
        yield self._render_pdf_script()

    def _reset_audio_state(self):
        self.audio_url = None
        self.is_playing = False
        self.audio_progress = 0
        self.current_time_str = "00:00"
        self.duration = 0
        self.duration_str = "00:00"
        self.timepoints = []
        self.current_sentence_index = -1

    def _reset_pdf_state(self):
        self.document_text = ""
        self.is_processing_pdf = False
        self.pdf_page_count = 0
        self.sentences = []
        self.sentence_to_page = {}

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
        self.upload_progress = 30
        yield
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
        self.upload_progress = 60
        yield
        self.uploaded_file = unique_name
        self.original_filename = file.name
        self._reset_audio_state()
        self._reset_pdf_state()
        self.is_processing_pdf = True
        self.uploading = False
        self.upload_progress = 100
        yield
        ai_state = await self.get_state(AIState)
        ai_state.clear_ai_states()
        yield rx.toast.success(f"Uploaded {file.name}. Processing...")
        yield State.process_pdf

    @rx.event(background=True)
    async def process_pdf(self):
        """Extracts text and renders PDF using PDF.js."""
        async with self:
            if not self.uploaded_file:
                return
            file_path = rx.get_upload_dir() / self.uploaded_file
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                num_pages = len(reader.pages)
            async with self:
                self.pdf_page_count = num_pages
            yield
            yield self._render_pdf_script()
        except Exception as e:
            logging.exception(f"Error processing PDF: {e}")
            async with self:
                self.is_processing_pdf = False
            yield rx.toast.error("Failed to process PDF.")

    def _render_pdf_script(self) -> rx.event.EventSpec:
        """Returns the script to render the PDF and extract text."""
        return rx.call_script(
            f"(async () => {{\n    try {{\n        const url = '/_upload/{self.uploaded_file}';\n        const pdfDoc = await pdfjsLib.getDocument(url).promise;\n        const allText = [];\n        const sentenceToPageMap = {{}};\n        const sentences = [];\n        const sentenceEnds = /(?<!\\w\\.\\w.)(?<![A-Z][a-z]\\.)(?<=\\.|\\?|!)\\s/g;\n\n        let currentSentence = '';\n        let sentenceIndex = 0;\n\n        for (let i = 1; i <= {self.pdf_page_count}; i++) {{\n            const page = await pdfDoc.getPage(i);\n            const scale = {self.zoom_level} / 100;\n            const viewport = page.getViewport({{ scale }});\n            const canvas = document.getElementById(`pdf-canvas-${{i-1}}`);\n            const context = canvas.getContext('2d');\n            canvas.height = viewport.height;\n            canvas.width = viewport.width;\n\n            const renderContext = {{ canvasContext: context, viewport: viewport }};\n            await page.render(renderContext).promise;\n\n            const textContent = await page.getTextContent();\n            const pageText = textContent.items.map(item => item.str).join(' ');\n\n            let textRuns = [];\n            let lastY = -1;\n            textContent.items.forEach(item => {{\n                if(Math.abs(item.transform[5] - lastY) > 2) {{\n                   if(textRuns.length > 0) textRuns[textRuns.length-1].text += ' ';\n                   textRuns.push({{text: '', items: []}});\n                }}\n                textRuns[textRuns.length-1].text += item.str;\n                textRuns[textRuns.length-1].items.push(item);\n                lastY = item.transform[5];\n            }});\n\n            textRuns.forEach(run => {{\n                let parts = run.text.split(sentenceEnds);\n                let currentItemIndex = 0;\n                parts.forEach((part, index) => {{\n                    if (!part.trim()) return;\n\n                    currentSentence += part.trim() + (index < parts.length - 1 ? ' ' : '');\n                    \n                    if (sentenceEnds.test(run.text.substring(currentSentence.length-2, currentSentence.length+2)) || index === parts.length-1) {{\n                        if (currentSentence.trim()) {{\n                            sentences.push([currentSentence.trim(), sentenceIndex]);\n                            sentenceToPageMap[sentenceIndex] = i - 1;\n                            sentenceIndex++;\n                        }}\n                        currentSentence = '';\n                    }}\n                }});\n            }});\n            allText.push(pageText);\n        }}\n        const fullText = allText.join(' ').replace(/\\s+/g, ' ');\n        return [fullText, sentences, sentenceToPageMap];\n    }} catch (error) {{\n        console.error('Error processing PDF:', error);\n        return [null, [], {{}}]; // Return empty data on error to unblock the UI\n    }}\n}})()",
            callback=State.on_pdf_processed,
        )

    @rx.event
    def on_pdf_processed(self, result: list):
        """Callback after PDF.js has processed the document."""
        if not result or len(result) < 3 or (not result[0]):
            self.is_processing_pdf = False
            return rx.toast.error("Failed to extract text from PDF.")
        self.document_text, self.sentences, self.sentence_to_page = (
            result[0],
            [tuple(s) for s in result[1]],
            {int(k): v for k, v in result[2].items()},
        )
        self.is_processing_pdf = False
        return rx.toast.success("Document is ready!")

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
                return self._update_highlight_script(current_index)

    def _update_highlight_script(self, sentence_index: int) -> rx.event.EventSpec:
        """Returns script to highlight sentence and scroll it into view."""
        return rx.call_script(
            f"\n            (async () => {{\n                const sentenceIndex = {sentence_index};\n                const sentenceToPageMap = {json.dumps(self.sentence_to_page)};\n                const pageNum = sentenceToPageMap[sentenceIndex];\n                if (pageNum === undefined) return;\n\n                const sentences = {json.dumps(self.sentences)};\n                const sentenceText = sentences.find(s => s[1] === sentenceIndex)[0];\n\n                const url = '/_upload/{self.uploaded_file}';\n                const pdfDoc = await pdfjsLib.getDocument(url).promise;\n                const page = await pdfDoc.getPage(pageNum + 1);\n                const scale = {self.zoom_level} / 100;\n                const viewport = page.getViewport({{ scale }});\n                const textContent = await page.getTextContent();\n\n                const bidiTexts = textContent.items.map(item => item.str);\n                const sentenceStartIndex = bidiTexts.join('').indexOf(sentenceText.substring(0, 15));\n                const sentenceEndIndex = sentenceStartIndex + sentenceText.length;\n\n                let charCount = 0;\n                let highlightRects = [];\n                let firstRect = null;\n\n                for (const item of textContent.items) {{\n                    const itemStart = charCount;\n                    const itemEnd = charCount + item.str.length;\n\n                    if (itemEnd > sentenceStartIndex && itemStart < sentenceEndIndex) {{\n                        const [x, y, width, height] = [\n                            item.transform[4],\n                            viewport.height - item.transform[5] - item.height,\n                            item.width,\n                            item.height,\n                        ];\n                        const rect = {{ x, y, width, height }};\n                        highlightRects.push(rect);\n                        if (!firstRect) firstRect = rect;\n                    }}\n                    charCount = itemEnd;\n                }}\n                \n                const highlightLayer = document.getElementById('highlight-layer');\n                const pdfContainer = document.getElementById('pdf-container');\n                const pageCanvas = document.getElementById(`pdf-canvas-${{pageNum}}`);\n                highlightLayer.innerHTML = ''; // Clear previous highlights\n\n                if (highlightRects.length > 0) {{\n                    highlightLayer.style.left = `${{pageCanvas.offsetLeft}}px`;\n                    highlightLayer.style.top = `${{pageCanvas.offsetTop}}px`;\n                    highlightLayer.style.width = `${{pageCanvas.width}}px`;\n                    highlightLayer.style.height = `${{pageCanvas.height}}px`;\n\n                    highlightRects.forEach(rect => {{\n                        const div = document.createElement('div');\n                        div.style.position = 'absolute';\n                        div.style.backgroundColor = 'rgba(252, 211, 77, 0.4)';\n                        div.style.left = `${{rect.x}}px`;\n                        div.style.top = `${{rect.y}}px`;\n                        div.style.width = `${{rect.width}}px`;\n                        div.style.height = `${{rect.height}}px`;\n                        highlightLayer.appendChild(div);\n                    }});\n                    \n                    if (firstRect) {{\n                         pdfContainer.scrollTo({{\n                             top: pageCanvas.offsetTop + firstRect.y - pdfContainer.clientHeight / 4,\n                             behavior: 'smooth'\n                         }});\n                    }}\n                }}\n            }})();\n            "
        )

    @rx.event
    def on_time_update(self) -> rx.event.EventSpec:
        return rx.call_script(
            "document.getElementById('audio-player').currentTime",
            callback=State.on_time_update_callback,
        )

    @rx.event
    def on_duration_change_callback(self, duration: float):
        if not isinstance(duration, (int, float)):
            duration = 0
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
        return rx.call_script(
            "var hl = document.getElementById('highlight-layer'); if(hl) hl.innerHTML = '';"
        )

    @rx.event
    def on_slider_change(self, value: int):
        return rx.call_script(
            f"\n            var audio = document.getElementById('audio-player');\n            if (audio.duration) {{\n                var newTime = audio.duration * ({value} / 100);\n                audio.currentTime = newTime;\n            }}\n            "
        )

    @rx.event
    def seek_audio(self, seconds: int):
        """Seeks the audio forward or backward by a number of seconds."""
        return rx.call_script(
            f"\n            var audio = document.getElementById('audio-player');\n            audio.currentTime += {seconds};\n            "
        )

    def _format_time(self, seconds: float) -> str:
        if not isinstance(seconds, (int, float)) or seconds < 0:
            return "00:00"
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"