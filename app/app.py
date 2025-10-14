import reflex as rx
from app.states.state import State
from app.components.sidebar import sidebar
from app.components.player_bar import player_bar
from app.components.reader_view import reader_view
from app.components.ai_tools import (
    summarizer_modal,
    glossary_modal,
    quiz_modal,
    chat_modal,
)


def main_content_area() -> rx.Component:
    """The main content area, including document display and player."""
    return rx.el.div(
        reader_view(),
        rx.cond(State.uploaded_file, player_bar(), rx.el.div()),
        class_name="flex-grow flex flex-col relative bg-gray-50",
    )


def index() -> rx.Component:
    """The main page of the app."""
    return rx.el.main(
        rx.el.div(
            sidebar(), main_content_area(), class_name="flex h-screen overflow-hidden"
        ),
        summarizer_modal(),
        glossary_modal(),
        quiz_modal(),
        chat_modal(),
        rx.el.audio(id="preview-player", class_name="hidden"),
        class_name="font-['Inter'] bg-white",
    )


app = rx.App(
    theme=rx.theme(appearance="light"),
    head_components=[
        rx.el.link(rel="preconnect", href="https://fonts.googleapis.com"),
        rx.el.link(rel="preconnect", href="https://fonts.gstatic.com", cross_origin=""),
        rx.el.link(
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
            rel="stylesheet",
        ),
    ],
)
app.add_page(index)