import queue
import logging
from pynput import keyboard
from recorder import Recorder

log = logging.getLogger("Yap")


class HotkeyListener:
    def __init__(self, recorder: Recorder, audio_queue: queue.Queue):
        self.recorder = recorder
        self.audio_queue = audio_queue
        self._recording = False
        self._pressed_keys = set()
        self._listener = None
        self.on_record_start = None  # callback
        self.on_record_stop = None   # callback

    def start(self):
        """Start the pynput keyboard listener on its own thread."""
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        log.info("pynput keyboard listener started.")

    def _on_press(self, key):
        """Track pressed keys. Start recording when Ctrl+Win are both held."""
        self._pressed_keys.add(key)

        # Check if Ctrl + Win are both held
        ctrl_held = any(
            k in self._pressed_keys
            for k in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.ctrl)
        )
        win_held = any(
            k in self._pressed_keys
            for k in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r)
        )

        if ctrl_held and win_held and not self._recording:
            self._recording = True
            log.info("Recording started (Ctrl+Win held).")
            self.recorder.start_recording()
            if self.on_record_start:
                self.on_record_start()

    def _on_release(self, key):
        """Stop recording when either Ctrl or Win is released."""
        self._pressed_keys.discard(key)

        if self._recording:
            # Check if Ctrl or Win was released
            is_ctrl = key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.ctrl)
            is_win = key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r)

            if is_ctrl or is_win:
                self._recording = False
                log.info(f"Recording stopped ({'Ctrl' if is_ctrl else 'Win'} released).")
                if self.on_record_stop:
                    self.on_record_stop()
                audio = self.recorder.stop_recording()
                if audio is not None:
                    self.audio_queue.put(audio)

    def stop(self):
        """Stop the keyboard listener."""
        if self._listener:
            self._listener.stop()
            self._listener = None
