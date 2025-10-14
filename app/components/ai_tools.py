import reflex as rx
from app.states.state import State
from app.states.ai_state import AIState, QuizQuestion, GlossaryTerm, ChatMessage


def loading_view(text: str) -> rx.Component:
    """A view to show while content is loading."""
    return rx.el.div(
        rx.spinner(class_name="w-8 h-8 text-violet-500"),
        rx.el.p(text, class_name="mt-4 text-lg text-gray-600"),
        class_name="flex flex-col items-center justify-center h-full text-center p-6",
    )


def summarizer_modal() -> rx.Component:
    """Modal to display the document summary."""
    return rx.radix.primitives.dialog.root(
        rx.radix.primitives.dialog.content(
            rx.radix.primitives.dialog.title("Document Summary"),
            rx.radix.primitives.dialog.description(
                rx.cond(
                    AIState.is_summarizing,
                    loading_view("Generating summary..."),
                    rx.el.div(
                        rx.markdown(
                            AIState.summary,
                            class_name="prose prose-violet max-w-none text-gray-700",
                        ),
                        class_name="mt-4 max-h-96 overflow-y-auto",
                    ),
                )
            ),
            rx.el.div(
                rx.radix.primitives.dialog.close(
                    rx.el.button(
                        "Close",
                        class_name="mt-4 px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300",
                    )
                ),
                class_name="flex justify-end mt-4",
            ),
            style={"max_width": "600px"},
        ),
        open=State.show_summarizer,
        on_open_change=State.set_show_summarizer,
    )


def glossary_term_item(term: GlossaryTerm) -> rx.Component:
    return rx.el.div(
        rx.el.dt(term["term"], class_name="font-semibold text-violet-700"),
        rx.el.dd(term["definition"], class_name="ml-4 text-gray-600"),
        class_name="py-2",
    )


def glossary_modal() -> rx.Component:
    """Modal to display the glossary of terms."""
    return rx.radix.primitives.dialog.root(
        rx.radix.primitives.dialog.content(
            rx.radix.primitives.dialog.title("Glossary"),
            rx.radix.primitives.dialog.description(
                rx.cond(
                    AIState.is_generating_glossary,
                    loading_view("Generating glossary..."),
                    rx.el.div(
                        rx.el.dl(
                            rx.foreach(AIState.glossary, glossary_term_item),
                            class_name="divide-y divide-gray-200",
                        ),
                        class_name="mt-4 max-h-96 overflow-y-auto",
                    ),
                )
            ),
            rx.el.div(
                rx.radix.primitives.dialog.close(
                    rx.el.button(
                        "Close",
                        class_name="mt-4 px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300",
                    )
                ),
                class_name="flex justify-end mt-4",
            ),
            style={"max_width": "600px"},
        ),
        open=State.show_glossary,
        on_open_change=State.set_show_glossary,
    )


def quiz_question_component(question: QuizQuestion, index: int) -> rx.Component:
    """Component for a single quiz question."""
    return rx.el.div(
        rx.el.p(f"{index + 1}. {question['question']}", class_name="font-semibold"),
        rx.el.div(
            rx.foreach(
                question["options"],
                lambda option, opt_index: rx.el.div(
                    rx.el.input(
                        type="radio",
                        name=f"q{index}",
                        value=opt_index,
                        on_change=lambda: AIState.select_quiz_answer(index, opt_index),
                        checked=question["user_answer"] == opt_index,
                        disabled=AIState.quiz_submitted,
                        class_name="mr-2 accent-violet-500",
                    ),
                    rx.el.label(
                        option,
                        class_name=rx.cond(
                            AIState.quiz_submitted
                            & (question["correct_answer"] == opt_index),
                            "text-green-600 font-bold",
                            rx.cond(
                                AIState.quiz_submitted
                                & (question["user_answer"] == opt_index)
                                & (question["is_correct"] == False),
                                "text-red-600 line-through",
                                "text-gray-700",
                            ),
                        ),
                    ),
                    class_name="flex items-center",
                ),
            ),
            class_name="mt-2 space-y-2",
        ),
        rx.cond(
            AIState.quiz_submitted,
            rx.el.div(
                rx.cond(
                    question["is_correct"],
                    rx.el.p("Correct!", class_name="text-sm text-green-700"),
                    rx.el.p("Incorrect.", class_name="text-sm text-red-700"),
                ),
                rx.el.p(
                    question["explanation"], class_name="text-sm text-gray-500 mt-1"
                ),
                class_name="p-2 mt-2 bg-gray-50 rounded-md border",
            ),
            rx.el.div(),
        ),
        class_name="my-4 p-4 border rounded-lg",
    )


