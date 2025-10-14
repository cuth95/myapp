import reflex as rx
from app.states.state import State
from app.states.ai_state import AIState


def ai_tool_button(text: str, tool_name: str) -> rx.Component:
    """A button to launch an AI tool modal."""
    on_click_events = {
        "reader": lambda: State.set_active_tab("reader"),
        "summarizer": [
            lambda: State.set_show_summarizer(True),
            lambda: AIState.generate_summary(State.document_text),
        ],
        "glossary": [
            lambda: State.set_show_glossary(True),
            lambda: AIState.generate_glossary(State.document_text),
        ],
        "quiz": [
            lambda: State.set_show_quiz(True),
            lambda: AIState.generate_quiz(State.document_text),
        ],
        "chat": [
            lambda: State.set_show_chat(True),
            lambda: AIState.start_chat(State.document_text),
        ],
    }
    is_active = rx.cond(
        tool_name == "reader",
        State.active_tab == "reader",
        rx.match(
            tool_name,
            ("summarizer", State.show_summarizer),
            ("glossary", State.show_glossary),
            ("quiz", State.show_quiz),
            ("chat", State.show_chat),
            False,
        ),
    )
    return rx.el.button(
        text,
        on_click=on_click_events.get(tool_name),
        class_name=rx.cond(
            is_active,
            "w-full text-left px-4 py-2 rounded-lg bg-gray-100 font-semibold text-gray-800",
            "w-full text-left px-4 py-2 rounded-lg hover:bg-gray-50 text-gray-600",
        ),
        disabled=rx.cond(tool_name != "reader", ~State.uploaded_file, False),
    )


def voice_option(voice: dict[str, str]) -> rx.Component:
    return rx.el.option(voice["name"], value=voice["id"])


def voice_selection() -> rx.Component:
    return rx.el.div(
        rx.el.label("Voice", class_name="font-medium text-sm text-gray-700"),
        rx.el.div(
            rx.el.select(
                rx.foreach(State.voices, voice_option),
                on_change=State.set_selected_voice,
                default_value=State.selected_voice,
                class_name="mt-1 w-full p-2 border rounded-md appearance-none",
                padding_right="2.5rem",
            ),
            rx.el.button(
                rx.cond(
                    State.is_generating_preview
                    & (State.preview_voice_id == State.selected_voice),
                    rx.spinner(class_name="h-4 w-4"),
                    rx.icon("play", class_name="h-4 w-4"),
                ),
                on_click=lambda: State.generate_preview_audio(State.selected_voice),
                class_name="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-500 hover:text-violet-600",
                disabled=State.is_generating_preview,
            ),
            class_name="relative mt-1",
        ),
        class_name="mt-4",
    )


def sidebar_footer() -> rx.Component:
    """The footer for the sidebar with user info and logout."""
    return rx.el.div(
        rx.el.div(
            rx.image(
                src="https://api.dicebear.com/9.x/notionists/svg?seed=JohnDoe",
                class_name="h-9 w-9 rounded-full",
            ),
            rx.el.div(
                rx.el.p("John Doe", class_name="text-sm font-semibold text-gray-700"),
                rx.el.p("john.doe@example.com", class_name="text-xs text-gray-500"),
                class_name="ml-3",
            ),
            class_name="flex items-center",
        ),
        rx.el.button(
            rx.icon(
                "log-out", class_name="h-5 w-5 text-gray-500 hover:text-violet-600"
            ),
            on_click=rx.toast.info("Logout clicked!"),
            class_name="p-2 rounded-lg hover:bg-gray-100",
        ),
        class_name="flex items-center justify-between p-4 border-t border-gray-200 shrink-0",
    )


def sidebar() -> rx.Component:
    """The sidebar component."""
    return rx.el.div(
        rx.el.div(
            rx.el.div(
                rx.el.h1("Readify", class_name="text-2xl font-bold text-violet-600"),
                class_name="p-4 border-b border-gray-200",
            ),
            rx.el.div(
                rx.upload.root(
                    rx.el.div(
                        rx.el.button(
                            rx.icon("cloud_upload", class_name="mr-2"),
                            "Upload PDF",
                            class_name=rx.cond(
                                State.uploading,
                                "bg-violet-200 text-violet-700 font-semibold py-2 px-4 rounded-lg w-full flex items-center justify-center cursor-not-allowed",
                                "bg-violet-500 hover:bg-violet-600 text-white font-semibold py-2 px-4 rounded-lg w-full flex items-center justify-center",
                            ),
                            disabled=State.uploading,
                        ),
                        class_name="w-full",
                    ),
                    id="pdf-upload",
                    on_drop=State.handle_upload(
                        rx.upload_files(upload_id="pdf-upload")
                    ),
                    class_name="w-full p-4 border-dashed border-gray-300 rounded-lg text-center cursor-pointer hover:border-violet-500",
                ),
                rx.cond(
                    State.uploading,
                    rx.el.div(
                        rx.el.progress(
                            value=State.upload_progress, class_name="w-full"
                        ),
                        rx.el.p(
                            "Uploading...", class_name="text-sm text-gray-500 mt-2"
                        ),
                        class_name="w-full mt-4",
                    ),
                    rx.cond(
                        State.uploaded_file,
                        rx.el.div(
                            rx.el.div(
                                rx.icon("file-text", class_name="text-gray-500"),
                                rx.el.p(
                                    State.original_filename,
                                    class_name="text-sm text-gray-700 ml-2 truncate",
                                ),
                                class_name="flex items-center p-2 bg-gray-100 rounded-md mt-4",
                            )
                        ),
                        rx.el.div(),
                    ),
                ),
                voice_selection(),
                class_name="p-4 border-b border-gray-200",
            ),
            rx.el.div(
                rx.el.h3(
                    "AI Tools",
                    class_name="px-4 text-sm font-semibold text-gray-500 uppercase tracking-wider",
                ),
                ai_tool_button("Reader", "reader"),
                ai_tool_button("Summarizer", "summarizer"),
                ai_tool_button("Glossary", "glossary"),
                ai_tool_button("Quiz", "quiz"),
                ai_tool_button("Chat", "chat"),
                class_name="p-4 space-y-2",
            ),
            class_name="flex-grow overflow-y-auto",
        ),
        sidebar_footer(),
        class_name="w-80 h-screen bg-white border-r border-gray-200 flex flex-col",
    )