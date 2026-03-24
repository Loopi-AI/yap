"""Yap control window — dark purple-themed settings panel."""

import os
import tkinter as tk
import logging

from PIL import Image, ImageTk

log = logging.getLogger("Yap")

# Colors matching the logo
BG = "#0f0f14"
BG_CARD = "#1a1a24"
BORDER = "#2a2a3a"
PURPLE = "#a78bfa"
PURPLE_LIGHT = "#c4b5fd"
PURPLE_DIM = "#6d5aad"
TEXT = "#e0e0e8"
TEXT_DIM = "#888899"
GREEN = "#4ade80"
RED = "#ef4444"
HOVER_BG = "#252535"

# All languages supported by Whisper
ALL_LANGUAGES = {
    "af": "Afrikaans", "ar": "Arabic", "bg": "Bulgarian", "bn": "Bengali",
    "bs": "Bosnian", "ca": "Catalan", "cs": "Czech", "cy": "Welsh",
    "da": "Dansk", "de": "Deutsch", "el": "Greek", "en": "English",
    "es": "Español", "et": "Estonian", "fa": "Persian", "fi": "Finnish",
    "fr": "Français", "gl": "Galician", "gu": "Gujarati", "he": "Hebrew",
    "hi": "Hindi", "hr": "Croatian", "hu": "Hungarian", "id": "Indonesian",
    "is": "Icelandic", "it": "Italiano", "ja": "Japanese", "ka": "Georgian",
    "kk": "Kazakh", "km": "Khmer", "kn": "Kannada", "ko": "Korean",
    "la": "Latin", "lt": "Lithuanian", "lv": "Latvian", "mk": "Macedonian",
    "ml": "Malayalam", "mn": "Mongolian", "mr": "Marathi", "ms": "Malay",
    "mt": "Maltese", "my": "Myanmar", "ne": "Nepali", "nl": "Dutch",
    "nn": "Nynorsk", "no": "Norwegian", "pa": "Punjabi", "pl": "Polish",
    "pt": "Português", "ro": "Romanian", "ru": "Russian", "si": "Sinhala",
    "sk": "Slovak", "sl": "Slovenian", "sq": "Albanian", "sr": "Serbian",
    "sv": "Svenska", "sw": "Swahili", "ta": "Tamil", "te": "Telugu",
    "tg": "Tajik", "th": "Thai", "tl": "Filipino", "tr": "Turkish",
    "uk": "Ukrainian", "ur": "Urdu", "uz": "Uzbek", "vi": "Vietnamese",
    "yo": "Yoruba", "zh": "Chinese",
}

WIN_W = 320
WIN_H = 440
TITLEBAR_H = 32
TITLEBAR_BG = "#000000"


