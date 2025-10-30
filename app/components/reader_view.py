import reflex as rx
from app.states.state import State


def pdf_page_canvas(page_num: int) -> rx.Component:
    """A canvas for rendering a single PDF page."""
    return rx.el.div(
        rx.el.canvas(id=f"pdf-canvas-{page_num}", class_name="shadow-lg"),
        rx.el.div(id=f"text-layer-{page_num}", class_name="absolute top-0 left-0"),
        class_name="relative",
    )


def reader_view() -> rx.Component:
    """The reader view component with PDF display."""
    return rx.el.div(
        rx.cond(
            State.is_processing_pdf,
            rx.el.div(
                rx.spinner(class_name="w-12 h-12 text-violet-500"),
                rx.el.p("Analyzing your document...", class_name="mt-4 text-gray-600"),
                class_name="flex flex-col items-center justify-center h-full",
            ),
            rx.cond(
                State.uploaded_file,
                rx.el.div(
                    rx.foreach(rx.Var.range(State.pdf_page_count), pdf_page_canvas),
                    rx.el.div(
                        id="highlight-layer",
                        class_name="absolute top-0 left-0 pointer-events-none",
                    ),
                    id="pdf-container",
                    class_name="w-full h-full overflow-y-auto p-8 space-y-4 bg-gray-200",
                ),
                rx.el.div(
                    rx.icon("file-search", class_name="h-16 w-16 text-gray-300"),
                    rx.el.p(
                        "Upload a PDF to get started",
                        class_name="mt-4 text-lg text-gray-500",
                    ),
                    class_name="w-full h-full flex flex-col items-center justify-center p-4 border-dashed border-2 border-gray-200 rounded-lg bg-gray-50",
                ),
            ),
        ),
        class_name="flex-grow overflow-hidden",
    )