# Yap

Local speech-to-text dictation tool for Windows. Hold Ctrl+Win, speak, release — text appears wherever your cursor is.

## Setup Instructions

When someone opens this project in Claude Code and asks you to "set this up", "install this", or "get this running", follow these steps:

### 1. Check Python
Yap requires Python 3.11+. Check if Python is installed:
```
python --version
```
If not installed, guide the user to install Python from https://www.python.org/downloads/ (make sure "Add to PATH" is checked during install).

### 2. Install dependencies
```
pip install -r requirements.txt
```

If the user has an NVIDIA GPU, also install CUDA support for faster transcription:
```
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```
This is optional — Yap works on CPU too, just slower.

### 3. Run Yap
```
python main.py
```
No admin required. A purple speech bubble appears in the system tray and a small black pill overlay shows at the bottom of the screen.

### 4. Create a desktop shortcut (optional)
Create a VBS launcher to start Yap without a console window:
```vbs
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "FULL_PATH_TO_YAP_FOLDER"
WshShell.Run "pythonw main.py", 0, False
```
Save as `launch.vbs` in the Yap folder. Then create a Windows shortcut (.lnk) on the desktop pointing to `launch.vbs`, with the icon set to `assets/yap.ico`.

## How It Works

- **Hold Ctrl+Win** → recording starts (start sound plays, overlay expands with waveform)
- **Release** → recording stops (stop sound plays, text is transcribed and pasted)
- **System tray icon** → right-click for language switching, left-click for control window
- **Control window** → enable/disable, language selection (Auto + dropdown), quit

## Tech Stack

- Python 3.11+, faster-whisper (Whisper speech-to-text)
- CUDA auto-detection (GPU if available, CPU fallback)
- sounddevice (audio capture), pynput (hotkeys), pyautogui + pyperclip (text injection)
- tkinter (overlay + control window), pystray (system tray), pygame-ce (sound effects)

## Config

`config.yaml` controls model size, language, hotkey, and device:
```yaml
model: small          # tiny, base, small, medium, large-v3
language: auto        # "auto" or a language code (en, da, de, etc.)
languages:            # enabled languages in the control window
  - en
  - da
hotkey: ctrl+windows
device: auto          # auto = GPU if available, else CPU
```

## Files

| File | Purpose |
|---|---|
| `main.py` | Entry point, tray, control window, sound effects, config |
| `control_window.py` | Settings panel (toggle, language dropdown/picker, quit) |
| `overlay.py` | Animated waveform pill overlay |
| `recorder.py` | Audio capture + resampling to 16kHz |
| `transcriber.py` | Whisper model loading + transcription |
| `hotkey.py` | Ctrl+Win hotkey detection |
| `injector.py` | Clipboard-based text paste |
