"""Native Tkinter desktop interface for RIKO.

The window routes text and voice turns through the shared mode functions in
``src/main.py``. It does not start an HTTP server or use a browser.
"""

from __future__ import annotations

import json
import queue
import re
import sys
import threading
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

try:
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import messagebox, simpledialog, ttk
except ImportError as error:
    raise SystemExit(
        "RIKO's desktop GUI requires Tkinter. On Debian/Ubuntu, install "
        "python3-tk and recreate the project virtual environment."
    ) from error


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from conversation_manager import ConversationManager
from prompt_manager import PromptManager
from settings_manager import SettingsManager
from main import create_chat_session, run_text_chat, run_voice_chat
from user_profile import default_profile, normalize_profile
from behavior_preferences import BEHAVIOR_CONTROLS, RESPONSE_STYLE_OPTIONS


COLORS = {
    "background": "#101116",
    "sidebar": "#15161c",
    "panel": "#191b24",
    "panel_lighter": "#232632",
    "border": "#303342",
    "text": "#eeeef2",
    "muted": "#a0a1ad",
    "quiet": "#747582",
    "accent": "#c4a8ff",
    "accent_dark": "#34294a",
    "assistant_bubble": "#202b29",
    "assistant_accent": "#91d4b7",
    "user_bubble": "#272433",
    "success": "#8cc7a2",
    "warning": "#e5b879",
    "danger": "#e88f9c",
}

MODEL_NAME = "qwen3:4b-instruct"
UI_FONT_FAMILY = {
    "win32": "Segoe UI",
    "darwin": "Helvetica Neue",
}.get(sys.platform, "DejaVu Sans")
CODE_FONT_FAMILY = {
    "win32": "Consolas",
    "darwin": "Menlo",
}.get(sys.platform, "DejaVu Sans Mono")
MIN_ZOOM = 0.8
MAX_ZOOM = 1.6
ZOOM_STEP = 0.1


def _clamp_zoom(factor: float) -> float:
    return round(min(MAX_ZOOM, max(MIN_ZOOM, float(factor))), 2)


def _merge_transcript_draft(current: str, candidate: str) -> str:
    """Join overlapping rolling STT drafts without repeating their shared words."""
    current_words = current.split()
    candidate_words = candidate.split()
    if not current_words:
        return candidate.strip()
    if not candidate_words:
        return current.strip()

    def normalize(word: str) -> str:
        return re.sub(r"\W+", "", word.casefold())

    current_normalized = [normalize(word) for word in current_words]
    candidate_normalized = [normalize(word) for word in candidate_words]

    if candidate_normalized[:len(current_normalized)] == current_normalized:
        return candidate.strip()
    if current_normalized[:len(candidate_normalized)] == candidate_normalized:
        return current.strip()

    overlap = 0
    maximum = min(len(current_words), len(candidate_words))
    for size in range(maximum, 0, -1):
        if current_normalized[-size:] == candidate_normalized[:size]:
            overlap = size
            break
    return " ".join(current_words + candidate_words[overlap:]).strip()


_INLINE_MARKDOWN = re.compile(
    r"(?P<image>!\[(?P<image_alt>[^\]]*)\]\([^)]+\))"
    r"|(?P<link>\[(?P<link_text>[^\]]+)\]\([^)]+\))"
    r"|(?P<bold>\*\*(?P<bold_star>.+?)\*\*|__(?P<bold_under>.+?)__)"
    r"|(?P<strike>~~(?P<strike_text>.+?)~~)"
    r"|(?P<code>`(?P<code_text>[^`]+)`)"
    r"|(?P<italic>\*(?P<italic_star>[^*\n]+?)\*|_(?P<italic_under>[^_\n]+?)_)"
)


