import reflex as rx
from app.states.state import State


def sentence_component(sentence: tuple[str, int]) -> rx.Component:
    """Renders a single sentence with highlighting. This is not displayed but used for audio sync."""
    return rx.el.span(
        sentence[0],
        id=f"sentence-{sentence[1]}",
        class_name=rx.cond(
            State.current_sentence_index == sentence[1], "bg-yellow-200", ""
        ),
    )


def reader_view() -> rx.Component:
    """The reader view component with PDF display."""
    return rx.el.div(
        rx.cond(
            State.uploaded_file,
            rx.el.div(
                rx.el.iframe(
                    src=rx.get_upload_url(State.uploaded_file)
                    + "#zoom="
                    + State.zoom_level.to_string(),
                    class_name="w-full h-full border-none",
                    key=State.uploaded_file,
                ),
                rx.el.div(
                    rx.foreach(State.sentences, sentence_component), class_name="hidden"
                ),
                class_name="w-full h-full",
            ),
            rx.el.div(
                rx.icon("file-search", class_name="h-16 w-16 text-gray-300"),
                rx.el.p(
                    "Upload a PDF to get started",
                    class_name="mt-4 text-lg text-gray-500",
                ),
                class_name="w-full h-full flex flex-col items-center justify-center p-4 border-dashed border-gray-200 rounded-lg bg-gray-50",
            ),
        ),
        class_name="flex-grow",
    )