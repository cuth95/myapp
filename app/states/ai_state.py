import reflex as rx
import os
import google.generativeai as genai
import json
import logging
import re
from typing import TypedDict, TypeVar

T = TypeVar("T")
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    GEMINI_AVAILABLE = True
except KeyError as e:
    GEMINI_AVAILABLE = False
    logging.exception(f"GEMINI_API_KEY not set. AI features will be disabled. {e}")


class QuizQuestion(TypedDict):
    question: str
    options: list[str]
    correct_answer: int
    explanation: str
    user_answer: int | None
    is_correct: bool | None


class GlossaryTerm(TypedDict):
    term: str
    definition: str


class ChatMessage(TypedDict):
    role: str
    text: str


class AIState(rx.State):
    """Handles all AI-powered features using the Gemini API."""

    summary: str = ""
    is_summarizing: bool = False
    glossary: list[GlossaryTerm] = []
    is_generating_glossary: bool = False
    quiz: list[QuizQuestion] = []
    is_generating_quiz: bool = False
    quiz_score: int = 0
    quiz_submitted: bool = False
    chat_history: list[ChatMessage] = []
    current_chat_message: str = ""
    is_chatting: bool = False
    document_context: str = ""

    def _get_model(self):
        if not GEMINI_AVAILABLE:
            raise ConnectionError("Gemini API key not configured.")
        return genai.GenerativeModel("gemini-2.0-flash")

    def _safe_json_parse(self, json_string: str, default: T) -> T:
        """Safely parses a JSON string, extracting it from markdown code blocks if necessary."""
        try:
            match = re.search(
                "(json)?\\s*([\\s\\S]*?)\\s*|([\\[{].*[\\]}])", json_string, re.DOTALL
            )
            if match:
                json_content = (
                    match.group(2) if match.group(2) is not None else match.group(3)
                )
                if json_content:
                    return json.loads(json_content.strip())
            return json.loads(json_string)
        except (json.JSONDecodeError, TypeError) as e:
            logging.exception(f"Failed to parse JSON. String was: {json_string}")
            return default

    @rx.event(background=True)
    async def generate_summary(self, document_text: str):
        """Generates a summary of the document."""
        async with self:
            if self.is_summarizing:
                return
            self.is_summarizing = True
            self.summary = ""
        yield
        try:
            model = self._get_model()
            prompt = f"Summarize the following document in 3-5 key bullet points:\n\n{document_text[:28000]}"
            response = await model.generate_content_async(prompt)
            async with self:
                self.summary = response.text
        except Exception as e:
            logging.exception(f"Error generating summary: {e}")
            yield rx.toast.error("Failed to generate summary.")
        finally:
            async with self:
                self.is_summarizing = False

    @rx.event(background=True)
    async def generate_glossary(self, document_text: str):
        """Generates a glossary from the document."""
        async with self:
            if self.is_generating_glossary:
                return
            self.is_generating_glossary = True
            self.glossary = []
        yield
        try:
            model = self._get_model()
            prompt = f"""\n            Extract key technical terms and acronyms from this text and provide definitions for each.\n            Format as a JSON array of objects, where each object has a 'term' and a 'definition' field.\n            Example: [{{"term": "AI", "definition": "Artificial Intelligence."}}]\n\n            Text: {document_text[:28000]}\n            """
            response = await model.generate_content_async(prompt)
            parsed_glossary = self._safe_json_parse(response.text, [])
            async with self:
                self.glossary = parsed_glossary
        except Exception as e:
            logging.exception(f"Error generating glossary: {e}")
            yield rx.toast.error("Failed to generate glossary.")
        finally:
            async with self:
                self.is_generating_glossary = False

    @rx.event(background=True)
    async def generate_quiz(self, document_text: str):
        """Generates a quiz based on the document."""
        async with self:
            if self.is_generating_quiz:
                return
            self.is_generating_quiz = True
            self.quiz = []
            self.quiz_submitted = False
            self.quiz_score = 0
        yield
        try:
            num_questions = min(10, max(3, len(document_text.split()) // 200))
            model = self._get_model()
            prompt = f"\n            Generate {num_questions} multiple-choice questions based on this text.\n            Format as a JSON array of objects, where each object has:\n            - 'question': The question text (string).\n            - 'options': An array of 4 answer choices (list[str]).\n            - 'correct_answer': The index (0-3) of the correct option (int).\n            - 'explanation': A brief explanation of why the answer is correct (string).\n\n            Text: {document_text[:28000]}\n            "
            response = await model.generate_content_async(prompt)
            parsed_quiz = self._safe_json_parse(response.text, [])
            for q in parsed_quiz:
                q["user_answer"] = None
                q["is_correct"] = None
            async with self:
                self.quiz = parsed_quiz
        except Exception as e:
            logging.exception(f"Error generating quiz: {e}")
            yield rx.toast.error("Failed to generate quiz.")
        finally:
            async with self:
                self.is_generating_quiz = False

    @rx.event
    def select_quiz_answer(self, question_index: int, answer_index: int):
        """Records the user's answer for a quiz question."""
        if not self.quiz_submitted:
            self.quiz[question_index]["user_answer"] = answer_index

    @rx.event
    def submit_quiz(self):
        """Grades the quiz and shows the results."""
        if any((q["user_answer"] is None for q in self.quiz)):
            return rx.toast.warning("Please answer all questions before submitting.")
        score = 0
        for i, q in enumerate(self.quiz):
            is_correct = q["user_answer"] == q["correct_answer"]
            self.quiz[i]["is_correct"] = is_correct
            if is_correct:
                score += 1
        self.quiz_score = score
        self.quiz_submitted = True

    @rx.event(background=True)
    async def start_chat(self, document_text: str):
        """Initializes the chat session with document context."""
        async with self:
            self.document_context = document_text
            self.chat_history = []
            self.is_chatting = False
            self.current_chat_message = ""
        yield rx.toast.info("Chat initialized. Ask a question about the document!")

    @rx.event(background=True)
    async def send_chat_message(self, form_data: dict[str, str]):
        """Sends a message to the chat and gets a response."""
        message_text = form_data["message"].strip()
        if not message_text or self.is_chatting:
            return
        async with self:
            self.is_chatting = True
            self.chat_history.append({"role": "user", "text": message_text})
            self.chat_history.append({"role": "model", "text": ""})
            self.current_chat_message = ""
        yield
        try:
            model = self._get_model()
            chat = model.start_chat(
                history=[
                    {"role": msg["role"], "parts": [msg["text"]]}
                    for msg in self.chat_history[:-2]
                ]
            )
            context_prompt = f"\n            You are a helpful assistant. Use the following document context to answer the user's question.\n            If the answer isn't in the document, use your general knowledge but mention you are doing so.\n\n            DOCUMENT CONTEXT:\n            ---\n            {self.document_context[:25000]}\n            ---\n            USER QUESTION: {message_text}\n            "
            response = await chat.send_message_async(context_prompt, stream=True)
            current_response_text = ""
            async for chunk in response:
                current_response_text += chunk.text
                async with self:
                    self.chat_history[-1]["text"] = current_response_text
                yield
        except Exception as e:
            logging.exception(f"Error in chat: {e}")
            error_message = "Sorry, I encountered an error. Please try again."
            async with self:
                self.chat_history[-1]["text"] = error_message
        finally:
            async with self:
                self.is_chatting = False
            yield rx.call_script("document.getElementById('chat-input').form.reset()")

    @rx.event
    def clear_ai_states(self):
        """Clears all AI-related data."""
        self.summary = ""
        self.glossary = []
        self.quiz = []
        self.chat_history = []
        self.is_summarizing = False
        self.is_generating_glossary = False
        self.is_generating_quiz = False
        self.is_chatting = False