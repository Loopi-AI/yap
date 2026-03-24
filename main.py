import ctypes
import os
import sys
import queue
import socket
import threading
import logging
import pygame
import yaml
from PIL import Image, ImageDraw
from pystray import Icon, MenuItem, Menu

from transcriber import Transcriber
from recorder import Recorder
from hotkey import HotkeyListener
from injector import inject_text
from overlay import RecordingOverlay
from control_window import ControlWindow

# --- Set AppUserModelID so Windows shows Yap icon in taskbar (not Python) ---
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("loopiai.yap.1")

# --- Force dark mode for native menus (tray right-click) ---
try:
    _uxtheme = ctypes.WinDLL("uxtheme.dll")
    _uxtheme[135](1)   # SetPreferredAppMode(ForceDark)
    _uxtheme[136]()     # FlushMenuThemes
except Exception:
    pass

# --- Single-instance constants ---
LOCK_PORT = 47391  # arbitrary high port for single-instance lock
SIGNAL_PORT = 47392  # port to signal running instance to show window

# --- Logging: file + console (console only if terminal attached) ---
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "yap.log")

log_handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
try:
    # Only add console handler if a real console exists
    if sys.stdout and sys.stdout.writable():
        log_handlers.append(logging.StreamHandler())
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=log_handlers,
)
log = logging.getLogger("Yap")


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    script = os.path.abspath(sys.argv[0])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}"', None, 1)
    sys.exit(0)


def _config_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


def load_config() -> dict:
    path = _config_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(config: dict):
    with open(_config_path(), "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)



def make_dot_icon(color: str, size: int = 64) -> Image.Image:
    """Create a simple colored circle icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse([margin, margin, size - margin, size - margin], fill=color)
    return img


def acquire_single_instance():
    """Try to bind a socket to LOCK_PORT. If it fails, another instance is running."""
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    try:
        lock.bind(("127.0.0.1", LOCK_PORT))
        lock.listen(1)
        return lock
    except OSError:
        return None


def signal_existing_instance():
    """Tell the running instance to show its control window."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", SIGNAL_PORT))
        s.sendall(b"show")
        s.close()
    except Exception:
        pass