class ControlWindow:
    """Dark-themed control panel for Yap. Runs on the overlay's tkinter thread."""

    def __init__(self, tk_root, on_toggle=None, on_language_change=None, on_quit=None,
                 on_languages_changed=None, initial_enabled=True, initial_language="en",
                 enabled_languages=None):
        self._tk_root = tk_root  # overlay's tk.Tk — used to schedule on its thread
        self._on_toggle = on_toggle
        self._on_language_change = on_language_change
        self._on_quit = on_quit
        self._on_languages_changed = on_languages_changed  # called when language list changes
        self._enabled = initial_enabled
        self._language = initial_language
        self._enabled_languages = list(enabled_languages or ["en", "da"])
        self._win = None
        self._visible = False
        self._toggle_btn = None
        self._status_dot = None
        self._status_text = None
        self._lang_buttons = {}
        self._lang_btns_frame = None
        self._logo_photo = None
        self._icon_photo = None
        self._picker_win = None
        self._dropdown_btn = None
        self._dropdown_frame = None
        self._dropdown_visible = False

    def toggle_visibility(self):
        """Show or hide the window. Thread-safe."""
        self._tk_root.after(0, self._do_toggle)

    def update_state(self, enabled=None, language=None):
        """Update displayed state from outside. Thread-safe."""
        self._tk_root.after(0, lambda: self._do_update(enabled, language))

    def destroy(self):
        if self._tk_root:
            self._tk_root.after(0, self._do_destroy)

    # --- internal (must run on tk thread) ---

    def _do_toggle(self):
        if self._win is None:
            self._create()
        elif self._visible:
            self._win.withdraw()
            self._visible = False
        else:
            self._win.deiconify()
            self._win.lift()
            self._win.focus_force()
            self._visible = True

    def _do_update(self, enabled, language):
        if enabled is not None:
            self._enabled = enabled
            self._refresh_toggle()
        if language is not None:
            self._language = language
            self._refresh_lang()

    def _do_destroy(self):
        if self._win:
            self._win.destroy()
            self._win = None
            self._visible = False

    def _create(self):
        self._win = tk.Toplevel(self._tk_root)
        self._win.title("Yap")
        self._win.overrideredirect(True)
        self._win.configure(bg=BG)
        self._win.attributes("-topmost", True)
        self._win.attributes("-alpha", 1.0)

        # Center on screen
        self._win.update_idletasks()
        x = (self._win.winfo_screenwidth() - WIN_W) // 2
        y = (self._win.winfo_screenheight() - WIN_H) // 2
        self._win.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

        # --- Custom title bar ---
        self._build_titlebar()

        self._build_ui()
        self._visible = True

    def _build_titlebar(self):
        tb = tk.Frame(self._win, bg=TITLEBAR_BG, height=TITLEBAR_H)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        # Drag support
        self._drag_x = 0
        self._drag_y = 0
        tb.bind("<Button-1>", self._on_drag_start)
        tb.bind("<B1-Motion>", self._on_drag_motion)

        # Title label
        title_lbl = tk.Label(tb, text="  Yap", font=("Segoe UI", 10),
                             fg=TEXT_DIM, bg=TITLEBAR_BG, anchor="w")
        title_lbl.pack(side="left", padx=(4, 0))
        title_lbl.bind("<Button-1>", self._on_drag_start)
        title_lbl.bind("<B1-Motion>", self._on_drag_motion)

        # Close button
        close_btn = tk.Label(tb, text=" \u2715 ", font=("Segoe UI", 11),
                             fg=TEXT_DIM, bg=TITLEBAR_BG, cursor="hand2")
        close_btn.pack(side="right", padx=(0, 4))
        close_btn.bind("<Button-1>", lambda e: self._on_close())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=RED, bg="#2a1515"))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=TEXT_DIM, bg=TITLEBAR_BG))

        # Minimize button (no maximize — just min + close)
        min_btn = tk.Label(tb, text=" \u2500 ", font=("Segoe UI", 11),
                           fg=TEXT_DIM, bg=TITLEBAR_BG, cursor="hand2")
        min_btn.pack(side="right")
        min_btn.bind("<Button-1>", lambda e: self._on_minimize())
        min_btn.bind("<Enter>", lambda e: min_btn.configure(bg="#1a1a24"))
        min_btn.bind("<Leave>", lambda e: min_btn.configure(bg=TITLEBAR_BG))

    def _on_drag_start(self, event):
        self._drag_x = event.x_root - self._win.winfo_x()
        self._drag_y = event.y_root - self._win.winfo_y()

    def _on_drag_motion(self, event):
        self._win.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _on_minimize(self):
        self._win.withdraw()
        self._visible = False

    def _build_ui(self):
        root = self._win

        # --- Logo ---
        logo_frame = tk.Frame(root, bg=BG)
        logo_frame.pack(pady=(28, 0))

        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "YAP-logo.png")
        if os.path.exists(logo_path):
            img = Image.open(logo_path).convert("RGBA")
            bbox = img.getbbox()
            if bbox:
                img = img.crop(bbox)
            img = img.resize((72, 72), Image.LANCZOS)
            self._logo_photo = ImageTk.PhotoImage(img)
            logo_label = tk.Label(logo_frame, image=self._logo_photo, bg=BG)
            logo_label.pack()

        # App name
        tk.Label(root, text="Yap", font=("Segoe UI", 20, "bold"),
                 fg=TEXT, bg=BG).pack(pady=(8, 0))
        tk.Label(root, text="Speech to Text", font=("Segoe UI", 10),
                 fg=TEXT_DIM, bg=BG).pack(pady=(0, 20))

        # --- Toggle Card ---
        toggle_card = tk.Frame(root, bg=BG_CARD, highlightbackground=BORDER,
                               highlightthickness=1, padx=16, pady=12)
        toggle_card.pack(padx=20, fill="x")

        toggle_top = tk.Frame(toggle_card, bg=BG_CARD)
        toggle_top.pack(fill="x")

        status_frame = tk.Frame(toggle_top, bg=BG_CARD)
        status_frame.pack(side="left")

        self._status_dot = tk.Canvas(status_frame, width=10, height=10,
                                      bg=BG_CARD, highlightthickness=0)
        self._status_dot.pack(side="left", padx=(0, 6))

        self._status_text = tk.Label(status_frame, font=("Segoe UI", 11),
                                      bg=BG_CARD)
        self._status_text.pack(side="left")

        self._toggle_btn = tk.Label(
            toggle_top, font=("Segoe UI", 10, "bold"),
            padx=14, pady=4, cursor="hand2",
        )
        self._toggle_btn.pack(side="right")
        self._toggle_btn.bind("<Button-1>", self._on_toggle_click)

        tk.Label(toggle_card, text="Hold  Ctrl + Win  to dictate",
                 font=("Segoe UI", 9), fg=TEXT_DIM, bg=BG_CARD).pack(pady=(8, 0))

        self._refresh_toggle()

        # --- Language Card ---
        lang_card = tk.Frame(root, bg=BG_CARD, highlightbackground=BORDER,
                             highlightthickness=1, padx=16, pady=12)
        lang_card.pack(padx=20, fill="x", pady=(12, 0))

        tk.Label(lang_card, text="Language", font=("Segoe UI", 11, "bold"),
                 fg=TEXT, bg=BG_CARD).pack(anchor="w")

        self._lang_btns_frame = tk.Frame(lang_card, bg=BG_CARD)
        self._lang_btns_frame.pack(fill="x", pady=(8, 0))

        self._rebuild_lang_buttons()

        # --- Quit ---
        quit_btn = tk.Label(
            root, text="Quit Yap", font=("Segoe UI", 10),
            fg=RED, bg=BG, cursor="hand2", padx=12, pady=6,
        )
        quit_btn.pack(side="bottom", pady=(0, 20))
        quit_btn.bind("<Button-1>", self._on_quit_click)
        quit_btn.bind("<Enter>", lambda e: quit_btn.configure(fg="#ff6b6b"))
        quit_btn.bind("<Leave>", lambda e: quit_btn.configure(fg=RED))

    def _refresh_toggle(self):
        if self._toggle_btn is None:
            return
        if self._enabled:
            self._toggle_btn.configure(text="Enabled", bg=PURPLE, fg="#ffffff")
            self._status_text.configure(text="Listening", fg=GREEN)
            self._status_dot.delete("all")
            self._status_dot.create_oval(1, 1, 9, 9, fill=GREEN, outline="")
        else:
            self._toggle_btn.configure(text="Disabled", bg="#333344", fg=TEXT_DIM)
            self._status_text.configure(text="Paused", fg=TEXT_DIM)
            self._status_dot.delete("all")
            self._status_dot.create_oval(1, 1, 9, 9, fill=TEXT_DIM, outline="")

    def _rebuild_lang_buttons(self):
        """Rebuild the language row: Auto on left, dropdown on right."""
        for w in self._lang_btns_frame.winfo_children():
            w.destroy()
        self._lang_buttons.clear()
        self._dropdown_frame = None
        self._dropdown_visible = False

        row = tk.Frame(self._lang_btns_frame, bg=BG_CARD)
        row.pack(fill="x", anchor="w")

        # Auto button (left)
        auto_btn = tk.Label(
            row, text="  Auto  ", font=("Segoe UI", 10),
            padx=10, pady=5, cursor="hand2",
        )
        auto_btn.pack(side="left")
        auto_btn.bind("<Button-1>", lambda e: self._on_lang_click("auto"))
        self._lang_buttons["auto"] = auto_btn

        # Dropdown button (right) — shows current language name + arrow
        self._dropdown_btn = tk.Label(
            row, font=("Segoe UI", 10),
            padx=10, pady=5, cursor="hand2",
            bg="#252535", fg=TEXT_DIM,
            highlightbackground=BORDER, highlightthickness=1,
        )
        self._dropdown_btn.pack(side="right")
        self._dropdown_btn.bind("<Button-1>", lambda e: self._toggle_dropdown())
        self._update_dropdown_label()

        self._refresh_lang()

    def _update_dropdown_label(self):
        """Update dropdown button text to show current specific language."""
        if self._language == "auto":
            # Show first enabled language as hint
            if self._enabled_languages:
                name = ALL_LANGUAGES.get(self._enabled_languages[0], self._enabled_languages[0])
            else:
                name = "Select"
        else:
            name = ALL_LANGUAGES.get(self._language, self._language)
        self._dropdown_btn.configure(text=f"  {name}  ▾")

    def _toggle_dropdown(self):
        """Show/hide a floating dropdown below the dropdown button."""
        if self._dropdown_visible and self._dropdown_frame:
            self._dropdown_frame.destroy()
            self._dropdown_frame = None
            self._dropdown_visible = False
            return

        # Calculate position: below the dropdown button, aligned right
        self._dropdown_btn.update_idletasks()
        btn_x = self._dropdown_btn.winfo_rootx()
        btn_y = self._dropdown_btn.winfo_rooty() + self._dropdown_btn.winfo_height() + 2
        btn_w = self._dropdown_btn.winfo_width()

        # Item height estimate: 34px per language + 30px separator + 34px add button
        n_items = len(self._enabled_languages)
        popup_h = (n_items * 34) + 30 + 34 + 4  # +4 for border
        popup_w = max(btn_w + 40, 180)

        dd = tk.Toplevel(self._win)
        dd.overrideredirect(True)
        dd.configure(bg=BG, highlightbackground=BORDER, highlightthickness=1)
        dd.attributes("-topmost", True)
        dd.geometry(f"{popup_w}x{popup_h}+{btn_x}+{btn_y}")
        self._dropdown_frame = dd
        self._dropdown_visible = True

        # Close when clicking elsewhere
        dd.bind("<FocusOut>", lambda e: self._close_dropdown())

        # Enabled languages with remove buttons
        for code in list(self._enabled_languages):
            name = ALL_LANGUAGES.get(code, code)
            item_frame = tk.Frame(dd, bg=BG)
            item_frame.pack(fill="x")

            is_active = code == self._language
            item = tk.Label(
                item_frame, text=f"  {name}", font=("Segoe UI", 10),
                fg=TEXT if is_active else TEXT_DIM, bg=PURPLE if is_active else BG,
                anchor="w", padx=8, pady=6, cursor="hand2",
            )
            item.pack(side="left", fill="x", expand=True)
            item.bind("<Button-1>", lambda e, c=code: self._select_from_dropdown(c))
            if not is_active:
                item.bind("<Enter>", lambda e, w=item: w.configure(bg="#252535", fg=TEXT))
                item.bind("<Leave>", lambda e, w=item: w.configure(bg=BG, fg=TEXT_DIM))

            # Remove button
            rm = tk.Label(
                item_frame, text=" × ", font=("Segoe UI", 9),
                fg=TEXT_DIM, bg=PURPLE if is_active else BG, cursor="hand2",
            )
            rm.pack(side="right", padx=(0, 4))
            rm.bind("<Button-1>", lambda e, c=code: self._remove_language(c))
            rm.bind("<Enter>", lambda e, w=rm: w.configure(fg=RED))
            rm.bind("<Leave>", lambda e, w=rm: w.configure(fg=TEXT_DIM))

        # Separator
        tk.Frame(dd, bg=BORDER, height=1).pack(fill="x", padx=8, pady=2)

        # "Add language" button
        add_item = tk.Label(
            dd, text="  + Add language", font=("Segoe UI", 10),
            fg=PURPLE, bg=BG, anchor="w", padx=8, pady=6, cursor="hand2",
        )
        add_item.pack(fill="x")
        add_item.bind("<Button-1>", lambda e: self._open_language_picker())
        add_item.bind("<Enter>", lambda e: add_item.configure(bg="#252535"))
        add_item.bind("<Leave>", lambda e: add_item.configure(bg=BG))

        dd.focus_set()

    def _close_dropdown(self):
        """Close the dropdown popup."""
        if self._dropdown_frame:
            try:
                self._dropdown_frame.destroy()
            except Exception:
                pass
            self._dropdown_frame = None
            self._dropdown_visible = False

    def _select_from_dropdown(self, code):
        """Select a language from the dropdown and close it."""
        self._close_dropdown()
        self._on_lang_click(code)

    def _refresh_lang(self):
        # Update Auto button style
        auto_btn = self._lang_buttons.get("auto")
        if auto_btn:
            if self._language == "auto":
                auto_btn.configure(bg=PURPLE, fg="#ffffff",
                                   highlightbackground=PURPLE, highlightthickness=0)
            else:
                auto_btn.configure(bg="#252535", fg=TEXT_DIM,
                                   highlightbackground=BORDER, highlightthickness=1)
        # Update dropdown button style
        if hasattr(self, '_dropdown_btn') and self._dropdown_btn:
            if self._language != "auto":
                self._dropdown_btn.configure(bg=PURPLE, fg="#ffffff",
                                              highlightbackground=PURPLE, highlightthickness=0)
            else:
                self._dropdown_btn.configure(bg="#252535", fg=TEXT_DIM,
                                              highlightbackground=BORDER, highlightthickness=1)
            self._update_dropdown_label()

    def _on_toggle_click(self, event):
        self._enabled = not self._enabled
        self._refresh_toggle()
        if self._on_toggle:
            self._on_toggle(self._enabled)

    def _on_lang_click(self, code):
        self._language = code
        self._refresh_lang()
        if self._on_language_change:
            self._on_language_change(code)

    def _remove_language(self, code):
        """Remove a language from the enabled list."""
        if code in self._enabled_languages:
            self._enabled_languages.remove(code)
            if self._language == code:
                self._language = "auto"
                if self._on_language_change:
                    self._on_language_change("auto")
            self._close_dropdown()
            self._rebuild_lang_buttons()
            self._toggle_dropdown()  # reopen with updated list
            if self._on_languages_changed:
                self._on_languages_changed(list(self._enabled_languages))

    def _open_language_picker(self):
        """Open a popup to add a new language."""
        self._close_dropdown()

        if self._picker_win is not None:
            try:
                self._picker_win.destroy()
            except Exception:
                pass

        pw = tk.Toplevel(self._win)
        pw.overrideredirect(True)
        pw.configure(bg=BG)
        pw.attributes("-topmost", True)
        self._picker_win = pw

        # Position below the control window
        x = self._win.winfo_x()
        y = self._win.winfo_y() + WIN_H + 4
        pw.geometry(f"{WIN_W}x320+{x}+{y}")

        # Title bar
        tb = tk.Frame(pw, bg=TITLEBAR_BG, height=28)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="  Add Language", font=("Segoe UI", 9),
                 fg=TEXT_DIM, bg=TITLEBAR_BG).pack(side="left")
        close_btn = tk.Label(tb, text=" ✕ ", font=("Segoe UI", 9),
                             fg=TEXT_DIM, bg=TITLEBAR_BG, cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: pw.destroy())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=RED))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=TEXT_DIM))

        # Search box
        search_var = tk.StringVar()
        search_entry = tk.Entry(
            pw, textvariable=search_var, font=("Segoe UI", 10),
            bg="#1a1a24", fg=TEXT, insertbackground=TEXT,
            highlightbackground=BORDER, highlightthickness=1, bd=0,
        )
        search_entry.pack(fill="x", padx=8, pady=(8, 4))
        search_entry.insert(0, "Search...")
        search_entry.bind("<FocusIn>", lambda e: (
            search_entry.delete(0, "end") if search_entry.get() == "Search..." else None
        ))

        # Scrollable list
        list_frame = tk.Frame(pw, bg=BG)
        list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        canvas = tk.Canvas(list_frame, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=WIN_W - 40)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(-1 * (event.delta // 120), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        pw.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        def populate(filter_text=""):
            for w in inner.winfo_children():
                w.destroy()
            ft = filter_text.lower().strip()
            if ft == "search...":
                ft = ""
            for code in sorted(ALL_LANGUAGES.keys(), key=lambda c: ALL_LANGUAGES[c]):
                name = ALL_LANGUAGES[code]
                if code in self._enabled_languages:
                    continue
                if ft and ft not in name.lower() and ft not in code.lower():
                    continue
                item = tk.Label(
                    inner, text=f"  {name}  ({code})", font=("Segoe UI", 10),
                    fg=TEXT_DIM, bg=BG, anchor="w", padx=8, pady=5, cursor="hand2",
                )
                item.pack(fill="x")
                item.bind("<Enter>", lambda e, w=item: w.configure(bg="#252535", fg=TEXT))
                item.bind("<Leave>", lambda e, w=item: w.configure(bg=BG, fg=TEXT_DIM))
                item.bind("<Button-1>", lambda e, c=code: self._add_language(c, pw))

        populate()
        search_var.trace_add("write", lambda *_: populate(search_var.get()))
        search_entry.focus_set()

    def _add_language(self, code, picker_win):
        """Add a language and close the picker."""
        if code not in self._enabled_languages:
            self._enabled_languages.append(code)
            self._rebuild_lang_buttons()
            if self._on_languages_changed:
                self._on_languages_changed(list(self._enabled_languages))
        try:
            picker_win.destroy()
        except Exception:
            pass
        self._picker_win = None

    def _on_quit_click(self, event):
        if self._on_quit:
            self._on_quit()

    def _on_close(self):
        self._win.withdraw()
        self._visible = False
