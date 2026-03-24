import threading
import logging
import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly
from math import gcd

WHISPER_SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 1024

log = logging.getLogger("Yap")


class Recorder:
    def __init__(self):
        self.recording_event = threading.Event()
        self._buffer: list[np.ndarray] = []
        self._stream = None
        self._device_rate = None
        self.audio_level = 0.0  # RMS level (0.0–1.0), updated every block

    def start_stream(self):
        """Start the audio input stream at the device's native sample rate.
        Resamples to 16kHz for Whisper on stop_recording()."""
        device_info = sd.query_devices(kind="input")
        self._device_rate = int(device_info["default_samplerate"])
        log.info(f"Using mic: {device_info['name']} at {self._device_rate}Hz")

        self._stream = sd.InputStream(
            samplerate=self._device_rate,
            channels=CHANNELS,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop_stream(self):
        """Stop and close the audio stream."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def _audio_callback(self, indata, frames, time_info, status):
        """sounddevice callback. Appends audio to buffer only while recording."""
        if self.recording_event.is_set():
            self._buffer.append(indata.copy())
            # Expose RMS level for waveform visualization (clamped 0–1)
            rms = float(np.sqrt(np.mean(indata ** 2)))
            self.audio_level = min(rms * 5.0, 1.0)  # amplify for visual range

    def start_recording(self):
        """Begin buffering audio."""
        self._buffer = []
        self.recording_event.set()

    def stop_recording(self) -> np.ndarray | None:
        """Stop buffering and return the recorded audio resampled to 16kHz mono.
        Returns None if recording was too short (< 0.3s)."""
        self.recording_event.clear()

        if not self._buffer:
            return None

        audio = np.concatenate(self._buffer, axis=0).flatten()
        duration = len(audio) / self._device_rate

        if duration < 0.3:
            return None

        # Resample to 16kHz if needed (proper anti-aliased resampling)
        if self._device_rate != WHISPER_SAMPLE_RATE:
            g = gcd(self._device_rate, WHISPER_SAMPLE_RATE)
            up = WHISPER_SAMPLE_RATE // g
            down = self._device_rate // g
            audio = resample_poly(audio, up, down).astype(np.float32)
            log.info(f"Resampled from {self._device_rate}Hz to {WHISPER_SAMPLE_RATE}Hz ({duration:.1f}s)")

        return audio