def _markdown_segments(markdown: str) -> list[tuple[str, tuple[str, ...]]]:
    """Convert common model Markdown into text and Tk formatting tags."""
    segments: list[tuple[str, tuple[str, ...]]] = []

    def append(text: str, tags: tuple[str, ...] = ()) -> None:
        if not text:
            return
        if segments and segments[-1][1] == tags:
            previous, previous_tags = segments[-1]
            segments[-1] = (previous + text, previous_tags)
        else:
            segments.append((text, tags))

    def inline(text: str, block_tags: tuple[str, ...] = ()) -> None:
        cursor = 0
        for match in _INLINE_MARKDOWN.finditer(text):
            append(text[cursor:match.start()], block_tags)
            if match.group("image") is not None:
                append(match.group("image_alt"), block_tags + ("italic",))
            elif match.group("link") is not None:
                append(match.group("link_text"), block_tags + ("link",))
            elif match.group("bold") is not None:
                value = match.group("bold_star") or match.group("bold_under")
                append(value, block_tags + ("bold",))
            elif match.group("strike") is not None:
                append(match.group("strike_text"), block_tags + ("strike",))
            elif match.group("code") is not None:
                append(match.group("code_text"), block_tags + ("inline_code",))
            elif match.group("italic") is not None:
                value = match.group("italic_star") or match.group("italic_under")
                append(value, block_tags + ("italic",))
            cursor = match.end()
        append(text[cursor:], block_tags)

    fenced_code = False
    for raw_line in markdown.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        line_ending = "\n" if raw_line.endswith(("\n", "\r")) else ""
        if re.match(r"^\s*(```|~~~)", line):
            fenced_code = not fenced_code
            continue
        if fenced_code:
            append(line + line_ending, ("code_block",))
            continue

        heading = re.match(r"^\s{0,3}(#{1,6})\s+(.*)$", line)
        if heading:
            level = min(len(heading.group(1)), 3)
            inline(heading.group(2), (f"heading{level}",))
        elif re.match(r"^\s{0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$", line):
            append("────────────────────────\n", ("rule",))
            continue
        elif re.match(r"^\s{0,3}>\s?", line):
            quoted = re.sub(r"^\s{0,3}>\s?", "", line)
            append("│ ", ("quote",))
            inline(quoted, ("quote",))
        else:
            item = re.match(r"^(\s*)([-+*]|\d+[.)])\s+(.*)$", line)
            if item:
                indent = "  " * (len(item.group(1)) // 2)
                marker = "•" if item.group(2) in {"-", "+", "*"} else item.group(2)
                append(f"{indent}{marker} ", ("list",))
                inline(item.group(3))
            else:
                inline(line)

        append(line_ending)
    return segments


class MarkdownResponse(tk.Text):
    """Selectable, auto-sized Tk text widget for assistant Markdown replies."""

    def __init__(self, master, *, width: int, background: str):
        super().__init__(
            master,
            width=width,
            height=1,
            wrap="word",
            bg=background,
            fg=COLORS["text"],
            font=(UI_FONT_FAMILY, 10),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=14,
            pady=0,
            cursor="xterm",
            takefocus=True,
            state="disabled",
        )
        self._configure_markdown_tags()

    def set_markdown(self, markdown: str) -> None:
        self.configure(state="normal")
        self.delete("1.0", "end")
        for content, tags in _markdown_segments(markdown):
            self.insert("end", content, tags)
        self.configure(state="disabled")
        self.update_idletasks()
        try:
            display_lines = self.count("1.0", "end-1c", "displaylines")
            height = int(display_lines[0]) if display_lines else 1
        except (tk.TclError, TypeError, ValueError):
            height = max(1, markdown.count("\n") + 1)
        self.configure(height=max(1, height))

    def set_zoom(self, factor: float) -> None:
        self._zoom_factor = factor
        self._configure_markdown_tags()

    def _configure_markdown_tags(self) -> None:
        factor = getattr(self, "_zoom_factor", 1.0)

        def font(family: str, size: int, *style: str):
            return (family, max(6, round(size * factor)), *style)

        self.tag_configure("bold", font=font(UI_FONT_FAMILY, 10, "bold"))
        self.tag_configure("italic", font=font(UI_FONT_FAMILY, 10, "italic"))
        self.tag_configure("strike", overstrike=True)
        self.tag_configure("link", foreground=COLORS["accent"], underline=True)
        self.tag_configure("inline_code", font=font(CODE_FONT_FAMILY, 9), foreground="#ffd479", background=COLORS["panel_lighter"])
        self.tag_configure("code_block", font=font(CODE_FONT_FAMILY, 9), foreground="#ffd479", background=COLORS["panel_lighter"], lmargin1=10, lmargin2=10, spacing1=3, spacing3=3)
        self.tag_configure("quote", foreground=COLORS["muted"], lmargin1=10, lmargin2=10)
        self.tag_configure("list", foreground=COLORS["accent"], lmargin1=8, lmargin2=8)
        self.tag_configure("rule", foreground=COLORS["border"])
        self.tag_configure("heading1", font=font(UI_FONT_FAMILY, 16, "bold"), foreground=COLORS["accent"], spacing1=7, spacing3=3)
        self.tag_configure("heading2", font=font(UI_FONT_FAMILY, 13, "bold"), foreground=COLORS["accent"], spacing1=6, spacing3=3)
        self.tag_configure("heading3", font=font(UI_FONT_FAMILY, 11, "bold"), foreground=COLORS["text"], spacing1=5, spacing3=2)


class RoundedFrame(tk.Frame):
    """Frame with a Canvas-drawn rounded surface, independent of OS window APIs."""

    def __init__(
        self,
        master,
        *,
        background: str,
        fill: str,
        radius: int = 16,
        outline: str = "",
        border_width: int = 0,
        **kwargs,
    ):
        super().__init__(
            master,
            bg=background,
            bd=0,
            highlightthickness=0,
            **kwargs,
        )
        self._surface_fill = fill
        self._surface_outline = outline
        self._base_radius = radius
        self._base_border_width = border_width
        self._zoom_factor = 1.0
        self._surface = tk.Canvas(
            self,
            bg=background,
            bd=0,
            highlightthickness=0,
            takefocus=False,
        )
        self._surface.place(x=0, y=0, relwidth=1, relheight=1)
        self.tk.call("lower", self._surface._w)
        self.bind("<Configure>", self._draw_surface, add="+")

    def set_zoom(self, factor: float) -> None:
        self._zoom_factor = factor
        self._draw_surface()

    def _draw_surface(self, _event=None) -> None:
        width = self.winfo_width()
        height = self.winfo_height()
        if width < 2 or height < 2:
            return
        radius = min(
            round(self._base_radius * self._zoom_factor),
            (width - 1) // 2,
            (height - 1) // 2,
        )
        right = width - 1
        bottom = height - 1
        self._surface.delete("rounded-surface")
        points = (
            radius, 0,
            right - radius, 0,
            right, 0,
            right, radius,
            right, bottom - radius,
            right, bottom,
            right - radius, bottom,
            radius, bottom,
            0, bottom,
            0, bottom - radius,
            0, radius,
            0, 0,
        )
        border_width = round(self._base_border_width * self._zoom_factor)
        self._surface.create_polygon(
            *points,
            smooth=True,
            splinesteps=24,
            fill=self._surface_fill,
            outline=self._surface_outline,
            width=border_width,
            tags="rounded-surface",
        )


class RikoDesktop:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("RIKO — Local companion")
        self.root.geometry("1180x790")
        self.root.minsize(900, 620)
        self.root.configure(bg=COLORS["background"])

        self.prompts = PromptManager(PROJECT_ROOT)
        self.settings = SettingsManager(PROJECT_ROOT)
        self.conversation: ConversationManager | None = None
        self.active_conversation: ConversationManager | None = None
        self.text_session = None
        self.voice_session = None
        self.voice_thread: threading.Thread | None = None
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.busy = False
        self.response_cancel_requested = False
        self.voice_session_active = False
        self.voice_stopping = False
        self.voice_restart_after_stop = False
        self.current_reply = ""
        self.active_reply_label: MarkdownResponse | tk.Label | None = None
        self.settings_window: tk.Toplevel | None = None
        self.voice_values: list[str] = []
        self.reply_action_widgets = {}
        self.reply_contexts = {}
        self.reply_bubbles = {}
        self.latest_text_reply_body = None
        self.read_aloud_tts = None
        self.read_aloud_active = False
        self.read_aloud_stop_event = None
        self.read_aloud_button = None
        self.read_aloud_lock = threading.Lock()
        self.mic_recording = False
        self.mic_stop_requested = False
        self.mic_stop_event = None
        self.mic_thread = None
        self.mic_original_text = ""
        self.mic_partial_text = ""
        self.zoom_factor = 1.0
        self.zoom_value_var = tk.StringVar(value="100%")
        self._base_font_specs = {}

        self.mode_var = tk.StringVar(value="text")
        self.status_var = tk.StringVar(value="Ready when you are.")
        self.runtime_var = tk.StringVar(value="Checking local runtime…")
        self.persona_var = tk.StringVar(value=self.settings.get_persona())

        self._configure_style()
        self._build_layout()
        self._show_welcome()
        self._apply_zoom()
        self._bind_zoom_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Control-k>", lambda _event: self.new_conversation())
        self.root.bind("<Control-K>", lambda _event: self.new_conversation())
        self.root.bind("<Control-Return>", lambda _event: self.send_message())
        self.root.bind("<Escape>", lambda _event: self.stop_response_generation())
        self.root.after(60, self._drain_events)
        self._check_runtime()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        self.ttk_style = style
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Riko.TCombobox",
            fieldbackground=COLORS["panel_lighter"],
            background=COLORS["panel_lighter"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["muted"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
            padding=8,
            font=(UI_FONT_FAMILY, 10),
        )
        style.map(
            "Riko.TCombobox",
            fieldbackground=[("readonly", COLORS["panel_lighter"])],
            foreground=[("readonly", COLORS["text"])],
            selectbackground=[("readonly", COLORS["accent_dark"])],
            selectforeground=[("readonly", COLORS["text"])],
        )

    def _bind_zoom_shortcuts(self) -> None:
        modifier = "Command" if sys.platform == "darwin" else "Control"
        bindings = {
            f"<{modifier}-plus>": self.zoom_in,
            f"<{modifier}-equal>": self.zoom_in,
            f"<{modifier}-Shift-equal>": self.zoom_in,
            f"<{modifier}-KP_Add>": self.zoom_in,
            f"<{modifier}-minus>": self.zoom_out,
            f"<{modifier}-KP_Subtract>": self.zoom_out,
            f"<{modifier}-0>": self.reset_zoom,
            f"<{modifier}-KP_0>": self.reset_zoom,
            f"<{modifier}-MouseWheel>": self._zoom_mousewheel,
            f"<{modifier}-Button-4>": self.zoom_in,
            f"<{modifier}-Button-5>": self.zoom_out,
        }
        for sequence, callback in bindings.items():
            try:
                self.root.bind_all(sequence, callback)
            except tk.TclError:
                # Some Tk builds don't expose keypad or Command key symbols.
                continue

    def zoom_in(self, _event=None):
        return self.set_zoom(self.zoom_factor + ZOOM_STEP)

    def zoom_out(self, _event=None):
        return self.set_zoom(self.zoom_factor - ZOOM_STEP)

    def reset_zoom(self, _event=None):
        return self.set_zoom(1.0)

    def _zoom_mousewheel(self, event):
        delta = getattr(event, "delta", 0)
        if delta > 0 or getattr(event, "num", None) == 4:
            return self.zoom_in()
        if delta < 0 or getattr(event, "num", None) == 5:
            return self.zoom_out()
        return "break"

    def set_zoom(self, factor: float):
        old_factor = self.zoom_factor
        new_factor = _clamp_zoom(factor)
        if new_factor == old_factor:
            return "break"
        self.zoom_factor = new_factor
        self.zoom_value_var.set(f"{round(new_factor * 100):.0f}%")
        self._apply_zoom()
        self._resize_window_for_zoom(old_factor, new_factor)
        return "break"

    def _descendant_widgets(self, parent):
        for child in parent.winfo_children():
            yield child
            yield from self._descendant_widgets(child)

    def _apply_zoom(self) -> None:
        factor = self.zoom_factor
        for widget in self._descendant_widgets(self.root):
            try:
                font_spec = widget.cget("font")
            except tk.TclError:
                font_spec = ""
            if font_spec:
                if widget not in self._base_font_specs:
                    try:
                        self._base_font_specs[widget] = tkfont.Font(
                            root=self.root,
                            font=font_spec,
                        ).actual()
                    except (tk.TclError, TypeError, ValueError):
                        self._base_font_specs[widget] = None
                base = self._base_font_specs[widget]
                if base:
                    base_size = int(base["size"])
                    scaled_size = max(6, round(abs(base_size) * factor))
                    if base_size < 0:
                        scaled_size = -scaled_size
                    font_parts = [base["family"], scaled_size]
                    if base["weight"] != "normal":
                        font_parts.append(base["weight"])
                    if base["slant"] != "roman":
                        font_parts.append(base["slant"])
                    if base["underline"]:
                        font_parts.append("underline")
                    if base["overstrike"]:
                        font_parts.append("overstrike")
                    try:
                        widget.configure(font=tuple(font_parts))
                    except tk.TclError:
                        pass
            if isinstance(widget, (MarkdownResponse, RoundedFrame)):
                widget.set_zoom(factor)

        self.ttk_style.configure(
            "Riko.TCombobox",
            font=(UI_FONT_FAMILY, max(8, round(10 * factor))),
        )
        if hasattr(self, "sidebar"):
            self.sidebar.configure(width=max(180, round(238 * factor)))

    def _schedule_zoom(self) -> None:
        try:
            self.root.after_idle(self._apply_zoom)
        except (AttributeError, tk.TclError):
            pass

    def _resize_window_for_zoom(self, old_factor: float, new_factor: float) -> None:
        self.root.update_idletasks()
        width = max(1, self.root.winfo_width())
        height = max(1, self.root.winfo_height())
        if width == 1:
            width = 1180
        if height == 1:
            height = 790
        ratio = new_factor / old_factor
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        max_width = max(700, screen_width - 48)
        max_height = max(500, screen_height - 80)
        next_width = round(width * ratio)
        next_height = round(height * ratio)
        if ratio > 1:
            next_width = max(width, min(next_width, max_width))
            next_height = max(height, min(next_height, max_height))
        else:
            next_width = min(next_width, max_width)
            next_height = min(next_height, max_height)
        minimum_width = min(max(700, round(900 * new_factor)), max_width)
        minimum_height = min(max(500, round(620 * new_factor)), max_height)
        self.root.minsize(minimum_width, minimum_height)
        x = min(max(0, self.root.winfo_x()), max(0, screen_width - next_width))
        y = min(max(0, self.root.winfo_y()), max(0, screen_height - next_height))
        self.root.geometry(f"{next_width}x{next_height}+{x}+{y}")

    def _build_layout(self) -> None:
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        self.sidebar = tk.Frame(self.root, bg=COLORS["sidebar"], width=238)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        self.workspace = tk.Frame(self.root, bg=COLORS["background"])
        self.workspace.grid(row=0, column=1, sticky="nsew")
        self.workspace.grid_rowconfigure(1, weight=1)
        self.workspace.grid_columnconfigure(0, weight=1)
        self._build_header()
        self._build_conversation_area()
        self._build_composer()

    def _build_sidebar(self) -> None:
        brand = tk.Frame(self.sidebar, bg=COLORS["sidebar"])
        brand.pack(fill="x", padx=22, pady=(25, 29))
        tk.Label(
            brand,
            text="✦",
            bg=COLORS["sidebar"],
            fg=COLORS["accent"],
            font=(UI_FONT_FAMILY, 22, "bold"),
        ).pack(side="left", padx=(0, 9))
        wordmark = tk.Frame(brand, bg=COLORS["sidebar"])
        wordmark.pack(side="left")
        tk.Label(
            wordmark,
            text="RIKO.",
            bg=COLORS["sidebar"],
            fg=COLORS["text"],
            font=(UI_FONT_FAMILY, 18, "bold"),
        ).pack(anchor="w")
        tk.Label(
            wordmark,
            text="LOCAL COMPANION",
            bg=COLORS["sidebar"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 8, "bold"),
        ).pack(anchor="w")

        self._button(
            self.sidebar,
            "＋   New conversation       Ctrl K",
            self.new_conversation,
            bg=COLORS["panel_lighter"],
            fg=COLORS["text"],
            padx=14,
            pady=12,
        ).pack(fill="x", padx=16, pady=(0, 25))

        tk.Label(
            self.sidebar,
            text="YOUR SPACE",
            bg=COLORS["sidebar"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 8, "bold"),
            anchor="w",
        ).pack(fill="x", padx=21, pady=(0, 8))
        self._nav_button("▤   Conversation", self._focus_composer, active=True)
        self._nav_button("◉   Your profile", self.open_profile)
        self._nav_button("⚙   Preferences", self.open_settings)

        spacer = tk.Frame(self.sidebar, bg=COLORS["sidebar"])
        spacer.pack(fill="both", expand=True)

        runtime = RoundedFrame(
            self.sidebar,
            background=COLORS["sidebar"],
            fill=COLORS["panel"],
            radius=14,
            outline=COLORS["border"],
            border_width=1,
        )
        runtime.pack(fill="x", padx=14, pady=(0, 16))
        runtime_inner = tk.Frame(runtime, bg=COLORS["panel"])
        runtime_inner.pack(fill="x", padx=13, pady=13)
        runtime_title = tk.Frame(runtime_inner, bg=COLORS["panel"])
        runtime_title.pack(fill="x")
        self.runtime_dot = tk.Label(
            runtime_title,
            text="●",
            bg=COLORS["panel"],
            fg=COLORS["warning"],
            font=(UI_FONT_FAMILY, 9),
        )
        self.runtime_dot.pack(side="left", padx=(0, 7))
        tk.Label(
            runtime_title,
            text="LOCAL RUNTIME",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=(UI_FONT_FAMILY, 8, "bold"),
        ).pack(side="left")
        self.runtime_state = tk.Label(
            runtime_title,
            text="CHECKING",
            bg=COLORS["panel"],
            fg=COLORS["warning"],
            font=(UI_FONT_FAMILY, 7, "bold"),
        )
        self.runtime_state.pack(side="right")
        tk.Label(
            runtime_inner,
            text="Ollama · Qwen 3",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=(UI_FONT_FAMILY, 10, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(12, 3))
        self.runtime_caption = tk.Label(
            runtime_inner,
            textvariable=self.runtime_var,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=(UI_FONT_FAMILY, 8),
            anchor="w",
            justify="left",
            wraplength=180,
        )
        self.runtime_caption.pack(fill="x")

        footer = tk.Frame(self.sidebar, bg=COLORS["sidebar"])
        footer.pack(fill="x", padx=18, pady=(0, 17))
        tk.Label(
            footer,
            text="▣   Runs on this computer",
            bg=COLORS["sidebar"],
            fg=COLORS["muted"],
            font=(UI_FONT_FAMILY, 9),
            anchor="w",
        ).pack(fill="x")

    def _nav_button(self, text: str, command, active: bool = False) -> None:
        bg = COLORS["accent_dark"] if active else COLORS["sidebar"]
        fg = COLORS["accent"] if active else COLORS["muted"]
        self._button(
            self.sidebar,
            text,
            command,
            bg=bg,
            fg=fg,
            activebackground=COLORS["panel_lighter"],
            padx=13,
            pady=11,
            anchor="w",
        ).pack(fill="x", padx=12, pady=2)

    @staticmethod
    def _button(parent, text: str, command, **kwargs) -> tk.Button:
        background = kwargs.get("bg", COLORS["panel"])
        foreground = kwargs.get("fg", COLORS["text"])
        defaults = {
            "text": text,
            "command": command,
            "relief": "flat",
            "borderwidth": 0,
            "cursor": "hand2",
            "font": (UI_FONT_FAMILY, 10),
            "highlightthickness": 0,
            "activebackground": (
                "#d4c1ff" if background == COLORS["accent"] else COLORS["panel_lighter"]
            ),
            "activeforeground": foreground,
            "overrelief": "flat",
        }
        defaults.update(kwargs)
        return tk.Button(parent, **defaults)

    def _build_header(self) -> None:
        header = tk.Frame(
            self.workspace,
            bg=COLORS["background"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        context = tk.Frame(header, bg=COLORS["background"])
        context.grid(row=0, column=0, sticky="w", padx=25, pady=18)
        tk.Label(
            context,
            text="YOUR SPACE",
            bg=COLORS["background"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 8, "bold"),
        ).pack(side="left")
        tk.Label(
            context,
            text="   /   Conversation",
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=(UI_FONT_FAMILY, 10),
        ).pack(side="left")
        actions = tk.Frame(header, bg=COLORS["background"])
        actions.grid(row=0, column=1, sticky="e", padx=22)
        self.persona_badge = tk.Label(
            actions,
            text=self._persona_name(),
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=(UI_FONT_FAMILY, 9),
            padx=11,
            pady=7,
        )
        self.persona_badge.pack(side="left", padx=(0, 8))
        zoom_controls = RoundedFrame(
            actions,
            background=COLORS["background"],
            fill=COLORS["panel"],
            radius=11,
            outline=COLORS["border"],
            border_width=1,
        )
        zoom_controls.pack(side="left", padx=(0, 10))
        self._button(
            zoom_controls,
            "−",
            self.zoom_out,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            padx=9,
            pady=5,
            font=(UI_FONT_FAMILY, 10, "bold"),
        ).pack(side="left", padx=(3, 0), pady=3)
        self._button(
            zoom_controls,
            "100%",
            self.reset_zoom,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            padx=4,
            pady=5,
            font=(UI_FONT_FAMILY, 8, "bold"),
            textvariable=self.zoom_value_var,
        ).pack(side="left", pady=3)
        self._button(
            zoom_controls,
            "+",
            self.zoom_in,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            padx=9,
            pady=5,
            font=(UI_FONT_FAMILY, 10, "bold"),
        ).pack(side="left", padx=(0, 3), pady=3)
        self._button(
            actions,
            "Preferences",
            self.open_settings,
            bg=COLORS["background"],
            fg=COLORS["muted"],
            padx=9,
            pady=7,
        ).pack(side="left")

    def _build_conversation_area(self) -> None:
        self.conversation_area = tk.Frame(
            self.workspace,
            bg=COLORS["background"],
        )
        self.conversation_area.grid(row=1, column=0, sticky="nsew")
        self.conversation_area.grid_rowconfigure(0, weight=1)
        self.conversation_area.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self.conversation_area,
            bg=COLORS["background"],
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(
            self.conversation_area,
            orient="vertical",
            command=self.canvas.yview,
        )
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.message_frame = tk.Frame(self.canvas, bg=COLORS["background"])
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.message_frame, anchor="nw"
        )
        self.message_frame.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_message_frame)
        self.canvas.bind_all("<MouseWheel>", self._mousewheel)
        self.canvas.bind_all("<Button-4>", lambda _event: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda _event: self.canvas.yview_scroll(1, "units"))

    def _build_composer(self) -> None:
        footer = tk.Frame(
            self.workspace,
            bg=COLORS["background"],
        )
        footer.grid(row=2, column=0, sticky="ew", padx=30, pady=(4, 16))
        footer.grid_columnconfigure(0, weight=1)

        self.status_label = tk.Label(
            footer,
            textvariable=self.status_var,
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=(UI_FONT_FAMILY, 9),
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        card = RoundedFrame(
            footer,
            background=COLORS["background"],
            fill=COLORS["panel"],
            radius=18,
            outline=COLORS["border"],
            border_width=1,
        )
        card.grid(row=1, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        self.text_panel = tk.Frame(card, bg=COLORS["panel"])
        self.text_panel.grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="ew",
            padx=10,
            pady=(9, 0),
        )
        self.text_panel.grid_columnconfigure(0, weight=1)
        self.input = tk.Text(
            self.text_panel,
            height=3,
            wrap="word",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            selectbackground=COLORS["accent_dark"],
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=12,
            font=(UI_FONT_FAMILY, 11),
            undo=True,
        )
        self.input.grid(row=0, column=0, sticky="ew")
        self.input.bind("<Return>", self._enter_to_send)
        self.input.bind("<Shift-Return>", lambda _event: None)

        self.voice_panel = tk.Frame(card, bg=COLORS["panel"], height=112)
        self.voice_panel.grid_columnconfigure(0, weight=1)
        tk.Label(
            self.voice_panel,
            text="Speak to Riko",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=(UI_FONT_FAMILY, 13, "bold"),
        ).grid(row=0, column=0, sticky="ew", pady=(15, 4))
        tk.Label(
            self.voice_panel,
            text="Selecting Voice starts listening automatically. Select Chat to stop.",
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            font=(UI_FONT_FAMILY, 9),
        ).grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.voice_status_label = tk.Label(
            self.voice_panel,
            text="Voice mode is off.",
            bg=COLORS["panel"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 9),
        )
        self.voice_status_label.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        self.voice_panel.grid_remove()

        toolbar = tk.Frame(card, bg=COLORS["panel"])
        toolbar.grid(row=1, column=0, columnspan=4, sticky="ew", padx=12, pady=(0, 10))
        mode_box = tk.Frame(toolbar, bg=COLORS["panel"])
        mode_box.pack(side="left")
        self.mode_buttons: dict[str, tk.Button] = {}
        for mode, label in (("text", "◌  Chat"), ("voice", "♬  Voice")):
            button = self._button(
                mode_box,
                label,
                lambda selected=mode: self.set_mode(selected),
                bg=COLORS["accent_dark"] if mode == "text" else COLORS["panel"],
                fg=COLORS["accent"] if mode == "text" else COLORS["muted"],
                padx=11,
                pady=7,
                font=(UI_FONT_FAMILY, 9, "bold"),
            )
            button.pack(side="left", padx=(0, 5))
            self.mode_buttons[mode] = button

        self.mode_hint = tk.Label(
            toolbar,
            text="Replies stream from your local model",
            bg=COLORS["panel"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 8),
        )
        self.mode_hint.pack(side="left", padx=8)

        self.send_button = self._button(
            toolbar,
            "Send  ↗",
            self._action_button_pressed,
            bg=COLORS["accent"],
            fg="#17131f",
            activebackground="#d4c1ff",
            padx=15,
            pady=8,
            font=(UI_FONT_FAMILY, 9, "bold"),
        )
        self.send_button.pack(side="right")

        self.mic_button = self._button(
            toolbar,
            "🎙",
            self.toggle_mic_recording,
            bg=COLORS["panel_lighter"],
            fg=COLORS["text"],
            activebackground=COLORS["border"],
            padx=11,
            pady=7,
            width=3,
            font=(UI_FONT_FAMILY, 11),
            takefocus=True,
        )
        self.mic_button.pack(side="right", padx=(0, 7))
        self._refresh_mic_button()

        note = tk.Frame(footer, bg=COLORS["background"])
        note.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        tk.Label(
            note,
            text="RIKO can make mistakes. Your judgment matters.",
            bg=COLORS["background"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 8),
        ).pack(side="left")
        self.keyboard_hint = tk.Label(
            note,
            text="Enter to send · Shift + Enter for a new line",
            bg=COLORS["background"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 8),
        )
        self.keyboard_hint.pack(side="right")
        self.set_mode("text")

    def _show_welcome(self) -> None:
        welcome = tk.Frame(self.message_frame, bg=COLORS["background"])
        welcome.pack(fill="x", padx=44, pady=(62, 20))
        tk.Label(
            welcome,
            text="✦",
            bg=COLORS["background"],
            fg=COLORS["accent"],
            font=(UI_FONT_FAMILY, 40),
        ).pack(anchor="center", pady=(0, 12))
        tk.Label(
            welcome,
            text="A LITTLE SPACE THAT'S YOURS",
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=(UI_FONT_FAMILY, 8, "bold"),
        ).pack(anchor="center", pady=(0, 14))
        title = tk.Frame(welcome, bg=COLORS["background"])
        title.pack()
        tk.Label(
            title,
            text="Good to have you",
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=(UI_FONT_FAMILY, 25, "bold"),
        ).pack(side="left", padx=(0, 7))
        tk.Label(
            title,
            text="here.",
            bg=COLORS["background"],
            fg=COLORS["accent"],
            font=(UI_FONT_FAMILY, 25, "italic"),
        ).pack(side="left")
        tk.Label(
            welcome,
            text="I'm Riko. We can talk something through, explore an idea,\nor simply pick up wherever you are.",
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=(UI_FONT_FAMILY, 11),
            justify="center",
        ).pack(anchor="center", pady=(10, 19))

        suggestions = tk.Frame(welcome, bg=COLORS["background"])
        suggestions.pack(anchor="center")
        for text in (
            "Help me think through an idea I'm working on",
            "Can you explain a topic I'm learning in a clear way?",
            "I could use help organizing what's on my mind",
        ):
            self._button(
                suggestions,
                "›   " + text,
                lambda prompt=text: self._use_suggestion(prompt),
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                activebackground=COLORS["panel_lighter"],
                padx=13,
                pady=10,
                anchor="w",
                font=(UI_FONT_FAMILY, 9),
            ).pack(fill="x", pady=3)
        tk.Label(
            welcome,
            text="TEXT OR VOICE · YOU CHOOSE",
            bg=COLORS["background"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 8, "bold"),
        ).pack(anchor="center", pady=(18, 0))
        self.welcome_frame = welcome
        self._schedule_zoom()

    def _use_suggestion(self, prompt: str) -> None:
        self.set_mode("text")
        self.input.delete("1.0", "end")
        self.input.insert("1.0", prompt)
        self.input.focus_set()

    def _focus_composer(self) -> None:
        if self.mode_var.get() == "voice":
            self.mode_buttons["voice"].focus_set()
        else:
            self.input.focus_set()

    def _enter_to_send(self, event) -> str | None:
        if event.state & 0x0001:
            return None
        self.send_message()
        return "break"

    def _resize_message_frame(self, event) -> None:
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def _update_scroll_region(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.root.after_idle(lambda: self.canvas.yview_moveto(1.0))

    def _mousewheel(self, event) -> None:
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _persona_name(self) -> str:
        try:
            persona = self.prompts.get_persona()
            return str(persona.get("name", "Riko"))
        except Exception:
            return "Riko"

    def set_mode(self, mode: str) -> None:
        if mode not in {"text", "voice"}:
            return
        current_mode = self.mode_var.get()
        if getattr(self, "mic_recording", False) and mode != current_mode:
            self.status_var.set("Stop microphone transcription before changing modes.")
            return
        if mode == current_mode:
            if mode == "voice" and not self.voice_session_active and not self.busy:
                self.start_voice_session()
            elif mode == "voice" and self.voice_stopping:
                self.voice_restart_after_stop = True
            return
        if self.busy and not self.voice_session_active:
            self.status_var.set("Wait for the current reply to finish before changing modes.")
            return
        if self.voice_session_active and mode == "text":
            self.stop_voice_session()
        elif mode == "voice" and self.voice_stopping:
            self.voice_restart_after_stop = True
        self.mode_var.set(mode)
        for key, button in self.mode_buttons.items():
            selected = key == mode
            button.configure(
                bg=COLORS["accent_dark"] if selected else COLORS["panel"],
                fg=COLORS["accent"] if selected else COLORS["muted"],
            )
        if mode == "voice":
            self.mode_hint.configure(text="Voice input goes to Ollama; replies stream here and speak aloud")
            self.keyboard_hint.configure(text="Voice starts automatically · Select Chat to stop")
            self.text_panel.grid_remove()
            self.voice_panel.grid(row=0, column=0, columnspan=4, sticky="ew", padx=12)
            self.send_button.pack_forget()
            self.voice_status_label.configure(text="Starting voice chat…")
            self.start_voice_session()
        else:
            self.mode_hint.configure(text="Replies stream from your local model")
            self.keyboard_hint.configure(text="Enter to send · Shift + Enter for a new line")
            self.voice_panel.grid_remove()
            self.text_panel.grid(
                row=0,
                column=0,
                columnspan=4,
                sticky="ew",
                padx=10,
                pady=(9, 0),
            )
            self.send_button.pack(side="right")
            if self.voice_session_active:
                self.voice_status_label.configure(text="Stopping voice chat…")
        self._refresh_send_button()
        self._refresh_mic_button()

    def _add_message(
        self,
        role: str,
        text: str,
        *,
        with_actions: bool = False,
    ) -> MarkdownResponse | tk.Label:
        is_user = role == "you"
        row = tk.Frame(self.message_frame, bg=COLORS["background"])
        row.pack(fill="x", padx=32, pady=(12, 4))
        bubble_color = (
            COLORS["user_bubble"] if is_user else COLORS["assistant_bubble"]
        )
        bubble = RoundedFrame(
            row,
            background=COLORS["background"],
            fill=bubble_color,
            radius=16,
            outline=COLORS["border"],
            border_width=1,
        )
        if is_user:
            bubble.pack(side="left", padx=(0, 120))
        else:
            bubble.pack(side="right", fill="x", expand=True, padx=(56, 0))
        tk.Label(
            bubble,
            text="YOU" if is_user else self._persona_name().upper(),
            bg=bubble_color,
            fg=COLORS["muted"] if is_user else COLORS["assistant_accent"],
            font=(UI_FONT_FAMILY, 8, "bold"),
            anchor="w",
        ).pack(fill="x", padx=4, pady=(10, 3))
        if is_user:
            body = tk.Label(
                bubble,
                text=text or " ",
                bg=bubble_color,
                fg=COLORS["text"],
                font=(UI_FONT_FAMILY, 10),
                justify="left",
                anchor="w",
                wraplength=max(
                    260,
                    min(560, round(self.workspace.winfo_width() * 0.58)),
                ),
                padx=14,
            )
        else:
            wrap_pixels = max(300, self.workspace.winfo_width() - 180)
            body = MarkdownResponse(
                bubble,
                width=max(42, min(120, wrap_pixels // 8)),
                background=bubble_color,
            )
            body.set_markdown(text or " ")
        body.pack(fill="x", padx=4, pady=(0, 11))
        if not hasattr(self, "reply_bubbles"):
            self.reply_bubbles = {}
        self.reply_bubbles[body] = bubble
        if not is_user and with_actions:
            actions = tk.Frame(bubble, bg=bubble_color)
            actions.pack(fill="x", padx=14, pady=(0, 10))
            regenerate_button = self._button(
                actions,
                "↻  Regenerate",
                lambda target=body: self.regenerate_reply(target),
                bg=bubble_color,
                fg=COLORS["muted"],
                activebackground=COLORS["panel_lighter"],
                padx=8,
                pady=4,
                font=(UI_FONT_FAMILY, 8),
            )
            regenerate_button.pack(side="left", padx=(0, 6))
            read_button = self._button(
                actions,
                "▶  Read aloud",
                lambda target=body: self.toggle_read_aloud(target),
                bg=bubble_color,
                fg=COLORS["muted"],
                activebackground=COLORS["panel_lighter"],
                padx=8,
                pady=4,
                font=(UI_FONT_FAMILY, 8),
            )
            read_button.pack(side="left")
            self.reply_action_widgets[body] = {
                "regenerate": regenerate_button,
                "read_aloud": read_button,
            }
        self._schedule_zoom()
        return body

    def _set_reply_content(self, text: str) -> None:
        if self.active_reply_label is None:
            return
        context = getattr(self, "reply_contexts", {}).get(self.active_reply_label)
        if context is not None:
            context["text"] = text
        render_markdown = getattr(self.active_reply_label, "set_markdown", None)
        if callable(render_markdown):
            render_markdown(text or " ")
        else:
            self.active_reply_label.configure(text=text or " ")

    def _add_tool_call(self, payload) -> None:
        body = self.active_reply_label
        bubble = getattr(self, "reply_bubbles", {}).get(body)
        if body is None or bubble is None or not isinstance(payload, dict):
            return

        tool_name = str(payload.get("tool_name", "unknown_tool"))
        display_name = {
            "get_architecture_info": "architecture_lookup",
            "explore_codebase": "codebase_lookup",
        }.get(tool_name, tool_name)
        arguments = payload.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {"query": arguments}
        if not isinstance(arguments, dict):
            arguments = {}
        query = (
            arguments.get("topic")
            or arguments.get("path")
            or arguments.get("query")
            or arguments.get("operation")
            or ""
        )
        paths = payload.get("result_paths", [])
        if not isinstance(paths, list):
            paths = []

        block = tk.Frame(bubble, bg=COLORS["panel_lighter"])
        block.pack(fill="x", padx=12, pady=(7, 0), before=body)
        details = tk.Frame(block, bg=COLORS["panel_lighter"])
        expanded = {"value": False}

        def toggle_details() -> None:
            expanded["value"] = not expanded["value"]
            if expanded["value"]:
                details.pack(fill="x", padx=11, pady=(0, 10))
                toggle.configure(text=f"▾  tool  {display_name}")
            else:
                details.pack_forget()
                toggle.configure(text=f"▸  tool  {display_name}")

        toggle = self._button(
            block,
            f"▸  tool  {display_name}",
            toggle_details,
            bg=COLORS["panel_lighter"],
            fg=COLORS["assistant_accent"],
            activebackground=COLORS["panel"],
            anchor="w",
            padx=10,
            pady=7,
            font=(UI_FONT_FAMILY, 9, "bold"),
        )
        toggle.pack(fill="x", padx=3, pady=3)

        tk.Label(
            details,
            text=f"Query / pattern: {query or '(not provided)'}",
            bg=COLORS["panel_lighter"],
            fg=COLORS["text"],
            font=(UI_FONT_FAMILY, 9),
            justify="left",
            anchor="w",
            wraplength=max(280, self.workspace.winfo_width() - 180),
        ).pack(fill="x", pady=(0, 5))
        tk.Label(
            details,
            text="Files returned",
            bg=COLORS["panel_lighter"],
            fg=COLORS["muted"],
            font=(UI_FONT_FAMILY, 8, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 2))
        for path in paths:
            tk.Label(
                details,
                text=f"→ {path}",
                bg=COLORS["panel_lighter"],
                fg=COLORS["text"],
                font=(CODE_FONT_FAMILY, 8),
                anchor="w",
                justify="left",
                wraplength=max(280, self.workspace.winfo_width() - 180),
            ).pack(fill="x")
        if not paths:
            tk.Label(
                details,
                text="No file paths returned.",
                bg=COLORS["panel_lighter"],
                fg=COLORS["quiet"],
                font=(UI_FONT_FAMILY, 8),
                anchor="w",
            ).pack(fill="x")

    def _refresh_reply_action_buttons(self) -> None:
        if not hasattr(self, "reply_action_widgets"):
            return
        try:
            read_aloud_enabled = self.settings.get_text_to_voice_enabled()
        except (AttributeError, TypeError):
            read_aloud_enabled = True

        for body, buttons in self.reply_action_widgets.items():
            context = self.reply_contexts.get(body)
            text = context.get("text", "").strip() if context else ""
            is_generating = bool(self.busy and self.active_reply_label is body)
            can_regenerate = bool(
                context
                and body is self.latest_text_reply_body
                and not self.busy
                and not self.mic_recording
                and not self.voice_session_active
            )
            can_read = bool(
                read_aloud_enabled
                and context
                and text
                and text != "…"
                and not is_generating
            )
            buttons["regenerate"].configure(
                state="normal" if can_regenerate else "disabled",
            )
            is_active_button = body is self.read_aloud_button
            if is_active_button and self.read_aloud_active:
                buttons["read_aloud"].configure(
                    text="■  Stop audio",
                    state="normal" if not self.mic_recording else "disabled",
                    fg=COLORS["danger"],
                )
            else:
                buttons["read_aloud"].configure(
                    text="▶  Read aloud",
                    state=(
                        "normal"
                        if can_read
                        and not self.read_aloud_active
                        and not self.mic_recording
                        else "disabled"
                    ),
                    fg=COLORS["muted"],
                )

    def regenerate_reply(self, body) -> None:
        context = self.reply_contexts.get(body)
        if (
            context is None
            or body is not self.latest_text_reply_body
            or self.busy
            or self.voice_session_active
            or self.mic_recording
        ):
            return
        if self.read_aloud_active:
            self._stop_read_aloud()

        conversation = context["conversation"]
        history = [dict(item) for item in context["history"]]
        if history and history[0].get("role") == "system":
            history[0]["content"] = self.prompts.build_prompt(mode="text")
        conversation.messages[:] = history
        begin_response = getattr(conversation, "begin_response", None)
        if callable(begin_response):
            begin_response()

        message = context["message"]
        context["text"] = ""
        self.active_reply_label = body
        self._set_reply_content("…")
        self.current_reply = ""
        self.busy = True
        self.response_cancel_requested = False
        self.current_turn_mode = "text"
        self.active_conversation = conversation
        self._refresh_send_button()
        self._refresh_mic_button()
        self._refresh_reply_action_buttons()
        for button in self.mode_buttons.values():
            button.configure(state="disabled")
        self.status_var.set("Regenerating RIKO's reply…")
        threading.Thread(
            target=self._respond,
            args=(message, conversation),
            name="riko-desktop-regenerate",
            daemon=True,
        ).start()

    def toggle_read_aloud(self, body) -> None:
        if self.read_aloud_active:
            self._stop_read_aloud()
            return
        try:
            if not self.settings.get_text_to_voice_enabled():
                self.status_var.set("Text-to-voice is disabled in Preferences.")
                return
        except AttributeError:
            pass

        context = self.reply_contexts.get(body)
        if context is None:
            return
        try:
            from audio.kokoro.tts import markdown_to_speech, remove_emojis

            text = markdown_to_speech(remove_emojis(context.get("text", "")))
        except Exception as error:
            self.status_var.set(f"Could not prepare speech: {error}")
            return
        if not text:
            self.status_var.set("There is no readable text in that reply.")
            return

        stop_event = threading.Event()
        self.read_aloud_active = True
        self.read_aloud_stop_event = stop_event
        self.read_aloud_button = body
        self._refresh_reply_action_buttons()
        self.status_var.set("Reading the reply aloud with Kokoro…")
        threading.Thread(
            target=self._read_aloud_worker,
            args=(text, stop_event),
            name="riko-text-read-aloud",
            daemon=True,
        ).start()

    def _read_aloud_worker(self, text: str, stop_event: threading.Event) -> None:
        error = None
        try:
            from audio.kokoro.tts import KokoroTTS

            with self.read_aloud_lock:
                if self.read_aloud_tts is None:
                    settings = self.settings.get_tts_settings()
                    self.read_aloud_tts = KokoroTTS(
                        voice=self.settings.get_tts_voice(),
                        speed=float(settings.get("speed", 1.0)),
                        lang=settings.get("language", "en-us"),
                        cache_enabled=self.settings.get_tts_cache_enabled(),
                    )
                else:
                    settings = self.settings.get_tts_settings()
                    self.read_aloud_tts.voice = self.settings.get_tts_voice()
                    self.read_aloud_tts.speed = float(settings.get("speed", 1.0))
                    self.read_aloud_tts.lang = settings.get("language", "en-us")
                    self.read_aloud_tts.cache_enabled = self.settings.get_tts_cache_enabled()
                tts = self.read_aloud_tts
            tts.speak_text(text, cancel_event=stop_event)
        except Exception as exc:
            error = str(exc)
        finally:
            self.events.put(("read_aloud_done", (stop_event, error)))

    def _stop_read_aloud(self) -> None:
        stop_event = self.read_aloud_stop_event
        if stop_event is not None:
            stop_event.set()
        with self.read_aloud_lock:
            tts = self.read_aloud_tts
        if tts is not None:
            try:
                tts.stop()
            except Exception as error:
                self.status_var.set(f"Could not stop speech playback: {error}")
        if self.read_aloud_active:
            self.status_var.set("Stopping read-aloud playback…")

    def _finish_read_aloud(self, payload) -> None:
        stop_event, error = payload
        if stop_event is not self.read_aloud_stop_event:
            return
        was_stopped = stop_event.is_set()
        self.read_aloud_active = False
        self.read_aloud_stop_event = None
        self.read_aloud_button = None
        self._refresh_reply_action_buttons()
        if error:
            self.status_var.set(f"Read aloud failed: {error}")
        elif not self.busy:
            self.status_var.set(
                "Read-aloud playback stopped."
                if was_stopped
                else "Finished reading the reply."
            )

    def new_conversation(self) -> None:
        if self.busy or self.voice_session_active or getattr(self, "mic_recording", False):
            self.status_var.set("Finish the current activity before starting a new conversation.")
            return
        if self.read_aloud_active:
            self._stop_read_aloud()
        self.conversation = None
        self.text_session = None
        self.reply_action_widgets.clear()
        self.reply_contexts.clear()
        self.latest_text_reply_body = None
        for child in self.message_frame.winfo_children():
            child.destroy()
        self._show_welcome()
        self.status_var.set("A new conversation is ready.")
        self._focus_composer()

    def send_message(self) -> None:
        if self.mode_var.get() != "text":
            return
        if self.busy or self.voice_session_active or getattr(self, "mic_recording", False):
            return
        message = self.input.get("1.0", "end-1c").strip()
        if not message:
            self.input.focus_set()
            return
        if len(message) > 20_000:
            self.status_var.set("Messages must be 20,000 characters or shorter.")
            return

        self._start_message(message, "text")

    def _refresh_mic_button(self) -> None:
        button = getattr(self, "mic_button", None)
        mode_var = getattr(self, "mode_var", None)
        if button is None or mode_var is None:
            return
        if mode_var.get() != "text":
            button.pack_forget()
            return
        button.pack(side="right", padx=(0, 7))
        if self.mic_recording and self.mic_stop_requested:
            button.configure(
                text="…",
                state="disabled",
                bg=COLORS["panel_lighter"],
                fg=COLORS["muted"],
            )
        elif self.mic_recording:
            button.configure(
                text="■",
                state="normal",
                bg=COLORS["danger"],
                fg="#1c1114",
                activebackground="#f1a3ad",
            )
        else:
            enabled = not self.busy and not self.voice_session_active
            button.configure(
                text="🎙",
                state="normal" if enabled else "disabled",
                bg=COLORS["panel_lighter"],
                fg=COLORS["text"],
                activebackground=COLORS["border"],
            )

    def toggle_mic_recording(self) -> None:
        if self.mic_recording:
            self.stop_mic_recording()
            return
        if self.mode_var.get() != "text":
            return
        if self.busy or self.voice_session_active:
            self.status_var.set("Wait for the current reply before recording a message.")
            return

        if self.read_aloud_active:
            self._stop_read_aloud()
        self.mic_original_text = self.input.get("1.0", "end-1c")
        self.mic_partial_text = ""
        self.mic_stop_event = threading.Event()
        self.mic_recording = True
        self.mic_stop_requested = False
        self.input.configure(state="disabled")
        for button in self.mode_buttons.values():
            button.configure(state="disabled")
        self._refresh_send_button()
        self._refresh_mic_button()
        self._refresh_reply_action_buttons()
        self.status_var.set("Listening… speak, then press the microphone button again to finish.")
        self.mic_thread = threading.Thread(
            target=self._run_mic_recording,
            args=(self.mic_stop_event,),
            name="riko-desktop-microphone-transcription",
            daemon=True,
        )
        self.mic_thread.start()

    def stop_mic_recording(self) -> None:
        if not self.mic_recording or self.mic_stop_requested:
            return
        self.mic_stop_requested = True
        if self.mic_stop_event is not None:
            self.mic_stop_event.set()
        self.status_var.set("Finishing transcription…")
        self._refresh_mic_button()

    def _run_mic_recording(self, stop_event: threading.Event) -> None:
        try:
            from audio.stt.streaming_voice_input import StreamingVoiceInput

            voice_input = StreamingVoiceInput(
                model_size="base",
                device="cpu",
                compute_type="int8",
                language_mode="auto",
                max_record_seconds=120.0,
                update_interval=0.8,
                window_seconds=6.0,
            )
            transcript = voice_input.listen_once(
                stop_event=stop_event,
                on_partial=lambda text: self.events.put(("mic_partial", text)),
                finalize_on_stop=True,
                manual_stop=True,
            )
            self.events.put(("mic_recording_done", (transcript, None)))
        except Exception as error:
            self.events.put(("mic_recording_done", ("", str(error))))

    def _set_composer_text(self, text: str) -> None:
        self.input.configure(state="normal")
        self.input.delete("1.0", "end")
        if text:
            self.input.insert("1.0", text)
        self.input.mark_set("insert", "end-1c")
        self.input.configure(state="disabled" if self.mic_recording else "normal")

    def _apply_mic_partial(self, partial: str) -> None:
        if not self.mic_recording or self.mic_stop_requested:
            return
        partial = partial.strip()
        if not partial:
            return
        self.mic_partial_text = _merge_transcript_draft(
            self.mic_partial_text,
            partial,
        )
        prefix = self.mic_original_text
        separator = "\n" if prefix and self.mic_partial_text else ""
        self._set_composer_text(prefix + separator + self.mic_partial_text)

    def _finish_mic_recording(self, payload) -> None:
        transcript, error = payload
        base_text = self.mic_original_text
        recognized_text = str(transcript or "").strip() or self.mic_partial_text
        self.mic_recording = False
        self.mic_stop_requested = False
        self.mic_stop_event = None
        self.mic_thread = None
        if recognized_text:
            separator = "\n" if base_text else ""
            self._set_composer_text(base_text + separator + recognized_text)
        else:
            self._set_composer_text(base_text)
        for button in self.mode_buttons.values():
            button.configure(state="normal")
        self._refresh_send_button()
        self._refresh_mic_button()
        self._refresh_reply_action_buttons()
        if error:
            self.status_var.set(f"Microphone transcription failed: {error}")
        elif transcript:
            self.status_var.set("Transcript added to the message. Review it, then press Send.")
        elif recognized_text:
            self.status_var.set("Final transcription was empty; kept the live draft for you to review.")
        else:
            self.status_var.set("No speech was recognized. You can try again or type a message.")
        self.input.focus_set()

    def handle_voice_transcription(self, transcript: str) -> None:
        """Append a transcript produced by the shared CLI voice pipeline."""
        message = transcript.strip()
        if not message:
            return
        if getattr(self, "welcome_frame", None) is not None:
            self.welcome_frame.destroy()
            self.welcome_frame = None
        self._add_message("you", message)
        self.current_reply = ""
        self.active_reply_label = self._add_message("riko", "…")
        self.status_var.set("RIKO is replying aloud…")

    def _start_message(self, message: str, mode: str) -> None:
        if mode != "text":
            raise ValueError("Only the text composer can start typed messages.")
        if self.busy or self.voice_session_active or self.mic_recording:
            return
        message = message.strip()
        if not message:
            self.status_var.set("Write a message first.")
            return
        if len(message) > 20_000:
            self.status_var.set("Messages must be 20,000 characters or shorter.")
            return
        try:
            conversation = self._conversation_for("text")
            history_before_turn = [dict(item) for item in conversation.messages]
            begin_response = getattr(conversation, "begin_response", None)
            if callable(begin_response):
                begin_response()
        except Exception as error:
            self.status_var.set(f"Could not start a reply: {error}")
            return
        if getattr(self, "welcome_frame", None) is not None:
            self.welcome_frame.destroy()
            self.welcome_frame = None
        if self.read_aloud_active:
            self._stop_read_aloud()
        self._add_message("you", message)
        self.input.delete("1.0", "end")
        self.current_reply = ""
        self.active_reply_label = self._add_message(
            "riko",
            "…",
            with_actions=True,
        )
        self.reply_contexts[self.active_reply_label] = {
            "message": message,
            "conversation": conversation,
            "history": history_before_turn,
            "text": "",
        }
        self.latest_text_reply_body = self.active_reply_label
        self.busy = True
        self.response_cancel_requested = False
        self.current_turn_mode = mode
        self.active_conversation = conversation
        self._refresh_send_button()
        self._refresh_mic_button()
        self._refresh_reply_action_buttons()
        for button in self.mode_buttons.values():
            button.configure(state="disabled")
        self.status_var.set("RIKO is thinking…")
        threading.Thread(
            target=self._respond,
            args=(message, conversation),
            name="riko-desktop-chat",
            daemon=True,
        ).start()

    def _conversation_for(self, mode: str) -> ConversationManager:
        if self.text_session is None or self.text_session.conversation is not self.conversation:
            self.text_session = create_chat_session(
                "text",
                prompt_manager=self.prompts,
                conversation=self.conversation,
            )
            self.conversation = self.text_session.conversation
        self.conversation.messages[0]["content"] = self.prompts.build_prompt(mode=mode)
        self.conversation.enable_text_status = mode == "text"
        self.conversation.enable_voice_status = False
        return self.conversation

    def _response_tokens(self, conversation: ConversationManager, message: str):
        session = self.text_session
        stream = (
            run_text_chat(session=session, message=message)
            if session is not None and session.conversation is conversation
            else run_text_chat(
                session=create_chat_session(
                    "text",
                    prompt_manager=self.prompts,
                    conversation=conversation,
                ),
                message=message,
            )
        )
        try:
            for item in stream:
                if (
                    isinstance(item, tuple)
                    and len(item) == 2
                    and item[0] == "__RIKO_STATUS__"
                ):
                    self.events.put(("status", str(item[1])))
                elif (
                    isinstance(item, tuple)
                    and len(item) == 2
                    and item[0] == "__RIKO_TOOL__"
                ):
                    self.events.put(("tool_call", item[1]))
                elif isinstance(item, str):
                    self.events.put(("token", item))
                yield item
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()

    def _respond(
        self,
        message: str,
        conversation: ConversationManager | None = None,
    ) -> None:
        try:
            conversation = conversation or self.active_conversation
            if conversation is None:
                conversation = self._conversation_for("text")
            for _item in self._response_tokens(conversation, message):
                pass
            self.events.put(("done", None))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _action_button_pressed(self) -> None:
        if self.busy:
            self.stop_response_generation()
        elif self.mode_var.get() == "text":
            self.send_message()

    def stop_response_generation(self) -> None:
        """Stop the active text or voice reply while keeping the session open."""
        if not self.busy or self.response_cancel_requested:
            return
        self.response_cancel_requested = True
        self.status_var.set("Stopping the response…")
        self._refresh_send_button()

        try:
            if self.current_turn_mode == "voice":
                if self.voice_session is not None:
                    self.voice_session.stop_response_generation()
                return

            conversation = self.active_conversation
            if conversation is None and self.text_session is not None:
                conversation = self.text_session.conversation
            stop = getattr(conversation, "stop_response_generation", None)
            if callable(stop):
                stop()
        except Exception as error:
            self.status_var.set(f"Could not stop the response: {error}")

    def _refresh_send_button(self) -> None:
        button = getattr(self, "send_button", None)
        mode_var = getattr(self, "mode_var", None)
        if button is None or mode_var is None:
            return

        mode = mode_var.get()
        visible = mode == "text" or (mode == "voice" and self.busy)
        if visible:
            button.pack(side="right")
        else:
            button.pack_forget()

        busy = bool(getattr(self, "busy", False))
        if getattr(self, "mic_recording", False) and mode == "text":
            button.configure(
                text="Send  ↗",
                state="disabled",
                bg=COLORS["panel_lighter"],
                fg=COLORS["muted"],
            )
        elif getattr(self, "voice_stopping", False) and mode == "text":
            button.configure(
                text="Stopping…",
                state="disabled",
                bg=COLORS["panel_lighter"],
                fg=COLORS["muted"],
            )
        elif busy and getattr(self, "response_cancel_requested", False):
            button.configure(
                text="Stopping…",
                state="disabled",
                bg=COLORS["panel_lighter"],
                fg=COLORS["muted"],
            )
        elif busy:
            button.configure(
                text="■  Stop",
                state="normal",
                bg=COLORS["danger"],
                fg="#1c1114",
                activebackground="#f1a3ad",
            )
        else:
            button.configure(
                text="Send  ↗",
                state="normal",
                bg=COLORS["accent"],
                fg="#17131f",
                activebackground="#d4c1ff",
            )

    def start_voice_session(self) -> None:
        if self.voice_session_active:
            if self.voice_stopping and self.mode_var.get() == "voice":
                self.voice_restart_after_stop = True
            return
        if self.busy:
            return

        self.voice_stopping = False
        self.voice_restart_after_stop = False
        try:
            self.voice_session = create_chat_session(
                "voice",
                prompt_manager=self.prompts,
                settings_manager=self.settings,
            )
            self.conversation = self.voice_session.conversation
        except Exception as error:
            self.status_var.set(f"Could not start Voice Chat: {error}")
            self.voice_status_label.configure(text=f"Could not start voice chat: {error}")
            self.voice_session = None
            return

        self.voice_session_active = True
        self.status_var.set("Starting RIKO's voice pipeline…")
        self.voice_status_label.configure(text="Starting RIKO's voice pipeline…")
        self.voice_thread = threading.Thread(
            target=self._run_voice_session,
            args=(self.voice_session,),
            name="riko-shared-voice-session",
            daemon=True,
        )
        self.voice_thread.start()

    def stop_voice_session(self) -> None:
        if self.voice_session is None or not self.voice_session_active:
            return
        self.voice_stopping = True
        self.voice_session.stop()
        self.send_button.configure(state="disabled")
        self.status_var.set("Stopping RIKO's voice pipeline…")
        self.voice_status_label.configure(text="Stopping voice chat…")

    def _run_voice_session(self, session) -> None:
        try:
            run_voice_chat(
                session=session,
                on_event=lambda event, payload: self.events.put(
                    ("voice_pipeline", (event, payload))
                ),
            )
        except Exception as error:
            self.events.put(("voice_pipeline", ("error", str(error))))

    def _handle_voice_pipeline_event(self, event: str, payload) -> None:
        if event == "transcript":
            self.handle_voice_transcription(str(payload))
        elif event == "tool_call":
            self._add_tool_call(payload)
        elif event == "response_started":
            self.busy = True
            self.response_cancel_requested = False
            self.current_turn_mode = "voice"
            self.status_var.set("RIKO is replying aloud…")
            self.voice_status_label.configure(text="RIKO is replying aloud…")
            self._refresh_send_button()
        elif event == "token":
            self.current_reply += str(payload)
            self._set_reply_content(self.current_reply or "…")
        elif event == "status":
            self.status_var.set(str(payload))
        elif event == "response_cancelled":
            self.response_cancel_requested = True
            self.status_var.set(str(payload))
            self.voice_status_label.configure(text=str(payload))
            self._refresh_send_button()
        elif event == "interruption_command":
            self.status_var.set(f'Heard “{payload}”. Listening for your next request.')
            self.voice_status_label.configure(text="Stopped. Listening for you.")
        elif event == "listening":
            self.busy = False
            self.response_cancel_requested = False
            self.status_var.set("Listening… speak naturally. RIKO will detect when you finish.")
            self.voice_status_label.configure(text="Listening… speak naturally.")
            self._refresh_send_button()
        elif event == "listen_error":
            self.status_var.set(f"Microphone/STT issue: {payload}. Retrying…")
            self.voice_status_label.configure(text=f"Microphone issue; retrying: {payload}")
        elif event == "turn_done":
            self.busy = False
            self.response_cancel_requested = False
            self._refresh_send_button()
        elif event == "turn_error":
            if not self.current_reply and self.active_reply_label is not None:
                self._set_reply_content("RIKO couldn't complete that reply.")
            self.status_var.set(str(payload))
            self.busy = False
            self.response_cancel_requested = False
            self._refresh_send_button()
        elif event == "warning":
            self.status_var.set(str(payload))
        elif event == "error":
            self.status_var.set(f"Voice Chat could not start: {payload}")
            self.voice_status_label.configure(text=f"Voice chat could not start: {payload}")
        elif event == "ended":
            restart_voice = (
                self.voice_restart_after_stop and self.mode_var.get() == "voice"
            )
            self.busy = False
            self.response_cancel_requested = False
            self.voice_session_active = False
            self.voice_stopping = False
            self.voice_restart_after_stop = False
            self.voice_session = None
            self.voice_thread = None
            self.active_conversation = None
            self._refresh_send_button()
            for button in self.mode_buttons.values():
                button.configure(state="normal")
            if restart_voice:
                self.voice_status_label.configure(text="Restarting voice chat…")
                self.status_var.set("Restarting RIKO's voice pipeline…")
            else:
                self.voice_status_label.configure(text="Voice chat stopped. Select Voice to start again.")
                self.status_var.set("Voice chat stopped. Ready when you are.")
            self._focus_composer()
            if restart_voice:
                self.root.after(0, self.start_voice_session)

    def _drain_events(self) -> None:
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if event == "voice_pipeline":
                pipeline_event, pipeline_payload = payload
                self._handle_voice_pipeline_event(pipeline_event, pipeline_payload)
            elif event == "mic_partial":
                self._apply_mic_partial(str(payload))
            elif event == "mic_recording_done":
                self._finish_mic_recording(payload)
            elif event == "read_aloud_done":
                self._finish_read_aloud(payload)
            elif event == "token":
                self.current_reply += str(payload)
                self._set_reply_content(self.current_reply or "…")
            elif event == "status":
                self.status_var.set(str(payload))
            elif event == "tool_call":
                self._add_tool_call(payload)
            elif event == "done":
                was_cancelled = self.response_cancel_requested
                self.busy = False
                self.response_cancel_requested = False
                if was_cancelled and not self.current_reply and self.active_reply_label is not None:
                    self._set_reply_content("Response stopped.")
                self.active_conversation = None
                self._refresh_send_button()
                self._refresh_mic_button()
                self._refresh_reply_action_buttons()
                for button in self.mode_buttons.values():
                    button.configure(state="normal")
                self.status_var.set(
                    "Response stopped. You can send another message."
                    if was_cancelled
                    else "Ready when you are."
                )
                self._focus_composer()
            elif event == "error":
                if self.busy and not self.current_reply:
                    if self.active_reply_label is not None:
                        self._set_reply_content("I couldn't complete that request.")
                self.busy = False
                self.response_cancel_requested = False
                self.active_conversation = None
                self._refresh_send_button()
                self._refresh_mic_button()
                self._refresh_reply_action_buttons()
                for button in self.mode_buttons.values():
                    button.configure(state="normal")
                self.status_var.set(str(payload))
            elif event == "runtime":
                available, model_ready = payload
                if available and model_ready:
                    self.runtime_state.configure(text="READY", fg=COLORS["success"])
                    self.runtime_dot.configure(fg=COLORS["success"])
                    self.runtime_var.set("Ollama and the chat model are ready.")
                elif available:
                    self.runtime_state.configure(text="MODEL NEEDED", fg=COLORS["warning"])
                    self.runtime_dot.configure(fg=COLORS["warning"])
                    self.runtime_var.set(f"Ollama is running. Download {MODEL_NAME} to chat.")
                else:
                    self.runtime_state.configure(text="OFFLINE", fg=COLORS["danger"])
                    self.runtime_dot.configure(fg=COLORS["danger"])
                    self.runtime_var.set("Start Ollama, then select Refresh status.")
            elif event == "voices":
                values, error = payload
                self.voice_values = list(values)
                if self.settings_window is not None and self.settings_window.winfo_exists():
                    combo = getattr(self, "voice_combo", None)
                    if combo is not None:
                        combo.configure(values=self.voice_values or [self.settings.get_tts_voice()])
                        if self.voice_var.get() not in self.voice_values:
                            self.voice_var.set(self.settings.get_tts_voice())
                    self.voice_note.configure(
                        text=(f"Voice list unavailable: {error}" if error else "Used for spoken replies."),
                        fg=COLORS["warning"] if error else COLORS["quiet"],
                    )
            elif event == "settings_saved":
                self.persona_badge.configure(text=self._persona_name())
                self._refresh_reply_action_buttons()
                if not self.settings.get_text_to_voice_enabled() and self.read_aloud_active:
                    self._stop_read_aloud()
                if self.voice_session is not None:
                    try:
                        self.voice_session.update_runtime_preferences()
                    except Exception as error:
                        self.status_var.set(f"Preferences saved; voice update failed: {error}")
                    else:
                        self.status_var.set(
                            "Preferences saved. Style applies to the next reply; voice settings apply to the next phrase."
                        )
                else:
                    self.status_var.set(
                        "Preferences saved. Style applies to the next reply."
                    )
        self.root.after(60, self._drain_events)

    def _check_runtime(self) -> None:
        def check() -> None:
            try:
                with urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as response:
                    data = json.loads(response.read().decode("utf-8"))
                names = {
                    model.get("name")
                    for model in data.get("models", [])
                    if isinstance(model, dict)
                }
                model_ready = MODEL_NAME in names or f"{MODEL_NAME}:latest" in names
                self.events.put(("runtime", (True, model_ready)))
            except (URLError, TimeoutError, OSError, json.JSONDecodeError):
                self.events.put(("runtime", (False, False)))

        threading.Thread(target=check, name="riko-runtime-check", daemon=True).start()
        self.root.after(15_000, self._check_runtime)

    def open_settings(self) -> None:
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        window = tk.Toplevel(self.root)
        self.settings_window = window
        window.title("RIKO preferences")
        window.configure(bg=COLORS["background"])
        window.transient(self.root)
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", window.destroy)
        body = tk.Frame(window, bg=COLORS["background"])
        body.pack(fill="both", expand=True, padx=26, pady=23)
        tk.Label(
            body,
            text="MAKE IT YOURS",
            bg=COLORS["background"],
            fg=COLORS["accent"],
            font=(UI_FONT_FAMILY, 8, "bold"),
        ).pack(anchor="w")
        tk.Label(
            body,
            text="A few preferences",
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=(UI_FONT_FAMILY, 20, "bold"),
        ).pack(anchor="w", pady=(5, 4))
        tk.Label(
            body,
            text="Choose the conversation style and voice that feel right to you.",
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=(UI_FONT_FAMILY, 9),
        ).pack(anchor="w", pady=(0, 18))
        tk.Label(
            body,
            text="You can save preferences while RIKO is replying. Style applies to the next reply; voice changes apply to the next spoken phrase.",
            bg=COLORS["background"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 8),
            justify="left",
            wraplength=420,
        ).pack(anchor="w", pady=(0, 16))

        self.text_to_voice_var = tk.BooleanVar(
            value=self.settings.get_text_to_voice_enabled(),
        )
        tk.Checkbutton(
            body,
            text="Enable text in, voice out",
            variable=self.text_to_voice_var,
            bg=COLORS["background"],
            fg=COLORS["text"],
            activebackground=COLORS["background"],
            activeforeground=COLORS["text"],
            selectcolor=COLORS["panel_lighter"],
            font=(UI_FONT_FAMILY, 9, "bold"),
            anchor="w",
            highlightthickness=0,
        ).pack(fill="x", pady=(0, 3))
        tk.Label(
            body,
            text="Shows a Read aloud action for text replies. Speech is only played when you choose it.",
            bg=COLORS["background"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 8),
            justify="left",
            wraplength=420,
        ).pack(anchor="w", pady=(0, 14))

        cache_row = tk.Frame(body, bg=COLORS["background"])
        cache_row.pack(fill="x", pady=(0, 2))
        self.tts_cache_var = tk.BooleanVar(
            value=self.settings.get_tts_cache_enabled(),
        )
        tk.Checkbutton(
            cache_row,
            text="Cache Read aloud audio locally",
            variable=self.tts_cache_var,
            bg=COLORS["background"],
            fg=COLORS["text"],
            activebackground=COLORS["background"],
            activeforeground=COLORS["text"],
            selectcolor=COLORS["panel_lighter"],
            font=(UI_FONT_FAMILY, 9, "bold"),
            anchor="w",
            highlightthickness=0,
        ).pack(side="left", fill="x", expand=True)
        self._button(
            cache_row,
            "Clear cache",
            self.clear_audio_cache,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            padx=10,
            pady=5,
        ).pack(side="right")
        tk.Label(
            body,
            text="Off by default. When enabled, repeated Read aloud phrases reuse local audio files. Cache is limited to 128 MB and can be cleared here.",
            bg=COLORS["background"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 8),
            justify="left",
            wraplength=420,
        ).pack(anchor="w", pady=(0, 14))

        self._button(
            body,
            "Tune RIKO's personality",
            self.open_behavior_preferences,
            bg=COLORS["panel"],
            fg=COLORS["text"],
            padx=14,
            pady=9,
        ).pack(fill="x", pady=(0, 14))

        personas = self.prompts.list_personas()
        self.persona_choice = tk.StringVar(value=self.settings.get_persona())
        self._field_label(body, "Conversation style")
        persona_combo = ttk.Combobox(
            body,
            textvariable=self.persona_choice,
            values=[persona["id"] for persona in personas],
            state="readonly",
            style="Riko.TCombobox",
            width=38,
        )
        persona_combo.pack(fill="x", pady=(0, 4))
        self.persona_description = tk.Label(
            body,
            text="",
            bg=COLORS["background"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 8),
            anchor="w",
        )
        self.persona_description.pack(fill="x", pady=(0, 14))

        def update_description(_event=None):
            selected = self.persona_choice.get()
            item = next((p for p in personas if p["id"] == selected), {})
            self.persona_description.configure(text=item.get("description", ""))

        persona_combo.bind("<<ComboboxSelected>>", update_description)
        update_description()

        self._field_label(body, "Kokoro voice")
        self.voice_var = tk.StringVar(value=self.settings.get_tts_voice())
        self.voice_combo = ttk.Combobox(
            body,
            textvariable=self.voice_var,
            values=self.voice_values or [self.settings.get_tts_voice()],
            state="readonly",
            style="Riko.TCombobox",
            width=38,
        )
        self.voice_combo.pack(fill="x", pady=(0, 4))
        self.voice_note = tk.Label(
            body,
            text="Loading available Kokoro voices…",
            bg=COLORS["background"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 8),
            anchor="w",
        )
        self.voice_note.pack(fill="x", pady=(0, 14))
        threading.Thread(target=self._load_voice_list, daemon=True).start()

        tts = self.settings.get_tts_settings()
        self.speed_var = tk.DoubleVar(value=float(tts.get("speed", 1.0)))
        speed_row = tk.Frame(body, bg=COLORS["background"])
        speed_row.pack(fill="x")
        self._field_label(speed_row, "Speaking pace")
        self.speed_label = tk.Label(
            speed_row,
            text=f"{self.speed_var.get():.2f}×",
            bg=COLORS["background"],
            fg=COLORS["accent"],
            font=(UI_FONT_FAMILY, 9, "bold"),
        )
        self.speed_label.pack(side="right")
        tk.Scale(
            body,
            variable=self.speed_var,
            from_=0.25,
            to=4.0,
            resolution=0.05,
            orient="horizontal",
            showvalue=False,
            bg=COLORS["background"],
            fg=COLORS["text"],
            troughcolor=COLORS["panel_lighter"],
            activebackground=COLORS["accent"],
            highlightthickness=0,
            command=lambda value: self.speed_label.configure(text=f"{float(value):.2f}×"),
        ).pack(fill="x", pady=(4, 16))

        buttons = tk.Frame(body, bg=COLORS["background"])
        buttons.pack(fill="x")
        self._button(
            buttons,
            "Save preferences",
            self.save_settings,
            bg=COLORS["accent"],
            fg="#17131f",
            padx=15,
            pady=10,
            font=(UI_FONT_FAMILY, 9, "bold"),
        ).pack(side="right")
        self._button(
            buttons,
            "Close",
            window.destroy,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            padx=15,
            pady=10,
        ).pack(side="right", padx=(0, 8))
        self._schedule_zoom()

    @staticmethod
    def _field_label(parent, text: str) -> None:
        tk.Label(
            parent,
            text=text,
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=(UI_FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

    def _load_voice_list(self) -> None:
        try:
            from audio.kokoro.voice_registry import KokoroVoiceRegistry

            voices = KokoroVoiceRegistry().list_voices()
            self.events.put(("voices", (voices, "")))
        except Exception as error:
            self.events.put(("voices", ([], str(error))))

    def save_settings(self) -> None:
        try:
            self.prompts.select_persona(self.persona_choice.get())
            voice = self.voice_var.get().strip()
            if self.voice_values and voice not in self.voice_values:
                raise ValueError("Choose one of the available Kokoro voices.")
            if self.voice_values:
                self.settings.set_tts_voice(voice, self.voice_values)
            self.settings.set_tts_speed(float(self.speed_var.get()))
            self.settings.set_text_to_voice_enabled(
                bool(self.text_to_voice_var.get())
            )
            self.settings.set_tts_cache_enabled(bool(self.tts_cache_var.get()))
        except (ValueError, OSError) as error:
            messagebox.showerror("Could not save preferences", str(error), parent=self.settings_window)
            return
        self.events.put(("settings_saved", None))

    def clear_audio_cache(self) -> None:
        if not messagebox.askyesno(
            "Clear cached speech",
            "Delete RIKO's locally cached Read aloud audio? This cannot be undone.",
            parent=self.settings_window,
        ):
            return
        try:
            from audio.kokoro.tts import DEFAULT_CACHE, KokoroTTS

            removed = KokoroTTS.clear_cache(DEFAULT_CACHE)
            messagebox.showinfo(
                "Speech cache cleared",
                f"Removed {removed} cached audio file(s).",
                parent=self.settings_window,
            )
        except OSError as error:
            messagebox.showerror(
                "Could not clear speech cache",
                str(error),
                parent=self.settings_window,
            )

    def open_behavior_preferences(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("RIKO personality preferences")
        window.configure(bg=COLORS["background"])
        window.transient(self.root)
        window.geometry("560x690")
        window.minsize(500, 560)

        header = tk.Frame(window, bg=COLORS["background"])
        header.pack(fill="x", padx=24, pady=(20, 8))
        tk.Label(
            header,
            text="TUNE RIKO'S STYLE",
            bg=COLORS["background"],
            fg=COLORS["accent"],
            font=(UI_FONT_FAMILY, 8, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="A little more you",
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=(UI_FONT_FAMILY, 19, "bold"),
        ).pack(anchor="w", pady=(4, 2))
        tk.Label(
            header,
            text="These sliders shape the next reply. They never override your current request, and serious conversations stay grounded.",
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=(UI_FONT_FAMILY, 9),
            justify="left",
            wraplength=500,
        ).pack(anchor="w")

        scroll_frame = tk.Frame(window, bg=COLORS["background"])
        scroll_frame.pack(fill="both", expand=True, padx=18, pady=(8, 4))
        canvas = tk.Canvas(
            scroll_frame,
            bg=COLORS["background"],
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        content = tk.Frame(canvas, bg=COLORS["background"])
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(content_window, width=event.width),
        )
        canvas.bind(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(-int(event.delta / 120), "units"),
        )
        canvas.bind(
            "<Button-4>", lambda _event: canvas.yview_scroll(-1, "units")
        )
        canvas.bind(
            "<Button-5>", lambda _event: canvas.yview_scroll(1, "units")
        )

        try:
            values = self.prompts.get_behavior_preferences()
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not load personality settings", str(error), parent=window)
            window.destroy()
            return

        slider_vars = {}
        slider_labels = {}
        for key, _section, label in BEHAVIOR_CONTROLS:
            row = tk.Frame(
                content,
                bg=COLORS["panel"],
                highlightthickness=1,
                highlightbackground=COLORS["border"],
            )
            row.pack(fill="x", padx=5, pady=5)
            title_row = tk.Frame(row, bg=COLORS["panel"])
            title_row.pack(fill="x", padx=12, pady=(8, 0))
            tk.Label(
                title_row,
                text=label,
                bg=COLORS["panel"],
                fg=COLORS["text"],
                font=(UI_FONT_FAMILY, 9, "bold"),
                anchor="w",
            ).pack(side="left", fill="x", expand=True)
            value_label = tk.Label(
                title_row,
                text=f"{values[key]}/10",
                bg=COLORS["panel"],
                fg=COLORS["accent"],
                font=(UI_FONT_FAMILY, 8, "bold"),
                width=6,
                anchor="e",
            )
            value_label.pack(side="right")
            slider_labels[key] = value_label
            variable = tk.IntVar(value=values[key])
            slider_vars[key] = variable
            tk.Scale(
                row,
                variable=variable,
                from_=0,
                to=10,
                resolution=1,
                orient="horizontal",
                showvalue=False,
                bg=COLORS["panel"],
                fg=COLORS["muted"],
                troughcolor=COLORS["panel_lighter"],
                activebackground=COLORS["accent"],
                highlightthickness=0,
                command=lambda value, label=value_label: label.configure(
                    text=f"{int(float(value))}/10"
                ),
            ).pack(fill="x", padx=8, pady=(0, 2))
            scale_hint = tk.Frame(row, bg=COLORS["panel"])
            scale_hint.pack(fill="x", padx=12, pady=(0, 7))
            tk.Label(
                scale_hint,
                text="Subtle",
                bg=COLORS["panel"],
                fg=COLORS["quiet"],
                font=(UI_FONT_FAMILY, 7),
            ).pack(side="left")
            tk.Label(
                scale_hint,
                text="Strong",
                bg=COLORS["panel"],
                fg=COLORS["quiet"],
                font=(UI_FONT_FAMILY, 7),
            ).pack(side="right")

        tk.Label(
            content,
            text="Response style",
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=(UI_FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(fill="x", padx=7, pady=(14, 6))
        style_by_label = {"Keep current style": values["response_style"]}
        style_by_label.update(RESPONSE_STYLE_OPTIONS)
        current_label = next(
            (
                label
                for label, style in RESPONSE_STYLE_OPTIONS.items()
                if style == values["response_style"]
            ),
            "Keep current style",
        )
        style_var = tk.StringVar(value=current_label)
        style_combo = ttk.Combobox(
            content,
            textvariable=style_var,
            values=list(style_by_label),
            state="readonly",
            style="Riko.TCombobox",
        )
        style_combo.pack(fill="x", padx=7, pady=(0, 5))

        actions = tk.Frame(window, bg=COLORS["background"])
        actions.pack(fill="x", padx=24, pady=(6, 18))

        def reset_to_persona() -> None:
            try:
                self.prompts.reset_behavior_preferences()
                refreshed = self.prompts.get_behavior_preferences()
                for key, variable in slider_vars.items():
                    variable.set(refreshed[key])
                    slider_labels[key].configure(text=f"{refreshed[key]}/10")
                style_var.set(next(
                    (label for label, style in RESPONSE_STYLE_OPTIONS.items()
                     if style == refreshed["response_style"]),
                    "Keep current style",
                ))
                style_by_label["Keep current style"] = refreshed["response_style"]
                self.status_var.set("Personality controls reset to the selected persona.")
            except (OSError, ValueError) as error:
                messagebox.showerror("Could not reset personality", str(error), parent=window)

        def save_behavior() -> None:
            selected_style = style_var.get()
            preferences = {key: variable.get() for key, variable in slider_vars.items()}
            preferences["response_style"] = style_by_label[selected_style]
            try:
                self.prompts.save_behavior_preferences(preferences)
            except (OSError, TypeError, ValueError) as error:
                messagebox.showerror("Could not save personality", str(error), parent=window)
                return
            self.status_var.set("Personality preferences saved for the next reply.")
            window.destroy()

        self._button(
            actions,
            "Reset to persona",
            reset_to_persona,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            padx=12,
            pady=9,
        ).pack(side="left")
        self._button(
            actions,
            "Save style",
            save_behavior,
            bg=COLORS["accent"],
            fg="#17131f",
            padx=16,
            pady=9,
            font=(UI_FONT_FAMILY, 9, "bold"),
        ).pack(side="right")
        self._schedule_zoom()

    def open_profile(self) -> None:
        try:
            profiles = self.prompts.list_profiles()
            profile_id = self.settings.get_profile()
            if not any(item["id"] == profile_id for item in profiles):
                profile_id = "user"
                self.prompts.select_profile(profile_id)
            profile = self.prompts.load_profile(profile_id)
        except Exception as error:
            messagebox.showerror("Could not open profile", str(error), parent=self.root)
            return

        window = tk.Toplevel(self.root)
        window.title("Your RIKO profile")
        window.configure(bg=COLORS["background"])
        window.transient(self.root)
        window.geometry("620x760")
        window.minsize(560, 640)
        window.resizable(True, True)
        body = tk.Frame(window, bg=COLORS["background"])
        body.pack(fill="both", expand=True, padx=25, pady=22)
        tk.Label(
            body,
            text="JUST ENOUGH CONTEXT",
            bg=COLORS["background"],
            fg=COLORS["accent"],
            font=(UI_FONT_FAMILY, 8, "bold"),
        ).pack(anchor="w")
        tk.Label(
            body,
            text="Profile context",
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=(UI_FONT_FAMILY, 20, "bold"),
        ).pack(anchor="w", pady=(5, 4))
        tk.Label(
            body,
            text="Saved on this computer. Riko uses these details when they help.",
            bg=COLORS["background"],
            fg=COLORS["muted"],
            font=(UI_FONT_FAMILY, 9),
        ).pack(anchor="w", pady=(0, 16))

        self._field_label(body, "Profile context used in the system prompt")
        profile_labels = {
            f"{item['name']} ({item['id']})": item["id"]
            for item in profiles
        }
        profiles_by_id = {item["id"]: item for item in profiles}
        active_profile_id = profile_id
        active_profile_label = next(
            (
                label
                for label, profile_id in profile_labels.items()
                if profile_id == active_profile_id
            ),
            next(label for label, profile_id in profile_labels.items() if profile_id == "user"),
        )
        active_profile_var = tk.StringVar(value=active_profile_label)
        profile_row = tk.Frame(body, bg=COLORS["background"])
        profile_row.pack(fill="x", pady=(0, 4))
        active_profile_combo = ttk.Combobox(
            profile_row,
            textvariable=active_profile_var,
            values=list(profile_labels),
            state="readonly",
            style="Riko.TCombobox",
        )
        active_profile_combo.pack(side="left", fill="x", expand=True)
        new_profile_button = self._button(
            profile_row,
            "＋ New",
            lambda: create_new_profile(),
            bg=COLORS["panel"],
            fg=COLORS["accent"],
            padx=11,
            pady=7,
            font=(UI_FONT_FAMILY, 8, "bold"),
        )
        new_profile_button.pack(side="left", padx=(8, 0))
        profile_description = tk.Label(
            body,
            text="This context is inserted through the existing system-prompt profile field.",
            bg=COLORS["background"],
            fg=COLORS["quiet"],
            font=(UI_FONT_FAMILY, 8),
            anchor="w",
        )
        profile_description.pack(fill="x", pady=(0, 14))

        profile_scroll_area = tk.Frame(body, bg=COLORS["background"])
        profile_scroll_area.pack(fill="both", expand=True)
        profile_canvas = tk.Canvas(
            profile_scroll_area,
            bg=COLORS["background"],
            highlightthickness=0,
            borderwidth=0,
        )
        profile_scrollbar = ttk.Scrollbar(
            profile_scroll_area,
            orient="vertical",
            command=profile_canvas.yview,
        )
        profile_canvas.configure(yscrollcommand=profile_scrollbar.set)
        profile_canvas.pack(side="left", fill="both", expand=True)
        profile_scrollbar.pack(side="right", fill="y")
        profile_content = tk.Frame(profile_canvas, bg=COLORS["background"])
        profile_content_window = profile_canvas.create_window(
            (0, 0), window=profile_content, anchor="nw"
        )
        profile_content.bind(
            "<Configure>",
            lambda _event: profile_canvas.configure(
                scrollregion=profile_canvas.bbox("all")
            ),
        )
        profile_canvas.bind(
            "<Configure>",
            lambda event: profile_canvas.itemconfigure(
                profile_content_window, width=event.width
            ),
        )

        def select_profile(_event=None):
            selected_id = profile_labels.get(active_profile_var.get())
            if selected_id is None:
                return
            try:
                self.prompts.select_profile(selected_id)
            except (OSError, ValueError) as error:
                messagebox.showerror("Could not select profile", str(error), parent=window)
                return
            selected = profiles_by_id[selected_id]
            description = selected.get("description", "")
            profile_description.configure(
                text=(
                    f"{description} Profile data stays local and is used only "
                    "when relevant."
                )
            )
            self.status_var.set(f"Profile context set to {selected['name']}.")
            update_profile_fields(selected_id)

        active_profile_combo.bind("<<ComboboxSelected>>", select_profile)

        tk.Label(
            profile_content,
            text="Profile details",
            bg=COLORS["background"],
            fg=COLORS["text"],
            font=(UI_FONT_FAMILY, 11, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        identity = profile.get("identity", {})
        preferences = profile.get("learning_preferences", {})
        communication = profile.get("communication_preferences", {})
        if not isinstance(identity, dict):
            identity = {}
        if not isinstance(preferences, dict):
            preferences = {}
        if not isinstance(communication, dict):
            communication = {}
        values = {
            "Name": identity.get("preferred_name", ""),
            "Role or occupation": identity.get("role", ""),
            "Interests (comma separated)": ", ".join(profile.get("interests", [])),
            "Current goals (comma separated)": ", ".join(profile.get("current_goals", [])),
            "Explanation style": preferences.get("explanation_style", ""),
            "Learning pace": preferences.get("pace", ""),
            "Response language": communication.get("response_language", ""),
            "Response length (concise/balanced/detailed)": communication.get("response_length", "balanced"),
            "Communication tone": communication.get("tone", ""),
        }
        fields: dict[str, tk.Entry] = {}
        for label, value in values.items():
            self._field_label(profile_content, label)
            entry = tk.Entry(
                profile_content,
                bg=COLORS["panel_lighter"],
                fg=COLORS["text"],
                insertbackground=COLORS["accent"],
                relief="flat",
                highlightthickness=1,
                highlightbackground=COLORS["border"],
                highlightcolor=COLORS["accent"],
                font=(UI_FONT_FAMILY, 9),
            )
            entry.insert(0, str(value))
            entry.pack(fill="x", pady=(0, 11), ipady=7, padx=1)
            fields[label] = entry

        code_var = tk.BooleanVar(value=preferences.get("code_explanations") is not False)
        code_checkbox = tk.Checkbutton(
            profile_content,
            text="Include code explanations when discussing code",
            variable=code_var,
            bg=COLORS["background"],
            fg=COLORS["muted"],
            activebackground=COLORS["background"],
            activeforeground=COLORS["text"],
            selectcolor=COLORS["panel_lighter"],
            font=(UI_FONT_FAMILY, 9),
        )
        code_checkbox.pack(anchor="w", pady=(0, 15))

        save_button = None

        def update_profile_fields(selected_id: str) -> None:
            selected_profile = self.prompts.load_profile(selected_id)
            selected_identity = selected_profile["identity"]
            selected_learning = selected_profile["learning_preferences"]
            selected_communication = selected_profile["communication_preferences"]
            selected_values = {
                "Name": selected_identity["preferred_name"],
                "Role or occupation": selected_identity["role"],
                "Interests (comma separated)": ", ".join(selected_profile["interests"]),
                "Current goals (comma separated)": ", ".join(selected_profile["current_goals"]),
                "Explanation style": selected_learning["explanation_style"],
                "Learning pace": selected_learning["pace"],
                "Response language": selected_communication["response_language"],
                "Response length (concise/balanced/detailed)": selected_communication["response_length"],
                "Communication tone": selected_communication["tone"],
            }
            for label, value in selected_values.items():
                field = fields[label]
                field.configure(state="normal")
                field.delete(0, "end")
                field.insert(0, str(value))

            code_var.set(selected_learning["code_explanations"])
            is_bundled = profiles_by_id[selected_id]["source"] == "bundled"
            field_state = "disabled" if is_bundled else "normal"
            for field in fields.values():
                field.configure(state=field_state)
            code_checkbox.configure(state=field_state)
            if save_button is not None:
                save_button.configure(
                    text=("Copy to personal profile" if is_bundled else "Save profile")
                )
            selected_description = profiles_by_id[selected_id].get("description", "")
            profile_description.configure(
                text=(
                    f"{selected_description} Profile data stays local and is used "
                    "only when relevant."
                )
            )

        def refresh_profile_options(selected_id: str) -> None:
            nonlocal profiles, profiles_by_id, profile_labels
            profiles = self.prompts.list_profiles()
            profiles_by_id = {item["id"]: item for item in profiles}
            profile_labels = {
                f"{item['name']} ({item['id']})": item["id"]
                for item in profiles
            }
            active_profile_combo.configure(values=list(profile_labels))
            display = next(
                label for label, item_id in profile_labels.items()
                if item_id == selected_id
            )
            active_profile_var.set(display)

        def create_new_profile() -> None:
            profile_id = simpledialog.askstring(
                "Create a profile",
                "Choose a short profile ID (letters, numbers, _ or -):",
                parent=window,
            )
            if profile_id is None:
                return
            profile_id = profile_id.strip()
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", profile_id):
                messagebox.showerror(
                    "Invalid profile ID",
                    "Use 1–40 letters, numbers, underscores, or hyphens.",
                    parent=window,
                )
                return
            if profile_id in profiles_by_id:
                messagebox.showerror(
                    "Profile already exists",
                    "Choose a different ID. Existing profile data was not changed.",
                    parent=window,
                )
                return
            try:
                path = self.prompts.profile_storage_path(profile_id)
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
                temp.write_text(
                    json.dumps(default_profile(), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                if path.exists():
                    temp.unlink(missing_ok=True)
                    raise FileExistsError(f"Profile already exists: {profile_id}")
                temp.replace(path)
                self.prompts.select_profile(profile_id)
                refresh_profile_options(profile_id)
                update_profile_fields(profile_id)
                self.status_var.set(f"Created local profile: {profile_id}.")
            except (OSError, ValueError) as error:
                messagebox.showerror("Could not create profile", str(error), parent=window)

        def save_profile() -> None:
            try:
                selected_id = profile_labels.get(active_profile_var.get())
                if selected_id is None:
                    raise ValueError("Select a valid profile first.")
                selected_profile = self.prompts.load_profile(selected_id)
                selected_identity = selected_profile["identity"]
                selected_preferences = selected_profile["learning_preferences"]
                selected_communication = selected_profile["communication_preferences"]
                updated = dict(selected_profile)
                updated_identity = dict(selected_identity)
                updated_identity["preferred_name"] = fields["Name"].get().strip()
                updated_identity["role"] = fields["Role or occupation"].get().strip()
                updated_preferences = dict(selected_preferences)
                updated_preferences["explanation_style"] = fields["Explanation style"].get().strip()
                updated_preferences["pace"] = fields["Learning pace"].get().strip()
                updated_preferences["code_explanations"] = bool(code_var.get())
                updated_communication = dict(selected_communication)
                updated_communication["response_language"] = fields["Response language"].get().strip()
                updated_communication["response_length"] = fields["Response length (concise/balanced/detailed)"].get().strip()
                updated_communication["tone"] = fields["Communication tone"].get().strip()
                updated["identity"] = updated_identity
                updated["interests"] = self._parse_profile_list(fields["Interests (comma separated)"].get())
                updated["current_goals"] = self._parse_profile_list(fields["Current goals (comma separated)"].get())
                for key, limit in (("preferred_name", 80), ("role", 120)):
                    if len(updated_identity[key]) > limit:
                        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be {limit} characters or shorter.")
                for key, limit in (("explanation_style", 160), ("pace", 120)):
                    if len(updated_preferences[key]) > limit:
                        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be {limit} characters or shorter.")
                updated["learning_preferences"] = updated_preferences
                updated["communication_preferences"] = updated_communication
                updated = normalize_profile(updated)

                bundled = profiles_by_id[selected_id]["source"] == "bundled"
                target_id = "user" if bundled else selected_id
                path = self.prompts.profile_storage_path(target_id)
                if bundled and path.exists() and not messagebox.askyesno(
                    "Replace personal profile?",
                    "Copying this preset will replace your saved personal profile. Continue?",
                    parent=window,
                ):
                    return
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_name(f".{path.name}.{threading.get_ident()}.tmp")
                temp.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                temp.replace(path)
                if target_id != selected_id:
                    self.prompts.select_profile(target_id)
                    refresh_profile_options(target_id)
                    update_profile_fields(target_id)
            except (OSError, ValueError, TypeError) as error:
                messagebox.showerror("Could not save profile", str(error), parent=window)
                return
            window.destroy()
            self.status_var.set(f"Profile saved locally: {target_id}.")

        actions = tk.Frame(profile_content, bg=COLORS["background"])
        actions.pack(fill="x")
        save_button = self._button(
            actions,
            "Save profile",
            save_profile,
            bg=COLORS["accent"],
            fg="#17131f",
            padx=15,
            pady=10,
            font=(UI_FONT_FAMILY, 9, "bold"),
        )
        save_button.pack(side="right")
        self._button(
            actions,
            "Close",
            window.destroy,
            bg=COLORS["panel"],
            fg=COLORS["muted"],
            padx=15,
            pady=10,
        ).pack(side="right", padx=(0, 8))
        update_profile_fields(active_profile_id)
        self._schedule_zoom()

    @staticmethod
    def _parse_profile_list(value: str) -> list[str]:
        result = [part.strip() for part in value.split(",") if part.strip()]
        if len(result) > 20:
            raise ValueError("Use no more than 20 interests or goals in each field.")
        if any(len(part) > 120 for part in result):
            raise ValueError("Each interest or goal must be 120 characters or shorter.")
        return result

    def close(self) -> None:
        if self.mic_stop_event is not None:
            self.mic_stop_event.set()
        if self.read_aloud_active:
            self._stop_read_aloud()
        if self.voice_session is not None:
            self.voice_session.stop()
        self.root.destroy()


def main() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise SystemExit(
            "RIKO's desktop window could not start. On Linux, install the "
            "python3-tk package and make sure a graphical desktop session is available.\n"
            f"Details: {error}"
        ) from error
    RikoDesktop(root)
    root.mainloop()


if __name__ == "__main__":
    main()