def quiz_modal() -> rx.Component:
    """Modal for the interactive quiz."""
    return rx.radix.primitives.dialog.root(
        rx.radix.primitives.dialog.content(
            rx.radix.primitives.dialog.title("Quiz"),
            rx.cond(
                AIState.quiz_submitted,
                rx.el.div(
                    rx.el.p(
                        f"Your Score: {AIState.quiz_score} / {AIState.quiz.length()}",
                        class_name="text-lg font-bold text-center text-violet-700",
                    ),
                    class_name="text-center",
                ),
                rx.el.div(),
            ),
            rx.radix.primitives.dialog.description(
                rx.cond(
                    AIState.is_generating_quiz,
                    loading_view("Generating quiz..."),
                    rx.el.div(
                        rx.foreach(AIState.quiz, quiz_question_component),
                        class_name="mt-4 max-h-[60vh] overflow-y-auto",
                    ),
                )
            ),
            rx.el.div(
                rx.cond(
                    ~AIState.is_generating_quiz & (AIState.quiz.length() > 0),
                    rx.el.button(
                        rx.cond(
                            AIState.quiz_submitted, "Retake Quiz", "Submit Answers"
                        ),
                        on_click=rx.cond(
                            AIState.quiz_submitted,
                            AIState.generate_quiz(State.document_text),
                            AIState.submit_quiz,
                        ),
                        class_name="px-4 py-2 bg-violet-500 text-white rounded-md hover:bg-violet-600",
                    ),
                    rx.el.div(),
                ),
                rx.radix.primitives.dialog.close(
                    rx.el.button(
                        "Close",
                        class_name="ml-2 px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300",
                    )
                ),
                class_name="flex justify-end mt-4",
            ),
            style={"max_width": "800px"},
        ),
        open=State.show_quiz,
        on_open_change=State.set_show_quiz,
    )


def chat_message_component(message: ChatMessage) -> rx.Component:
    """Component for a single chat message."""
    return rx.el.div(
        rx.cond(
            message["role"] == "user",
            rx.el.p(
                message["text"],
                class_name="bg-violet-500 text-white p-3 rounded-lg max-w-lg",
            ),
            rx.el.div(
                rx.cond(
                    message["text"] == "",
                    loading_view("..."),
                    rx.markdown(
                        message["text"],
                        class_name="prose prose-sm max-w-none text-gray-800",
                    ),
                ),
                class_name="bg-gray-100 p-3 rounded-lg max-w-lg",
            ),
        ),
        class_name=rx.cond(
            message["role"] == "user", "flex justify-end", "flex justify-start"
        ),
    )


def chat_modal() -> rx.Component:
    """Modal for the interactive chat."""
    return rx.radix.primitives.dialog.root(
        rx.radix.primitives.dialog.content(
            rx.radix.primitives.dialog.title("Chat with Document"),
            rx.el.div(
                rx.scroll_area(
                    rx.el.div(
                        rx.foreach(AIState.chat_history, chat_message_component),
                        class_name="space-y-4 p-4",
                    ),
                    type="always",
                    scrollbars="vertical",
                    class_name="h-96 border rounded-md bg-white",
                ),
                rx.el.form(
                    rx.el.input(
                        id="chat-input",
                        name="message",
                        placeholder="Ask a question...",
                        class_name="flex-grow p-2 border rounded-l-md",
                        disabled=AIState.is_chatting,
                    ),
                    rx.el.button(
                        rx.icon("send", class_name="h-5 w-5"),
                        type="submit",
                        class_name="p-2 bg-violet-500 text-white rounded-r-md disabled:bg-violet-300",
                        disabled=AIState.is_chatting,
                    ),
                    on_submit=AIState.send_chat_message,
                    class_name="flex mt-4",
                ),
                class_name="mt-4",
            ),
            rx.el.div(
                rx.radix.primitives.dialog.close(
                    rx.el.button(
                        "Close",
                        class_name="mt-4 px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300",
                    )
                ),
                class_name="flex justify-end mt-4",
            ),
            style={"max_width": "800px"},
        ),
        open=State.show_chat,
        on_open_change=State.set_show_chat,
    )