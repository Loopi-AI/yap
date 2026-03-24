import logging
import os
import glob

import numpy as np

# Register pip-installed NVIDIA DLL paths before importing CTranslate2/faster-whisper
_site_pkgs = os.path.join(os.path.dirname(os.__file__), "site-packages")
for _bin_dir in glob.glob(os.path.join(_site_pkgs, "nvidia", "*", "bin")):
    os.add_dll_directory(_bin_dir)

from faster_whisper import WhisperModel

log = logging.getLogger("Yap")


class Transcriber:
    def __init__(self, model_size: str = "base", device: str = "auto", language: str = "en"):
        self.model_size = model_size
        self.language = language
        self.model = None

        if device == "auto":
            self.device = self._detect_device()
        else:
            self.device = device
        self.compute_type = "float16" if self.device == "cuda" else "int8"

    @staticmethod
    def _detect_device() -> str:
        """Check if CUDA is actually usable (not just installed)."""
        import ctypes
        try:
            ctypes.cdll.LoadLibrary("cublas64_12.dll")
            return "cuda"
        except OSError:
            return "cpu"

    def load_model(self):
        """Load the Whisper model. Call on background thread — takes 2-5s."""
        log.info(f"Loading on device={self.device}, compute_type={self.compute_type}")
        self.model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe a numpy float32 audio array (16kHz mono). Returns text."""
        if self.model is None:
            return ""

        try:
            segments, info = self.model.transcribe(
                audio,
                language=self.language if self.language else None,
                beam_size=5,
                vad_filter=True,
            )

            result_segments = list(segments)

            text = " ".join(seg.text.strip() for seg in result_segments)
            return text.strip()
        except Exception as exc:
            log.error(f"Transcription error: {exc}")
            return ""
