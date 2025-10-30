import reflex as rx
from app.states.state import State


def player_bar() -> rx.Component:
    """The audio player bar."""
    return rx.el.div(
        rx.el.div(
            rx.el.button(
                rx.icon("rewind", class_name="h-5 w-5"),
                on_click=lambda: State.seek_audio(-20),
                disabled=State.is_generating_audio,
            ),
            rx.el.button(
                rx.cond(
                    State.is_generating_audio,
                    rx.spinner(class_name="h-6 w-6"),
                    rx.icon(
                        rx.cond(State.is_playing, "pause", "play"), class_name="h-6 w-6"
                    ),
                ),
                on_click=State.handle_play_click,
                class_name="bg-violet-500 text-white rounded-full p-3 mx-4 disabled:bg-violet-300",
                disabled=State.is_generating_audio,
            ),
            rx.el.button(
                rx.icon("fast-forward", class_name="h-5 w-5"),
                on_click=lambda: State.seek_audio(20),
                disabled=State.is_generating_audio,
            ),
            class_name="flex items-center",
        ),
        rx.el.div(
            rx.el.span(State.current_time_str, class_name="text-xs w-12 text-center"),
            rx.el.input(
                type="range",
                on_change=State.on_slider_change.throttle(100),
                class_name="w-full mx-4 accent-violet-500",
                min=0,
                max=100,
                default_value=State.audio_progress,
                key=State.audio_url,
                disabled=State.is_generating_audio,
            ),
            rx.el.span(State.duration_str, class_name="text-xs w-12 text-center"),
            class_name="flex items-center flex-grow mx-6",
        ),
        rx.el.div(
            rx.el.button(
                rx.icon("zoom-out", class_name="h-5 w-5"), on_click=State.zoom_out
            ),
            rx.el.button(
                rx.icon("zoom-in", class_name="h-5 w-5"),
                on_click=State.zoom_in,
                class_name="mx-2",
            ),
            rx.el.button(
                rx.icon("download", class_name="h-5 w-5"),
                on_click=rx.download(
                    url=rx.get_upload_url(State.audio_url), filename="audio.mp3"
                ),
                disabled=~State.audio_url,
            ),
            class_name="flex items-center",
        ),
        rx.el.audio(
            src=rx.cond(State.audio_url, rx.get_upload_url(State.audio_url), ""),
            id="audio-player",
            key=State.audio_url,
            custom_attrs={
                "onTimeUpdate": State.on_time_update,
                "onLoadedMetadata": State.on_duration_change,
                "onEnded": State.on_ended,
            },
        ),
        class_name="fixed bottom-0 left-80 right-0 h-16 bg-white border-t border-gray-200 flex items-center px-6 z-10",
    )