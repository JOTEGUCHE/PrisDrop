"""Integración del reproductor de escritorio con los controles multimedia de Windows."""
from pathlib import Path

from PySide6.QtCore import QObject, Signal


class WindowsMediaControls(QObject):
    button_pressed = Signal(str)

    def __init__(self, window_handle: int, parent=None):
        super().__init__(parent)
        from winrt.windows.media import (
            MediaPlaybackStatus,
            MediaPlaybackType,
            SystemMediaTransportControlsButton,
        )
        from winrt.windows.media.interop import get_for_window
        from winrt.windows.storage import StorageFile
        from winrt.windows.storage.streams import RandomAccessStreamReference

        self._media_type = MediaPlaybackType
        self._button_type = SystemMediaTransportControlsButton
        self._playback_status_type = MediaPlaybackStatus
        self._storage_file_type = StorageFile
        self._stream_reference_type = RandomAccessStreamReference
        self._controls = get_for_window(window_handle)
        self._button_token = self._controls.add_button_pressed(self._on_button_pressed)
        self._controls.is_enabled = True
        self._controls.is_play_enabled = True
        self._controls.is_pause_enabled = True
        self._controls.is_stop_enabled = True
        self._controls.is_next_enabled = True
        self._controls.is_previous_enabled = True

    def set_media(self, title: str, artist: str, is_video: bool, thumbnail_path: str):
        self._controls.is_enabled = True
        updater = self._controls.display_updater
        updater.clear_all()
        if is_video:
            updater.type = self._media_type.VIDEO
            updater.video_properties.title = title
            updater.video_properties.subtitle = artist
        else:
            updater.type = self._media_type.MUSIC
            updater.music_properties.title = title
            updater.music_properties.artist = artist

        thumbnail = Path(thumbnail_path) if thumbnail_path else None
        if thumbnail is not None and thumbnail.is_file():
            storage_file = self._storage_file_type.get_file_from_path_async(
                str(thumbnail.resolve())).get()
            updater.thumbnail = self._stream_reference_type.create_from_file(storage_file)
        updater.update()

    def set_playback_state(self, state: str):
        status = {
            "playing": self._playback_status_type.PLAYING,
            "paused": self._playback_status_type.PAUSED,
            "stopped": self._playback_status_type.STOPPED,
        }.get(state)
        if status is None:
            raise ValueError(f"Estado multimedia no válido: {state}")
        self._controls.playback_status = status

    def clear_media(self):
        self._controls.playback_status = self._playback_status_type.STOPPED
        updater = self._controls.display_updater
        updater.clear_all()
        updater.update()
        self._controls.is_enabled = False

    def close(self):
        self._controls.remove_button_pressed(self._button_token)
        self.remove_button_handler()
        self.clear_media()
        self._controls.is_enabled = False

    def remove_button_handler(self):
        if self._button_token is None:
            return
        self._controls.remove_button_pressed(self._button_token)
        self._button_token = None

    def _on_button_pressed(self, _sender, event_args):
        button = event_args.button
        buttons = self._button_type
        if button == buttons.PLAY:
            self.button_pressed.emit("play")
        elif button == buttons.PAUSE:
            self.button_pressed.emit("pause")
        elif button == buttons.STOP:
            self.button_pressed.emit("stop")
        elif button == buttons.NEXT:
            self.button_pressed.emit("next")
        elif button == buttons.PREVIOUS:
            self.button_pressed.emit("previous")