def listen_for_signals(control_window):
    """Background thread: accept connections on SIGNAL_PORT to show the window."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", SIGNAL_PORT))
    srv.listen(1)
    srv.settimeout(1.0)
    while True:
        try:
            conn, _ = srv.accept()
            data = conn.recv(64)
            conn.close()
            if data == b"show":
                control_window.toggle_visibility()
        except socket.timeout:
            continue
        except Exception:
            break


def main():
    # Single-instance check
    lock = acquire_single_instance()
    if lock is None:
        log.info("Yap already running — signaling existing instance.")
        signal_existing_instance()
        sys.exit(0)

    log.info("Yap starting...")

    config = load_config()
    model_size = config.get("model", "small")
    language = config.get("language", "en") or "en"
    device = config.get("device", "auto")

    # "auto" means Whisper auto-detects — pass None to transcriber
    transcriber = Transcriber(
        model_size=model_size, device=device,
        language=None if language == "auto" else language,
    )
    recorder = Recorder()
    audio_queue = queue.Queue()
    hotkey_listener = HotkeyListener(recorder, audio_queue)

    model_ready = threading.Event()
    running = threading.Event()
    running.set()

    # Recording overlay (connected to recorder for audio-reactive waveform)
    overlay = RecordingOverlay(recorder=recorder)

    # Language state
    enabled_languages = config.get("languages", ["en"])
    current_lang = [language]  # mutable container for closure — "auto" or a language code
    enabled = [True]  # mutable container for enable/disable toggle

    # Icons: pre-scaled tray PNG for crisp display, red dot for recording
    tray_png = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "yap-tray.png")
    icon_ready = Image.open(tray_png).convert("RGBA")
    icon_loading = icon_ready.copy()
    icon_recording = make_dot_icon("#ef4444")

    def make_title():
        if current_lang[0] == "auto":
            lang_name = "Auto"
        else:
            from control_window import ALL_LANGUAGES
            lang_name = ALL_LANGUAGES.get(current_lang[0], current_lang[0])
        state = "" if enabled[0] else " (paused)"
        return f"Yap — {lang_name}{state} (hold Ctrl+Win)"

    def set_language(lang):
        def action(icon, item):
            current_lang[0] = lang
            transcriber.language = None if lang == "auto" else lang
            control_window.update_state(language=lang)
            log.info(f"Language switched to {lang}")
            tray.title = make_title()
        return action

    def set_language_from_window(lang):
        current_lang[0] = lang
        transcriber.language = None if lang == "auto" else lang
        log.info(f"Language switched via window to {lang}")
        tray.title = make_title()
        # Save to config
        config["language"] = lang
        save_config(config)

    def on_languages_changed(languages):
        config["languages"] = languages
        save_config(config)
        # Rebuild tray menu with updated languages
        _rebuild_tray_menu()

    def toggle_enabled(is_enabled):
        enabled[0] = is_enabled
        if is_enabled:
            hotkey_listener.start()
            overlay.show_idle()
            log.info("Yap enabled")
        else:
            hotkey_listener.stop()
            overlay.hide_idle()
            log.info("Yap paused")
        tray.title = make_title()

    def is_lang(lang):
        def check(item):
            return current_lang[0] == lang
        return check

    _shutting_down = [False]

    def shutdown(icon=None):
        if _shutting_down[0]:
            return
        _shutting_down[0] = True
        log.info("Shutting down...")
        running.clear()
        try:
            hotkey_listener.stop()
        except Exception:
            pass
        try:
            recorder.stop_stream()
        except Exception:
            pass
        try:
            control_window.destroy()
        except Exception:
            pass
        try:
            overlay.destroy()
        except Exception:
            pass
        try:
            pygame.mixer.quit()
        except Exception:
            pass
        try:
            if icon:
                icon.stop()
            else:
                tray.stop()
        except Exception:
            pass
        # Force exit if something hangs
        os._exit(0)

    # Control window (runs on overlay's tkinter thread)
    control_window = ControlWindow(
        tk_root=overlay.tk_root,
        on_toggle=toggle_enabled,
        on_language_change=set_language_from_window,
        on_languages_changed=on_languages_changed,
        on_quit=shutdown,
        initial_enabled=True,
        initial_language=language,
        enabled_languages=enabled_languages,
    )

    # Listen for "show window" signals from second launches
    signal_thread = threading.Thread(target=listen_for_signals, args=(control_window,), daemon=True)
    signal_thread.start()

    # Show control window on startup
    control_window.toggle_visibility()

    def on_tray_click(icon, item):
        control_window.toggle_visibility()

    def _build_tray_menu():
        from control_window import ALL_LANGUAGES
        items = [MenuItem("Open Yap", on_tray_click, default=True), Menu.SEPARATOR]
        items.append(MenuItem("Auto", set_language("auto"), checked=is_lang("auto"), radio=True))
        for code in enabled_languages:
            name = ALL_LANGUAGES.get(code, code)
            items.append(MenuItem(name, set_language(code), checked=is_lang(code), radio=True))
        items.append(Menu.SEPARATOR)
        items.append(MenuItem("Quit", lambda icon, item: shutdown(icon)))
        return Menu(*items)

    def _rebuild_tray_menu():
        tray.menu = _build_tray_menu()

    tray = Icon(
        "Yap",
        icon_loading,
        "Yap — Loading model...",
        menu=_build_tray_menu(),
    )

    # Sound effects — pygame.mixer keeps the audio device open (no pop)
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
    sfx_start = pygame.mixer.Sound(os.path.join(assets_dir, "start.wav"))
    sfx_stop = pygame.mixer.Sound(os.path.join(assets_dir, "stop.wav"))
    # Play an inaudible tone on loop to keep the DAC awake (prevents pop on first real sound)
    _keepalive = pygame.mixer.Sound(buffer=bytes(2 * 4410))  # 100ms of silence, 16-bit mono
    _keepalive.set_volume(0.01)
    _keepalive.play(loops=-1)
    log.info("Sound effects loaded (pygame.mixer).")

    # Recording state callbacks — swap tray icon + overlay + sound
    def on_record_start():
        sfx_start.play()
        tray.icon = icon_recording
        tray.title = "Yap — Recording..."
        overlay.show()

    def on_record_stop():
        tray.icon = icon_ready
        tray.title = make_title()
        overlay.hide()
        sfx_stop.play()

    hotkey_listener.on_record_start = on_record_start
    hotkey_listener.on_record_stop = on_record_stop

    # Load model on background thread
    def load_model():
        log.info(f"Loading Whisper model '{model_size}' (language={'auto' if not language else language})...")
        transcriber.load_model()
        model_ready.set()
        log.info("Model loaded and ready.")
        tray.icon = icon_ready
        tray.title = make_title()

    model_thread = threading.Thread(target=load_model, daemon=True)
    model_thread.start()

    # Start audio stream
    try:
        recorder.start_stream()
        log.info("Audio stream started.")
    except Exception as exc:
        log.error(f"No microphone detected: {exc}")
        tray_err = Icon(
            "Yap", icon_loading, "Yap — No microphone detected",
            menu=Menu(MenuItem("Quit", lambda icon, item: icon.stop())),
        )
        tray_err.run(setup=lambda icon: icon.notify("No microphone detected.", "Yap"))
        return

    hotkey_listener.start()
    log.info("Hotkey listener active (Ctrl+Win).")

    # Transcription consumer
    def consume_queue():
        while running.is_set():
            try:
                audio = audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if not model_ready.is_set():
                log.warning("Model not ready yet, skipping.")
                continue

            log.info("Transcribing...")
            text = transcriber.transcribe(audio)
            if text:
                log.info(f"Transcribed: {text}")
                inject_text(text)
            else:
                log.info("No speech detected.")

    consumer_thread = threading.Thread(target=consume_queue, daemon=True)
    consumer_thread.start()

    log.info("System tray active. Hold Ctrl+Win to dictate.")
    tray.run()


if __name__ == "__main__":
    main()
