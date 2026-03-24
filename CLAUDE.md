# Yap

Local speech-to-text dictation tool for Windows. Hold Ctrl+Win, speak, release — text appears wherever your cursor is.

## Setup Instructions

When someone opens this project in Claude Code and asks you to "set this up", "install this", or "get this running", follow every step below. Do not skip steps. Verify each step before moving on.

---

### Step 1: Verify Windows

This tool is **Windows-only**. If the user is on macOS or Linux, stop and tell them: "Yap currently only supports Windows. macOS support is planned for the future."

Check the OS:
```
python -c "import platform; print(platform.system())"
```
Expected output: `Windows`. If not, stop here.

---

### Step 2: Check Python

Yap requires **Python 3.11 or newer**.

Try these commands in order until one works:
```
python --version
```
```
python3 --version
```
```
py --version
```

**If none work (Python not installed):**
Tell the user:
> You need Python 3.11+ installed. Download it from https://www.python.org/downloads/
> **IMPORTANT:** During installation, check the box that says "Add Python to PATH" on the very first screen. Then restart your terminal and run this setup again.

**If the version is below 3.11:**
Tell the user to upgrade Python from the same link.

**Remember which python command worked** — use it for all subsequent commands. For example, if `py` worked, use `py` instead of `python` everywhere below.

---

### Step 3: Check pip

```
<python_command> -m pip --version
```

If pip is not found:
```
<python_command> -m ensurepip --upgrade
```

If that also fails, tell the user:
> pip is not available. Try reinstalling Python from https://www.python.org/downloads/ and make sure "Add Python to PATH" is checked.

---

### Step 4: Install dependencies

```
<python_command> -m pip install -r requirements.txt
```

**If this fails with a build error for any package:**
1. First retry with `--upgrade pip`: `<python_command> -m pip install --upgrade pip` then retry the install
2. If it still fails, the user may need Microsoft Visual C++ Build Tools. Tell them:
   > A package failed to build. Install "Microsoft C++ Build Tools" from https://visualstudio.microsoft.com/visual-cpp-build-tools/ — select "Desktop development with C++" during installation. Then restart your terminal and run this setup again.

**All packages that must install successfully:**
- faster-whisper (speech-to-text engine)
- sounddevice (audio capture)
- pynput (hotkey detection)
- pyautogui (fallback text injection)
- pyperclip (clipboard access)
- pystray (system tray icon)
- Pillow (image processing)
- PyYAML (config loading)
- numpy, scipy (audio processing)
- pygame-ce (sound effects)

---

### Step 5: Check for NVIDIA GPU (optional but recommended)

```
<python_command> -c "import ctypes; ctypes.WinDLL('nvcuda.dll'); print('NVIDIA GPU detected')"
```

**If NVIDIA GPU is detected**, install CUDA support for much faster transcription:
```
<python_command> -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```
If these fail to install, that's fine — Yap will fall back to CPU automatically.

**If no GPU detected**, skip this step. CPU mode works, just slower.

---

### Step 6: Verify microphone

```
<python_command> -c "import sounddevice; print(sounddevice.query_devices(kind='input'))"
```

This should print details about the default input device. If it errors with "No input device", tell the user:
> No microphone detected. Make sure a microphone is plugged in or your built-in mic is enabled in Windows Settings > System > Sound > Input.

---

### Step 7: Verify assets

Check that all required asset files exist:
```
ls assets/
```

Required files:
- `start.wav` — recording start sound effect
- `stop.wav` — recording stop sound effect
- `yap-tray.png` — system tray icon
- `yap.ico` — application icon

If any are missing, the app will crash on startup. Report which files are missing.

---

### Step 8: Run Yap

```
<python_command> main.py
```

**What should happen (tell the user):**
1. A small control window appears with an enable/disable toggle and language selector
2. A small dark pill-shaped overlay appears at the bottom-center of the screen
3. A purple speech bubble icon appears in the system tray (bottom-right, near the clock)
4. The tray tooltip says "Yap — Loading model..." while the AI model downloads for the first time
5. **FIRST RUN WILL BE SLOW** — the Whisper speech model (~500MB) downloads automatically. This can take 1-5 minutes depending on internet speed. Subsequent launches are instant.
6. Once the model loads, the tray tooltip changes to "Yap — English (hold Ctrl+Win)"
7. **To test:** Hold Ctrl+Win, say something, release. The text should appear wherever their cursor is.

**If the app crashes on startup, check `yap.log` in the project folder** for the error message and troubleshoot from there.

---

### Step 9: Create desktop shortcut (optional)

Ask the user: "Want me to create a desktop shortcut so you can launch Yap without opening a terminal?"

If yes:

1. Create `launch.vbs` in the Yap folder:
```vbs
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "FULL_PATH_TO_THIS_FOLDER"
WshShell.Run "<python_command_as_pythonw> main.py", 0, False
```
Replace `FULL_PATH_TO_THIS_FOLDER` with the actual absolute path to the Yap folder.
Replace `<python_command_as_pythonw>` with `pythonw` (or the full path to `pythonw.exe` if Python isn't on PATH). `pythonw` runs Python without a console window.

2. Create a Windows shortcut on the desktop pointing to `launch.vbs`, with the icon set to `assets\yap.ico`.

---

## Troubleshooting

### "No module named X"
A dependency wasn't installed. Run `<python_command> -m pip install -r requirements.txt` again.

### App starts but hotkey doesn't work
- Make sure no other app is capturing Ctrl+Win (some keyboard managers do this)
- Try running as administrator (right-click terminal → Run as administrator)

### Text doesn't appear after speaking
- Make sure the cursor is in a text field before releasing the hotkey
- Check `yap.log` for transcription errors
- If using CPU mode, transcription may take a few seconds — wait for the stop sound

### "No microphone detected"
- Check Windows Settings > System > Sound > Input
- Make sure the correct mic is set as default
- Some USB mics need drivers installed first

### Overlay doesn't show
- The overlay requires Windows 10 or 11
- If using multiple monitors, it appears on the primary monitor

### Model download hangs
- Check internet connection
- The model downloads from Hugging Face — if blocked by a corporate firewall, the user may need to use a different network

---

## How It Works

- **Hold Ctrl+Win** → recording starts (start sound plays, overlay expands with waveform)
- **Release** → recording stops (stop sound plays, text is transcribed and pasted)
- **System tray icon** → right-click for language switching, left-click for control window
- **Control window** → enable/disable, language selection, quit

## Config

`config.yaml` controls model size, language, hotkey, and device:
```yaml
model: small          # tiny, base, small, medium, large-v3
language: auto        # "auto" or a language code (en, de, da, etc.)
languages:            # enabled languages shown in the control window
  - en
hotkey: ctrl+windows
device: auto          # auto = GPU if available, else CPU
```

Smaller models (`tiny`, `base`) are faster but less accurate. `small` is the best balance.

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
| `config.yaml` | User config (model, language, device) |
