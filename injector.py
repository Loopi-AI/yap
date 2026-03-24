import time
import pyperclip
import pyautogui


def inject_text(text: str):
    """Paste text into the currently focused text field via clipboard."""
    if not text:
        return

    # Save current clipboard
    try:
        original = pyperclip.paste()
    except Exception:
        original = ""

    try:
        # Add leading space so consecutive dictations don't run together
        pyperclip.copy(" " + text)
        time.sleep(0.05)

        # Paste into active field
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.15)  # Wait for paste to complete (some apps are slow)
    finally:
        # Restore original clipboard
        try:
            pyperclip.copy(original)
        except Exception:
            pass
