# Yap — Free Speech to Text for Windows

<p align="center">
  <img src="assets/Yap Logo.png" width="128" alt="Yap logo">
</p>

Hold **Ctrl+Win**, speak, release — text appears wherever your cursor is. Works in any app.

Like [Whispr Flow](https://whisprflow.com), but free and open source. Runs 100% locally — no cloud, no subscription, no data leaves your machine.

## Features

- **Hold-to-talk dictation** — Ctrl+Win hotkey, works in any text field
- **GPU-accelerated** — near-instant transcription on NVIDIA GPUs (CPU works too)
- **60+ languages** — auto-detect or pick from the control window
- **Minimal UI** — small animated pill overlay + system tray icon
- **No admin required** — runs without elevation

## Install

### Using Claude Code / Antigravity

Open this project folder and tell Claude:

> Set this up and run it

Claude will read the `CLAUDE.md` and handle everything.

### Manual

1. Install [Python 3.11+](https://www.python.org/downloads/) (check "Add to PATH")
2. Clone this repo:
   ```
   git clone https://github.com/Loopi-AI/yap.git
   cd yap
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. (Optional) For GPU acceleration with an NVIDIA card:
   ```
   pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
   ```
5. Run:
   ```
   python main.py
   ```

## Usage

| Action | What happens |
|---|---|
| **Hold Ctrl+Win** | Recording starts — pill expands, waveform animates |
| **Release** | Text is transcribed and pasted at your cursor |
| **Left-click tray icon** | Open control window |
| **Right-click tray icon** | Quick language switch |

## Config

Edit `config.yaml` to change model size, language, or device:

```yaml
model: small          # tiny, base, small, medium, large-v3
language: auto        # "auto" or a language code
device: auto          # auto = GPU if available, else CPU
```

Smaller models (`tiny`, `base`) are faster but less accurate. `small` is the best balance for most people.

## Requirements

- Windows 10/11
- Python 3.11+
- A microphone
- (Optional) NVIDIA GPU with CUDA for fast transcription

## License

MIT — do whatever you want with it.
