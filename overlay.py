"""Pill overlay with smooth expand animation on recording + voice-message waveform."""

import ctypes
import ctypes.wintypes
import threading
import tkinter as tk
import logging
import random

log = logging.getLogger("Yap")

# Size — idle is a small subtle pill, recording expands both width and height
IDLE_W = 47
IDLE_H = 11
PILL_W = 65
PILL_H = 18
NUM_BARS = 9
BAR_GAP = 2
CORNER_RADIUS = 12

# Animation
EXPAND_SPEED = 0.18
ANIM_INTERVAL = 16    # ms (~60fps)

# Colors
BG = "#000000"
BG_REC = "#0a0a0a"
BAR_COLOR_IDLE = "#2a2040"
BAR_COLOR = "#a78bfa"
BAR_ACTIVE = "#c4b5fd"
BAR_PEAK = "#d8b4fe"


class RecordingOverlay:
    """Pill that expands from a subtle idle sliver to voice-message waveform on recording."""

    def __init__(self, recorder=None):
        self._recorder = recorder
        self._root = None
        self._canvas = None
        self._pill_id = None
        self._bar_ids = []
        self._bar_heights = [0.0] * NUM_BARS
        self._target_heights = [0.0] * NUM_BARS
        self._wave_job = None
        self._size_job = None
        self._thread = None
        self._ready = threading.Event()
        self._recording = False
        self._screen_w = 0
        self._screen_h = 0
        self._monitor_job = None
        self._last_monitor_rect = None
        self._current_w = float(IDLE_W)
        self._current_h = float(IDLE_H)
        self._target_w = float(IDLE_W)
        self._target_h = float(IDLE_H)
        self._start()

    # --- public API (thread-safe) ---

    @property
    def tk_root(self):
        self._ready.wait(timeout=5)
        return self._root

    def show(self):
        self._ready.wait(timeout=3)
        if self._root:
            self._root.after(0, self._reposition_to_active_monitor)
            self._root.after(0, self._do_start_recording)

    def hide(self):
        self._ready.wait(timeout=3)
        if self._root:
            self._root.after(0, self._do_stop_recording)

    def show_idle(self):
        self._ready.wait(timeout=3)
        if self._root:
            self._root.after(0, lambda: self._root.deiconify())

    def hide_idle(self):
        self._ready.wait(timeout=3)
        if self._root:
            self._root.after(0, lambda: self._root.withdraw())

    def destroy(self):
        if self._root:
            self._root.after(0, self._do_destroy)

    # --- multi-monitor ---

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.wintypes.DWORD),
            ("rcMonitor", ctypes.wintypes.RECT),
            ("rcWork", ctypes.wintypes.RECT),
            ("dwFlags", ctypes.wintypes.DWORD),
        ]

    _MonitorFromPoint = ctypes.windll.user32.MonitorFromPoint
    _MonitorFromPoint.argtypes = [ctypes.wintypes.POINT, ctypes.wintypes.DWORD]
    _MonitorFromPoint.restype = ctypes.c_void_p

    _GetMonitorInfoW = ctypes.windll.user32.GetMonitorInfoW
    _GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MONITORINFO)]
    _GetMonitorInfoW.restype = ctypes.wintypes.BOOL

    def _get_active_monitor_rect(self):
        try:
            pt = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            MONITOR_DEFAULTTONEAREST = 2
            hmon = self._MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
            mi = self._MONITORINFO()
            mi.cbSize = ctypes.sizeof(self._MONITORINFO)
            self._GetMonitorInfoW(hmon, ctypes.byref(mi))
            rc = mi.rcWork
            return rc.left, rc.top, rc.right, rc.bottom
        except Exception:
            return 0, 0, self._screen_w, self._screen_h

    def _reposition_to_active_monitor(self):
        left, top, right, bottom = self._get_active_monitor_rect()
        mon_w = right - left
        x = left + (mon_w - PILL_W) // 2
        y = bottom - PILL_H - 10
        self._root.geometry(f"{PILL_W}x{PILL_H}+{x}+{y}")

    def _get_foreground_monitor_rect(self):
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                MONITOR_DEFAULTTONEAREST = 2
                hmon = ctypes.windll.user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
                mi = self._MONITORINFO()
                mi.cbSize = ctypes.sizeof(self._MONITORINFO)
                self._GetMonitorInfoW(hmon, ctypes.byref(mi))
                rc = mi.rcWork
                return rc.left, rc.top, rc.right, rc.bottom
        except Exception:
            pass
        return self._get_active_monitor_rect()

    def _poll_monitor(self):
        rect = self._get_foreground_monitor_rect()
        if rect != self._last_monitor_rect:
            self._last_monitor_rect = rect
            self._reposition_to_active_monitor()
        self._monitor_job = self._root.after(500, self._poll_monitor)

    # --- internal ---

    def _start(self):
        self._thread = threading.Thread(target=self._run_tk, daemon=True)
        self._thread.start()

    def _run_tk(self):
        self._root = tk.Tk()
        self._root.title("")
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.90)

        trans = "#010101"
        self._root.configure(bg=trans)
        self._root.attributes("-transparentcolor", trans)

        self._screen_w = self._root.winfo_screenwidth()
        self._screen_h = self._root.winfo_screenheight()

        self._reposition_to_active_monitor()

        self._canvas = tk.Canvas(
            self._root, width=PILL_W, height=PILL_H,
            bg=trans, highlightthickness=0,
        )
        self._canvas.pack()

        # Main pill (no border — tkinter can't anti-alias small polygons)
        self._pill_id = self._rounded_rect(
            0, 0, IDLE_W, IDLE_H,
            radius=CORNER_RADIUS, fill=BG, outline="",
        )

        mid = PILL_H / 2
        for i in range(NUM_BARS):
            bid = self._canvas.create_rectangle(
                0, mid, 1, mid, fill=BAR_COLOR_IDLE, outline="",
            )
            self._bar_ids.append(bid)

        self._current_w = float(IDLE_W)
        self._current_h = float(IDLE_H)
        self._target_w = float(IDLE_W)
        self._target_h = float(IDLE_H)
        self._layout(IDLE_W, IDLE_H)

        self._recording = False
        self._ready.set()
        self._set_wave_idle()
        self._poll_monitor()
        log.info("Overlay initialized (voice-message waveform).")
        self._root.mainloop()

    @staticmethod
    def _pill_points(x1, y1, x2, y2, r):
        """Generate points for a pill/rounded-rect using arc segments."""
        import math
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
        pts = []
        # Number of points per quarter-circle arc
        n = 12
        # Top-right arc
        for i in range(n + 1):
            a = -math.pi / 2 + (math.pi / 2) * i / n
            pts.append(x2 - r + r * math.cos(a))
            pts.append(y1 + r + r * math.sin(a))
        # Bottom-right arc
        for i in range(n + 1):
            a = 0 + (math.pi / 2) * i / n
            pts.append(x2 - r + r * math.cos(a))
            pts.append(y2 - r + r * math.sin(a))
        # Bottom-left arc
        for i in range(n + 1):
            a = math.pi / 2 + (math.pi / 2) * i / n
            pts.append(x1 + r + r * math.cos(a))
            pts.append(y2 - r + r * math.sin(a))
        # Top-left arc
        for i in range(n + 1):
            a = math.pi + (math.pi / 2) * i / n
            pts.append(x1 + r + r * math.cos(a))
            pts.append(y1 + r + r * math.sin(a))
        return pts

    def _rounded_rect(self, x1, y1, x2, y2, radius=10, **kwargs):
        pts = self._pill_points(x1, y1, x2, y2, radius)
        return self._canvas.create_polygon(pts, smooth=False, **kwargs)

    def _update_pill_shape(self, w, h):
        ox = (PILL_W - w) / 2
        oy = (PILL_H - h) / 2
        pts = self._pill_points(ox, oy, ox + w, oy + h, CORNER_RADIUS)
        self._canvas.coords(self._pill_id, *pts)

    def _layout(self, w, h):
        self._update_pill_shape(w, h)

        ox = (PILL_W - w) / 2
        pad = 6
        wave_left = ox + pad
        wave_right = ox + w - pad
        wave_width = max(wave_right - wave_left, 1)
        single_w = max((wave_width - (NUM_BARS - 1) * BAR_GAP) / NUM_BARS, 1)
        total_w = NUM_BARS * single_w + (NUM_BARS - 1) * BAR_GAP
        sx = wave_left + (wave_width - total_w) / 2

        mid = PILL_H / 2
        for i in range(NUM_BARS):
            bx = sx + i * (single_w + BAR_GAP)
            coords = self._canvas.coords(self._bar_ids[i])
            if len(coords) == 4:
                old_top, old_bot = coords[1], coords[3]
            else:
                old_top, old_bot = mid, mid
            self._canvas.coords(self._bar_ids[i], bx, old_top, bx + single_w, old_bot)

    # --- smooth size animation ---

    def _start_size_anim(self):
        if self._size_job is None:
            self._animate_size()

    def _animate_size(self):
        dw = self._target_w - self._current_w
        dh = self._target_h - self._current_h
        if abs(dw) < 0.5 and abs(dh) < 0.5:
            self._current_w = self._target_w
            self._current_h = self._target_h
            self._layout(self._current_w, self._current_h)
            self._size_job = None
            return

        self._current_w += dw * EXPAND_SPEED
        self._current_h += dh * EXPAND_SPEED
        self._layout(self._current_w, self._current_h)
        self._size_job = self._root.after(ANIM_INTERVAL, self._animate_size)

    # --- state ---

    def _do_start_recording(self):
        self._recording = True
        self._bar_heights = [0.0] * NUM_BARS
        self._canvas.itemconfig(self._pill_id, fill=BG_REC)
        self._target_w = float(PILL_W)
        self._target_h = float(PILL_H)
        self._start_size_anim()
        if self._wave_job:
            self._root.after_cancel(self._wave_job)
        self._animate_wave_recording()

    def _do_stop_recording(self):
        self._recording = False
        self._canvas.itemconfig(self._pill_id, fill=BG)
        self._target_w = float(IDLE_W)
        self._target_h = float(IDLE_H)
        self._start_size_anim()
        if self._wave_job:
            self._root.after_cancel(self._wave_job)
            self._wave_job = None
        self._set_wave_idle()

    def _do_destroy(self):
        if self._wave_job:
            self._root.after_cancel(self._wave_job)
        if self._size_job:
            self._root.after_cancel(self._size_job)
        if self._monitor_job:
            self._root.after_cancel(self._monitor_job)
        self._root.destroy()

    # --- waveform ---

    def _bar_layout_for_w(self, w):
        offset = (PILL_W - w) / 2
        pad = 6
        wave_left = offset + pad
        wave_right = offset + w - pad
        wave_width = max(wave_right - wave_left, 1)
        single_w = max((wave_width - (NUM_BARS - 1) * BAR_GAP) / NUM_BARS, 1)
        total_w = NUM_BARS * single_w + (NUM_BARS - 1) * BAR_GAP
        sx = wave_left + (wave_width - total_w) / 2
        return single_w, sx

    def _set_wave_idle(self):
        """Hide bars in idle."""
        mid = PILL_H / 2
        for i in range(NUM_BARS):
            self._canvas.coords(self._bar_ids[i], 0, mid, 0, mid)
            self._canvas.itemconfig(self._bar_ids[i], fill=BAR_COLOR_IDLE)
        self._wave_job = None

    def _animate_wave_recording(self):
        if not self._recording:
            return

        level = 0.0
        if self._recorder:
            level = min(self._recorder.audio_level * 5.0, 1.0)

        max_bar_h = (self._current_h - 2) / 2

        # Voice icon shape: fixed height pattern like the reference image
        # Short-medium-tall-tall-TALLEST-tall-tall-medium-short
        # Each bar's base shape is fixed; audio level scales the whole thing
        shape = [0.15, 0.3, 0.65, 0.9, 1.0, 0.9, 0.65, 0.3, 0.15]
        for i in range(NUM_BARS):
            base = shape[i] if i < len(shape) else 0.3
            # Audio drives overall height, with slight per-bar jitter
            jitter = random.uniform(0.9, 1.1)
            target = base * level * jitter
            # Minimum height so bars are always visible during recording
            idle_min = base * 0.2
            self._target_heights[i] = max(target, idle_min)

        single_w, sx = self._bar_layout_for_w(self._current_w)
        mid = PILL_H / 2

        for i in range(NUM_BARS):
            diff = self._target_heights[i] - self._bar_heights[i]
            speed = 0.45 if diff > 0 else 0.15
            self._bar_heights[i] += diff * speed

            h = self._bar_heights[i] * max_bar_h
            h = max(h, 0.5)

            bx = sx + i * (single_w + BAR_GAP)
            self._canvas.coords(self._bar_ids[i], bx, mid - h, bx + single_w, mid + h)

            if self._bar_heights[i] > 0.7:
                self._canvas.itemconfig(self._bar_ids[i], fill=BAR_PEAK)
            elif self._bar_heights[i] > 0.3:
                self._canvas.itemconfig(self._bar_ids[i], fill=BAR_ACTIVE)
            else:
                self._canvas.itemconfig(self._bar_ids[i], fill=BAR_COLOR)

        self._wave_job = self._root.after(33, self._animate_wave_recording)
