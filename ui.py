import re
import math
from datetime import datetime
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageDraw
from typing import Callable, List, Dict, Any

ctk.set_appearance_mode("Dark")


class IconFactory:
    """Generates crisp 4x-supersampled anti-aliased vector icons in memory using Pillow."""

    @staticmethod
    def _canvas(size: int = 96):
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        return img, ImageDraw.Draw(img), size

    @staticmethod
    def _to_ctk(img: Image.Image, display_size=(18, 18)) -> ctk.CTkImage:
        smooth = img.resize((display_size[0] * 2, display_size[1] * 2), Image.LANCZOS)
        return ctk.CTkImage(light_image=smooth, dark_image=smooth, size=display_size)

    @classmethod
    def screen_reticle(cls, color="#ffffff", accent="#a5f3fc", size=(18, 18)) -> ctk.CTkImage:
        img, d, s = cls._canvas()
        d.rounded_rectangle((10, 14, s - 10, s - 26), radius=10, outline=color, width=6)
        d.line((s // 2, s - 26, s // 2, s - 12), fill=color, width=6)
        d.line((28, s - 12, s - 28, s - 12), fill=color, width=6)
        cx, cy = s // 2, (s - 12) // 2
        d.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), outline=accent, width=5)
        d.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=accent)
        return cls._to_ctk(img, size)

    @classmethod
    def send_bolt(cls, color="#ffffff", size=(18, 18)) -> ctk.CTkImage:
        img, d, s = cls._canvas()
        pts = [(14, 46), (82, 14), (54, 82), (42, 54)]
        d.polygon(pts, fill=color)
        return cls._to_ctk(img, size)

    @classmethod
    def mic(cls, color="#10b981", size=(18, 18)) -> ctk.CTkImage:
        img, d, s = cls._canvas()
        d.rounded_rectangle((34, 12, 62, 54), radius=14, fill=color)
        d.arc((22, 26, 74, 68), start=0, end=180, fill=color, width=6)
        d.line((48, 68, 48, 84), fill=color, width=6)
        d.line((32, 84, 64, 84), fill=color, width=6)
        return cls._to_ctk(img, size)

    @classmethod
    def stop_square(cls, color="#ef4444", size=(18, 18)) -> ctk.CTkImage:
        img, d, s = cls._canvas()
        d.rounded_rectangle((14, 14, s - 14, s - 14), radius=16, outline=color, width=6)
        d.rounded_rectangle((30, 30, s - 30, s - 30), radius=6, fill=color)
        return cls._to_ctk(img, size)

    @classmethod
    def tasks_board(cls, color="#818cf8", size=(16, 16)) -> ctk.CTkImage:
        img, d, s = cls._canvas()
        d.rounded_rectangle((18, 16, s - 18, s - 12), radius=10, outline=color, width=6)
        d.rounded_rectangle((34, 8, s - 34, 24), radius=6, fill=color)
        d.line((30, 42, s - 30, 42), fill=color, width=6)
        d.line((30, 58, s - 30, 58), fill=color, width=6)
        d.line((30, 74, s - 42, 74), fill=color, width=6)
        return cls._to_ctk(img, size)

    @classmethod
    def memory_chip(cls, color="#c084fc", size=(16, 16)) -> ctk.CTkImage:
        img, d, s = cls._canvas()
        d.rounded_rectangle((24, 24, s - 24, s - 24), radius=10, outline=color, width=6)
        d.rectangle((38, 38, s - 38, s - 38), fill=color)
        for pos in (34, 48, 62):
            d.line((pos, 10, pos, 24), fill=color, width=5)
            d.line((pos, s - 24, pos, s - 10), fill=color, width=5)
            d.line((10, pos, 24, pos), fill=color, width=5)
            d.line((s - 24, pos, s - 10, pos), fill=color, width=5)
        return cls._to_ctk(img, size)

    @classmethod
    def sun_briefing(cls, color="#f59e0b", size=(16, 16)) -> ctk.CTkImage:
        img, d, s = cls._canvas()
        c = s // 2
        d.ellipse((c - 18, c - 18, c + 18, c + 18), fill=color)
        for i in range(8):
            ang = i * (math.pi / 4)
            x1, y1 = c + math.cos(ang) * 26, c + math.sin(ang) * 26
            x2, y2 = c + math.cos(ang) * 38, c + math.sin(ang) * 38
            d.line((x1, y1, x2, y2), fill=color, width=6)
        return cls._to_ctk(img, size)

    @classmethod
    def undo_arrow(cls, color="#38bdf8", size=(16, 16)) -> ctk.CTkImage:
        img, d, s = cls._canvas()
        d.arc((20, 26, s - 16, s - 18), start=200, end=45, fill=color, width=7)
        d.polygon([(14, 44), (36, 24), (38, 48)], fill=color)
        return cls._to_ctk(img, size)

    @classmethod
    def bell(cls, color="#fbbf24", size=(16, 16)) -> ctk.CTkImage:
        img, d, s = cls._canvas()
        d.chord((22, 16, s - 22, s - 16), start=180, end=0, fill=color)
        d.rectangle((22, 48, s - 22, 68), fill=color)
        d.rounded_rectangle((14, 64, s - 14, 74), radius=5, fill=color)
        d.ellipse((40, 74, 56, 88), fill=color)
        return cls._to_ctk(img, size)

    @classmethod
    def pin(cls, color="#a5b4fc", size=(16, 16)) -> ctk.CTkImage:
        img, d, s = cls._canvas()
        d.rounded_rectangle((28, 14, s - 28, 26), radius=6, fill=color)
        d.polygon([(34, 26), (s - 34, 26), (s - 22, 56), (22, 56)], fill=color)
        d.line((48, 56, 48, 86), fill=color, width=6)
        return cls._to_ctk(img, size)

    @classmethod
    def clear_spark(cls, color="#f43f5e", size=(16, 16)) -> ctk.CTkImage:
        img, d, s = cls._canvas()
        d.rounded_rectangle((24, 26, s - 24, s - 14), radius=8, outline=color, width=6)
        d.line((16, 24, s - 16, 24), fill=color, width=6)
        d.line((38, 14, s - 38, 14), fill=color, width=6)
        d.line((40, 40, 40, s - 26), fill=color, width=5)
        d.line((56, 40, 56, s - 26), fill=color, width=5)
        return cls._to_ctk(img, size)


class AtlasUI(ctk.CTk):
    BG_DEEP = "#080a0f"
    BG_MAIN = "#0d1017"
    SURFACE = "#131722"
    CARD_BG = "#181d2a"
    CARD_ELEVATED = "#1f2536"
    BORDER_SUBTLE = "#262d42"
    BORDER_GLOW = "#4f587a"

    ACCENT = "#6366f1"
    ACCENT_BRIGHT = "#818cf8"
    ACCENT_HOVER = "#4f46e5"
    SCREEN_ACCENT = "#06b6d4"
    SCREEN_HOVER = "#0891b2"

    TEXT_MAIN = "#f3f4f6"
    TEXT_SECONDARY = "#cbd5e1"
    TEXT_MUTED = "#94a3b8"

    STATUS_GREEN = "#10b981"
    STATUS_AMBER = "#f59e0b"
    STATUS_RED = "#ef4444"

    USER_BUBBLE = "#232b42"
    ASSISTANT_BUBBLE = "#141824"

    def __deepcopy__(self, memo):
        return self

    def __init__(
        self,
        on_ask_text: Callable[[str], None],
        on_ask_screen: Callable[[str], None],
        on_manual_voice: Callable[[], None],
        on_stop_all: Callable[[], None],
        on_clear_chat: Callable[[], None],
        on_complete_task: Callable[[int], None],
        on_snooze_task: Callable[[int], None],
        on_delete_memory: Callable[[str, str], None],
        on_undo: Callable[[], None],
        on_briefing: Callable[[], None],
        on_toggle_mute: Callable[[bool], None],
        on_toggle_quiet: Callable[[bool], None],
        on_approval_decision: Callable[[str], None],
    ):
        super().__init__()
        self.on_ask_text = on_ask_text
        self.on_ask_screen = on_ask_screen
        self.on_manual_voice = on_manual_voice
        self.on_stop_all = on_stop_all
        self.on_clear_chat = on_clear_chat
        self.on_complete_task = on_complete_task
        self.on_snooze_task = on_snooze_task
        self.on_delete_memory = on_delete_memory
        self.on_undo = on_undo
        self.on_briefing = on_briefing
        self.on_toggle_mute = on_toggle_mute
        self.on_toggle_quiet = on_toggle_quiet
        self.on_approval_decision = on_approval_decision

        self.is_pinned = False
        self.is_muted = False
        self.is_quiet = False
        self.task_panel_visible = False
        self.memory_panel_visible = False

        self._anim_phase = 0.0
        self._state_color = self.STATUS_GREEN
        self._is_active_busy = False
        self._num_bars = 16
        self._target_bars = [0.0] * self._num_bars
        self._current_bars = [0.0] * self._num_bars
        self._action_banner_text = ""

        self.title("ATLAS AI Operator")
        self.geometry("720x850")
        self.minsize(600, 700)
        self.configure(fg_color=self.BG_MAIN)

        self._init_icons()
        self._build_layout()
        self._start_animation_engine()

    def _init_icons(self):
        self.ico_screen = IconFactory.screen_reticle()
        self.ico_send = IconFactory.send_bolt()
        self.ico_mic_on = IconFactory.mic("#10b981")
        self.ico_mic_off = IconFactory.mic("#ef4444")
        self.ico_stop = IconFactory.stop_square()
        self.ico_tasks = IconFactory.tasks_board()
        self.ico_memory = IconFactory.memory_chip()
        self.ico_sun = IconFactory.sun_briefing()
        self.ico_undo = IconFactory.undo_arrow()
        self.ico_bell = IconFactory.bell("#fbbf24")
        self.ico_bell_off = IconFactory.bell("#94a3b8")
        self.ico_pin = IconFactory.pin()
        self.ico_clear = IconFactory.clear_spark()

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # ==========================================
        # 1. TOP COMMAND HEADER HUD
        # ==========================================
        self.header_card = ctk.CTkFrame(
            self,
            fg_color=self.SURFACE,
            corner_radius=16,
            border_width=1,
            border_color=self.BORDER_SUBTLE,
        )
        self.header_card.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))
        self.header_card.grid_columnconfigure(1, weight=1)

        brand_frame = ctk.CTkFrame(self.header_card, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=(12, 8), pady=8, sticky="w")

        self.orb_canvas = tk.Canvas(brand_frame, width=42, height=42, bg=self.SURFACE, highlightthickness=0)
        self.orb_canvas.pack(side="left", padx=(0, 10))

        title_stack = ctk.CTkFrame(brand_frame, fg_color="transparent")
        title_stack.pack(side="left")
        ctk.CTkLabel(
            title_stack,
            text="A T L A S",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=self.ACCENT_BRIGHT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_stack,
            text="GEMINI 3.1 FLASH-LITE  •  FULL SYSTEM OPERATOR",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=self.TEXT_MUTED,
        ).pack(anchor="w")

        # Center Mirrored Waveform Pill
        self.status_badge = ctk.CTkFrame(
            self.header_card,
            fg_color=self.BG_DEEP,
            corner_radius=999,
            border_width=1,
            border_color=self.BORDER_SUBTLE,
        )
        self.status_badge.grid(row=0, column=1, padx=6, pady=8, sticky="w")

        self.vis_canvas = tk.Canvas(self.status_badge, width=84, height=22, bg=self.BG_DEEP, highlightthickness=0)
        self.vis_canvas.pack(side="left", padx=(12, 6), pady=4)
        self.vis_bars = [
            self.vis_canvas.create_rectangle(2 + i * 5, 9, 5 + i * 5, 13, fill=self.STATUS_GREEN, outline="")
            for i in range(self._num_bars)
        ]

        self.status_label = ctk.CTkLabel(
            self.status_badge,
            text="Ready",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.STATUS_GREEN,
        )
        self.status_label.pack(side="left", padx=(2, 14), pady=3)

        # Right Vector Icon Toolbar
        ctrl = ctk.CTkFrame(self.header_card, fg_color="transparent")
        ctrl.grid(row=0, column=2, padx=(4, 12), pady=8, sticky="e")

        btn_cfg = {
            "height": 32,
            "corner_radius": 8,
            "fg_color": self.CARD_BG,
            "hover_color": "#283048",
            "border_width": 1,
            "border_color": self.BORDER_SUBTLE,
            "font": ctk.CTkFont(size=12, weight="bold"),
        }

        self.btn_tasks = ctk.CTkButton(
            ctrl, text="Tasks", image=self.ico_tasks, compound="left", width=78,
            command=self.toggle_task_panel, **btn_cfg
        )
        self.btn_tasks.pack(side="left", padx=2)

        self.btn_memory = ctk.CTkButton(
            ctrl, text="Memory", image=self.ico_memory, compound="left", width=86,
            command=self.toggle_memory_panel, **btn_cfg
        )
        self.btn_memory.pack(side="left", padx=2)

        ctk.CTkButton(ctrl, text="", image=self.ico_sun, width=34, command=self.on_briefing, **btn_cfg).pack(side="left", padx=2)
        ctk.CTkButton(ctrl, text="", image=self.ico_undo, width=34, command=self.on_undo, **btn_cfg).pack(side="left", padx=2)

        self.btn_quiet = ctk.CTkButton(ctrl, text="", image=self.ico_bell, width=34, command=self.toggle_quiet, **btn_cfg)
        self.btn_quiet.pack(side="left", padx=2)

        self.btn_mute = ctk.CTkButton(ctrl, text="", image=self.ico_mic_on, width=34, command=self.toggle_mute, **btn_cfg)
        self.btn_mute.pack(side="left", padx=2)

        self.btn_pin = ctk.CTkButton(ctrl, text="", image=self.ico_pin, width=34, command=self.toggle_pin, **btn_cfg)
        self.btn_pin.pack(side="left", padx=2)

        ctk.CTkButton(ctrl, text="", image=self.ico_clear, width=34, command=self._handle_clear, **btn_cfg).pack(side="left", padx=2)

        # ==========================================
        # 2. QUICK-ACTION CHIP BAR
        # ==========================================
        self.chip_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.chip_bar.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 4))

        chip_style = {
            "height": 26,
            "corner_radius": 999,
            "fg_color": "#151a28",
            "hover_color": "#232b42",
            "border_width": 1,
            "border_color": self.BORDER_SUBTLE,
            "font": ctk.CTkFont(size=11),
            "text_color": self.TEXT_SECONDARY,
        }

        ctk.CTkButton(
            self.chip_bar, text="🖥️ Inspect Current Screen",
            command=lambda: self._quick_prompt("Inspect my current screen and tell me what is open.", screen=True),
            **chip_style
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            self.chip_bar, text="💬 Send WhatsApp Message",
            command=lambda: self.update_input_box("Send a WhatsApp message to [Contact Name] saying: "),
            **chip_style
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            self.chip_bar, text="🚀 List Installed PC Apps",
            command=lambda: self._quick_prompt("List the applications installed on my computer.", screen=False),
            **chip_style
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            self.chip_bar, text="🛠️ System Health",
            command=lambda: self._quick_prompt("Check my CPU, RAM, and disk space status.", screen=False),
            **chip_style
        ).pack(side="left", padx=6)

        # ==========================================
        # 3. APPROVAL BANNER (Levels 2 & 3 Only)
        # ==========================================
        self.approval_frame = ctk.CTkFrame(
            self, fg_color="#231724", corner_radius=12, border_width=1, border_color=self.STATUS_AMBER
        )
        self.approval_lbl = ctk.CTkLabel(
            self.approval_frame, text="", font=ctk.CTkFont(size=12),
            text_color=self.TEXT_MAIN, wraplength=460, justify="left"
        )
        self.approval_lbl.pack(side="left", padx=14, pady=10, expand=True, fill="x")

        btn_box = ctk.CTkFrame(self.approval_frame, fg_color="transparent")
        btn_box.pack(side="right", padx=10, pady=8)
        ctk.CTkButton(
            btn_box, text="✓ Approve Once", width=106, height=26, fg_color=self.STATUS_GREEN,
            command=lambda: self._resolve_approval("approve_once")
        ).pack(pady=2)
        ctk.CTkButton(
            btn_box, text="✕ Deny", width=106, height=26, fg_color=self.STATUS_AMBER,
            command=lambda: self._resolve_approval("deny")
        ).pack(pady=2)
        ctk.CTkButton(
            btn_box, text="⏹ Cancel Task", width=106, height=26, fg_color=self.STATUS_RED,
            command=lambda: self._resolve_approval("cancel_task")
        ).pack(pady=2)

        # ==========================================
        # 4. CONVERSATION STREAM (Formatted Markdown Cards)
        # ==========================================
        self.chat_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=self.CARD_BG,
            corner_radius=16,
            border_width=1,
            border_color=self.BORDER_SUBTLE,
        )
        self.chat_scroll.grid(row=3, column=0, sticky="nsew", padx=18, pady=6)
        self.chat_scroll.grid_columnconfigure(0, weight=1)

        self.add_assistant_bubble(
            "**ATLAS Operator Online.**\n"
            "• **Universal App Access:** Ask me to open *any* installed app on your PC (`WhatsApp`, `Spotify`, `VS Code`, `Discord`, etc.).\n"
            "• **WhatsApp & Vision Agent:** Ask me to look at your screen or send a WhatsApp message to any contact automatically."
        )

        # ==========================================
        # 5. COMMAND INPUT & LIVE TELEMETRY DOCK
        # ==========================================
        self.input_card = ctk.CTkFrame(
            self,
            fg_color=self.SURFACE,
            corner_radius=16,
            border_width=1,
            border_color=self.BORDER_SUBTLE,
        )
        self.input_card.grid(row=4, column=0, sticky="ew", padx=18, pady=(6, 16))
        self.input_card.grid_columnconfigure((0, 1), weight=1)

        # Live Action Telemetry Bar
        self.action_hud = ctk.CTkFrame(self.input_card, fg_color=self.BG_DEEP, corner_radius=8, height=28)
        self.action_dot_canvas = tk.Canvas(self.action_hud, width=22, height=18, bg=self.BG_DEEP, highlightthickness=0)
        self.action_dot_canvas.pack(side="left", padx=(10, 4), pady=4)
        self.action_hud_lbl = ctk.CTkLabel(
            self.action_hud, text="", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.SCREEN_ACCENT
        )
        self.action_hud_lbl.pack(side="left", padx=4, pady=4)

        # Screen Capture + Reticle Preview
        self.preview_frame = ctk.CTkFrame(
            self.input_card, fg_color=self.BG_DEEP, corner_radius=10, border_width=1, border_color=self.BORDER_SUBTLE
        )
        self.preview_img_lbl = ctk.CTkLabel(self.preview_frame, text="")
        self.preview_img_lbl.pack(side="left", padx=10, pady=6)
        self.preview_caption = ctk.CTkLabel(
            self.preview_frame,
            text="🎯 Vision Target Locked (Cyan reticle shows interaction point)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.SCREEN_ACCENT,
        )
        self.preview_caption.pack(side="left", padx=8)

        self.input_box = ctk.CTkEntry(
            self.input_card,
            placeholder_text="Say 'Atlas' or type a command (e.g., 'Open WhatsApp and send Hi to Rahul')...",
            height=46,
            corner_radius=12,
            fg_color=self.BG_DEEP,
            border_width=1,
            border_color=self.BORDER_SUBTLE,
            text_color=self.TEXT_MAIN,
            font=ctk.CTkFont(size=14),
        )
        self.input_box.grid(row=2, column=0, columnspan=4, sticky="ew", padx=12, pady=(12, 10))
        self.input_box.bind("<Return>", lambda _e: self._handle_chat_click())
        self.input_box.bind("<FocusIn>", lambda _e: self.input_box.configure(border_color=self.ACCENT))
        self.input_box.bind("<FocusOut>", lambda _e: self.input_box.configure(border_color=self.BORDER_SUBTLE))

        self.btn_screen = ctk.CTkButton(
            self.input_card,
            text="Vision + Screen Task",
            image=self.ico_screen,
            compound="left",
            height=42,
            corner_radius=10,
            fg_color=self.SCREEN_ACCENT,
            hover_color=self.SCREEN_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_screen_click,
        )
        self.btn_screen.grid(row=3, column=0, sticky="ew", padx=(12, 5), pady=(0, 12))

        self.btn_chat = ctk.CTkButton(
            self.input_card,
            text="Execute / Send",
            image=self.ico_send,
            compound="left",
            height=42,
            corner_radius=10,
            fg_color=self.ACCENT,
            hover_color=self.ACCENT_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._handle_chat_click,
        )
        self.btn_chat.grid(row=3, column=1, sticky="ew", padx=5, pady=(0, 12))

        self.btn_mic = ctk.CTkButton(
            self.input_card,
            text="",
            image=self.ico_mic_on,
            width=48,
            height=42,
            corner_radius=10,
            fg_color=self.CARD_ELEVATED,
            hover_color="#2e364f",
            border_width=1,
            border_color=self.BORDER_SUBTLE,
            command=self.on_manual_voice,
        )
        self.btn_mic.grid(row=3, column=2, padx=5, pady=(0, 12))

        self.btn_stop = ctk.CTkButton(
            self.input_card,
            text="",
            image=self.ico_stop,
            width=48,
            height=42,
            corner_radius=10,
            fg_color="#2b141d",
            hover_color="#4c1d2e",
            border_width=1,
            border_color=self.STATUS_RED,
            command=self.on_stop_all,
        )
        self.btn_stop.grid(row=3, column=3, padx=(5, 12), pady=(0, 12))

        # ==========================================
        # 6. SLIDE-IN TASKS & MEMORY DRAWERS
        # ==========================================
        self.task_panel = ctk.CTkFrame(
            self, width=360, height=390, fg_color=self.SURFACE, corner_radius=14,
            border_width=1, border_color=self.BORDER_GLOW
        )
        thdr = ctk.CTkFrame(self.task_panel, fg_color="transparent")
        thdr.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(thdr, text="Active Tasks & Reminders", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(thdr, text="✕", width=26, height=24, fg_color="transparent", command=self.toggle_task_panel).pack(side="right")
        self.task_list_scroll = ctk.CTkScrollableFrame(self.task_panel, fg_color="transparent", width=330, height=310)
        self.task_list_scroll.pack(fill="both", expand=True, padx=8, pady=6)

        self.memory_panel = ctk.CTkFrame(
            self, width=380, height=400, fg_color=self.SURFACE, corner_radius=14,
            border_width=1, border_color=self.BORDER_GLOW
        )
        mhdr = ctk.CTkFrame(self.memory_panel, fg_color="transparent")
        mhdr.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(mhdr, text="Memory Inspector (Profile & Workspace)", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(mhdr, text="✕", width=26, height=24, fg_color="transparent", command=self.toggle_memory_panel).pack(side="right")
        self.memory_list_scroll = ctk.CTkScrollableFrame(self.memory_panel, fg_color="transparent", width=350, height=320)
        self.memory_list_scroll.pack(fill="both", expand=True, padx=8, pady=6)

    # ==========================================
    # RICH MARKDOWN CARD FORMATTER (No Raw ** Asterisks)
    # ==========================================
    def _insert_formatted_markdown(self, parent_frame: ctk.CTkFrame, raw_text: str, bg_color: str):
        """Renders **bold**, `inline code`, and VERIFIED badges cleanly without raw markdown symbols."""
        clean_lines = raw_text.strip().splitlines() or [raw_text]
        for line in clean_lines:
            row = ctk.CTkFrame(parent_frame, fg_color="transparent")
            row.pack(anchor="w", fill="x", pady=1)

            # Split line into tokens of **bold** or `code`
            tokens = re.split(r"(\*\*.*?\*\*|`.*?`)", line)
            text_acc = []
            for tok in tokens:
                if not tok:
                    continue
                if tok.startswith("**") and tok.endswith("**") and len(tok) > 4:
                    if text_acc:
                        ctk.CTkLabel(
                            row, text="".join(text_acc), font=ctk.CTkFont(size=14),
                            text_color=self.TEXT_SECONDARY, wraplength=460, justify="left"
                        ).pack(side="left")
                        text_acc = []
                    bold_val = tok[2:-2]
                    color = self.STATUS_GREEN if "VERIFIED" in bold_val else "#ffffff"
                    ctk.CTkLabel(
                        row, text=bold_val, font=ctk.CTkFont(size=14, weight="bold"),
                        text_color=color, wraplength=460, justify="left"
                    ).pack(side="left", padx=2)
                elif tok.startswith("`") and tok.endswith("`") and len(tok) > 2:
                    if text_acc:
                        ctk.CTkLabel(
                            row, text="".join(text_acc), font=ctk.CTkFont(size=14),
                            text_color=self.TEXT_SECONDARY, wraplength=460, justify="left"
                        ).pack(side="left")
                        text_acc = []
                    code_val = tok[1:-1]
                    pill = ctk.CTkLabel(
                        row, text=f" {code_val} ", font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                        fg_color=self.BG_DEEP, text_color=self.SCREEN_ACCENT, corner_radius=5
                    )
                    pill.pack(side="left", padx=2)
                else:
                    text_acc.append(tok)

            if text_acc:
                joined = "".join(text_acc)
                ctk.CTkLabel(
                    row, text=joined, font=ctk.CTkFont(size=14),
                    text_color=self.TEXT_MAIN, wraplength=460, justify="left"
                ).pack(side="left")

    # ==========================================
    # 30 FPS HUD REACTOR & MIRRORED WAVEFORM ENGINE
    # ==========================================
    def _start_animation_engine(self):
        def _tick():
            self._anim_phase += 0.12

            # 1. Multi-Ring Orbital Reactor
            self.orb_canvas.delete("all")
            cx, cy = 21, 21
            speed = 2.5 if self._is_active_busy else 1.0
            pulse = math.sin(self._anim_phase * speed)

            r_out = 16 + pulse * 2.0
            self.orb_canvas.create_oval(cx - r_out, cy - r_out, cx + r_out, cy + r_out, outline="#262f45", width=2)

            ang1 = (self._anim_phase * 48 * speed) % 360
            self.orb_canvas.create_arc(
                cx - 14, cy - 14, cx + 14, cy + 14, start=ang1, extent=100,
                style=tk.ARC, outline=self.ACCENT_BRIGHT, width=2.5
            )
            self.orb_canvas.create_arc(
                cx - 14, cy - 14, cx + 14, cy + 14, start=(ang1 + 180) % 360, extent=100,
                style=tk.ARC, outline=self.SCREEN_ACCENT, width=2.5
            )

            ang2 = (-self._anim_phase * 36 * speed) % 360
            self.orb_canvas.create_arc(
                cx - 9, cy - 9, cx + 9, cy + 9, start=ang2, extent=140,
                style=tk.ARC, outline=self._state_color, width=2
            )

            r_core = 4.2 + pulse * 0.9
            self.orb_canvas.create_oval(
                cx - r_core, cy - r_core, cx + r_core, cy + r_core, fill=self._state_color, outline=""
            )

            # 2. Mirrored Center-Out 16-Bar Audio Waveform
            mid_y = 11
            for i in range(self._num_bars):
                target = self._target_bars[i]
                if target > self._current_bars[i]:
                    self._current_bars[i] += (target - self._current_bars[i]) * 0.48
                else:
                    self._current_bars[i] = max(0.05, self._current_bars[i] * 0.82)

                val = self._current_bars[i]
                if self._is_active_busy and val < 0.18:
                    val = 0.16 + 0.14 * abs(math.sin(self._anim_phase * 2.2 + i * 0.45))

                half_h = max(1.5, val * 9.5)
                x0 = 3 + i * 5
                color = (
                    self.STATUS_RED if val > 0.72
                    else (self.STATUS_AMBER if val > 0.38 else self._state_color)
                )
                self.vis_canvas.coords(self.vis_bars[i], x0, mid_y - half_h, x0 + 3, mid_y + half_h)
                self.vis_canvas.itemconfig(self.vis_bars[i], fill=color)
                self._target_bars[i] *= 0.88

            # 3. Live Action HUD Pulse Dot
            if self._action_banner_text:
                self.action_dot_canvas.delete("all")
                dr = 4 + 2 * abs(math.sin(self._anim_phase * 2.5))
                self.action_dot_canvas.create_oval(11 - dr, 9 - dr, 11 + dr, 9 + dr, fill=self.SCREEN_ACCENT, outline="")

            self.after(33, _tick)

        self.after(33, _tick)

    def _animate_drawer_in(self, panel: ctk.CTkFrame, target_y: int = 72):
        start_y = 38
        steps = 8

        def _step(i):
            progress = 1.0 - pow(1.0 - (i / steps), 3)
            cur_y = int(start_y + (target_y - start_y) * progress)
            panel.place(relx=0.97, y=cur_y, anchor="ne")
            panel.lift()
            if i < steps:
                self.after(14, lambda: _step(i + 1))

        _step(1)

    # ==========================================
    # THREAD-SAFE UI HELPERS
    # ==========================================
    def safe_call(self, func, *args, **kwargs):
        self.after(0, lambda: func(*args, **kwargs))

    def set_status(self, text: str, color: str = "#10b981", disable_buttons: bool = False):
        def _u():
            self.status_label.configure(text=text, text_color=color)
            self._state_color = color
            self._is_active_busy = disable_buttons
            self.header_card.configure(border_color=color if disable_buttons else self.BORDER_SUBTLE)
            state = "disabled" if disable_buttons else "normal"
            self.btn_screen.configure(state=state)
            self.btn_chat.configure(state=state)
            self.btn_mic.configure(state=state)
            if not disable_buttons:
                self.set_action_banner("")
        self.safe_call(_u)

    def set_action_banner(self, text: str):
        def _b():
            self._action_banner_text = text
            if text:
                self.action_hud_lbl.configure(text=text)
                self.action_hud.grid(row=0, column=0, columnspan=4, sticky="ew", padx=12, pady=(10, 0))
            else:
                self.action_hud.grid_forget()
        self.safe_call(_b)

    def update_visualizer(self, levels: List[float]):
        def _d():
            if not levels:
                return
            for i in range(self._num_bars):
                src_idx = i % len(levels)
                mirror_weight = 1.0 - abs((i - self._num_bars / 2) / (self._num_bars / 2)) * 0.35
                self._target_bars[i] = min(1.0, levels[src_idx] * mirror_weight)
        self.safe_call(_d)

    def add_user_bubble(self, text: str):
        def _add():
            stamp = datetime.now().strftime("%H:%M")
            card = ctk.CTkFrame(
                self.chat_scroll, fg_color=self.USER_BUBBLE, corner_radius=14,
                border_width=1, border_color="#384566"
            )
            card.pack(anchor="e", pady=6, padx=(80, 6))

            ctk.CTkLabel(
                card, text=f"YOU  •  {stamp}", font=ctk.CTkFont(size=10, weight="bold"),
                text_color=self.ACCENT_BRIGHT
            ).pack(anchor="e", padx=14, pady=(8, 0))

            ctk.CTkLabel(
                card, text=text, font=ctk.CTkFont(size=14),
                text_color=self.TEXT_MAIN, wraplength=460, justify="left"
            ).pack(padx=14, pady=(2, 10))
            self.chat_scroll._parent_canvas.yview_moveto(1.0)
        self.safe_call(_add)

    def add_assistant_bubble(self, text: str):
        def _add():
            stamp = datetime.now().strftime("%H:%M")
            outer = ctk.CTkFrame(
                self.chat_scroll, fg_color=self.ASSISTANT_BUBBLE, corner_radius=14,
                border_width=1, border_color=self.BORDER_SUBTLE
            )
            outer.pack(anchor="w", pady=6, padx=(6, 65), fill="x")

            stripe_col = self.STATUS_GREEN if "VERIFIED" in text else self.ACCENT
            stripe = ctk.CTkFrame(outer, width=4, fg_color=stripe_col, corner_radius=4)
            stripe.pack(side="left", fill="y", padx=(0, 4), pady=8)

            inner = ctk.CTkFrame(outer, fg_color="transparent")
            inner.pack(side="left", fill="both", expand=True, padx=10, pady=8)

            ctk.CTkLabel(
                inner, text=f"ATLAS OPERATOR  •  {stamp}",
                font=ctk.CTkFont(size=10, weight="bold"), text_color=self.SCREEN_ACCENT
            ).pack(anchor="w", pady=(0, 3))

            self._insert_formatted_markdown(inner, text, self.ASSISTANT_BUBBLE)
            self.chat_scroll._parent_canvas.yview_moveto(1.0)
        self.safe_call(_add)

    def update_input_box(self, text: str):
        def _s():
            self.input_box.delete(0, "end")
            self.input_box.insert(0, text)
            self.input_box.focus_set()
        self.safe_call(_s)

    def show_screen_preview(self, image_path: str):
        def _sh():
            try:
                pil_img = Image.open(image_path)
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(96, 54))
                self.preview_img_lbl.configure(image=ctk_img)
                self.preview_img_lbl.image = ctk_img
                self.preview_frame.grid(row=1, column=0, columnspan=4, sticky="ew", padx=12, pady=(8, 0))
                self.after(6500, lambda: self.preview_frame.grid_forget())
            except Exception:
                pass
        self.safe_call(_sh)

    def show_approval_prompt(self, payload: Dict[str, str]):
        def _p():
            txt = (
                f"⚠️ {payload['level']}\n"
                f"• Action: {payload['action']}\n"
                f"• Target: {payload['target']}\n"
                f"• Scope: {payload['scope']}\n"
                f"• Consequences: {payload['consequences']}"
            )
            self.approval_lbl.configure(text=txt)
            self.approval_frame.grid(row=2, column=0, sticky="ew", padx=18, pady=4)
        self.safe_call(_p)

    def _resolve_approval(self, choice: str):
        self.approval_frame.grid_forget()
        self.on_approval_decision(choice)

    def render_tasks(self, tasks: List[Dict[str, Any]]):
        def _r():
            for c in self.task_list_scroll.winfo_children():
                c.destroy()
            self.btn_tasks.configure(text=f"Tasks ({len(tasks)})" if tasks else "Tasks")
            if not tasks:
                ctk.CTkLabel(self.task_list_scroll, text="No active tasks.", text_color=self.TEXT_MUTED).pack(pady=24)
                return
            for t in tasks:
                row = ctk.CTkFrame(
                    self.task_list_scroll, fg_color=self.CARD_ELEVATED, corner_radius=8,
                    border_width=1, border_color=self.BORDER_SUBTLE
                )
                row.pack(fill="x", pady=4)
                info = ctk.CTkFrame(row, fg_color="transparent")
                info.pack(side="left", padx=8, pady=6, fill="x", expand=True)
                p_tag = f"[{t.get('priority', 'medium').upper()}] "
                ctk.CTkLabel(info, text=p_tag + t["title"], font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(fill="x")
                ctk.CTkLabel(info, text=f"🕒 {t['due_time']}", font=ctk.CTkFont(size=11), text_color=self.SCREEN_ACCENT, anchor="w").pack(fill="x")
                ctk.CTkButton(
                    row, text="+15m", width=42, height=24, font=ctk.CTkFont(size=10),
                    fg_color="#282d3d", command=lambda tid=t["id"]: self.on_snooze_task(tid)
                ).pack(side="right", padx=(2, 6))
                ctk.CTkButton(
                    row, text="✔", width=32, height=24, font=ctk.CTkFont(size=11),
                    fg_color="#13382e", hover_color=self.STATUS_GREEN, command=lambda tid=t["id"]: self.on_complete_task(tid)
                ).pack(side="right", padx=2)
        self.safe_call(_r)

    def render_memories(self, data: Dict[str, Any]):
        def _rm():
            for c in self.memory_list_scroll.winfo_children():
                c.destroy()
            total = len(data.get("profile", {})) + len(data.get("workspace", {}))
            self.btn_memory.configure(text=f"Memory ({total})" if total else "Memory")
            if total == 0:
                ctk.CTkLabel(self.memory_list_scroll, text="No stored memories.", text_color=self.TEXT_MUTED).pack(pady=24)
                return
            for cat in ("profile", "workspace"):
                items = data.get(cat, {})
                for k, v in items.items():
                    row = ctk.CTkFrame(self.memory_list_scroll, fg_color=self.CARD_ELEVATED, corner_radius=8)
                    row.pack(fill="x", pady=3)
                    lbl_txt = f"[{cat.upper()}] {k}: {v.get('value', '')}\n({v.get('updated_at', '')})"
                    ctk.CTkLabel(row, text=lbl_txt, font=ctk.CTkFont(size=11), justify="left", anchor="w", wraplength=255).pack(side="left", padx=8, pady=6)
                    ctk.CTkButton(
                        row, text="✕", width=28, height=24, fg_color="#3b1d26", hover_color=self.STATUS_RED,
                        command=lambda c_name=cat, k_name=k: self.on_delete_memory(c_name, k_name)
                    ).pack(side="right", padx=6)
        self.safe_call(_rm)

    # ==========================================
    # UI INTERACTION CALLBACKS
    # ==========================================
    def _quick_prompt(self, prompt: str, screen: bool = False):
        self.add_user_bubble(f"🖥️ {prompt}" if screen else prompt)
        if screen:
            self.on_ask_screen(prompt)
        else:
            self.on_ask_text(prompt)

    def toggle_task_panel(self):
        self.task_panel_visible = not self.task_panel_visible
        if self.task_panel_visible:
            self.memory_panel_visible = False
            self.memory_panel.place_forget()
            self._animate_drawer_in(self.task_panel)
        else:
            self.task_panel.place_forget()

    def toggle_memory_panel(self):
        self.memory_panel_visible = not self.memory_panel_visible
        if self.memory_panel_visible:
            self.task_panel_visible = False
            self.task_panel.place_forget()
            self._animate_drawer_in(self.memory_panel)
        else:
            self.memory_panel.place_forget()

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        self.attributes("-topmost", self.is_pinned)
        self.btn_pin.configure(fg_color=self.ACCENT if self.is_pinned else self.CARD_BG)

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        self.btn_mute.configure(
            image=self.ico_mic_off if self.is_muted else self.ico_mic_on,
            fg_color="#3b1d26" if self.is_muted else self.CARD_BG,
        )
        self.on_toggle_mute(self.is_muted)

    def toggle_quiet(self):
        self.is_quiet = not self.is_quiet
        self.btn_quiet.configure(
            image=self.ico_bell_off if self.is_quiet else self.ico_bell,
            fg_color="#332614" if self.is_quiet else self.CARD_BG,
        )
        self.on_toggle_quiet(self.is_quiet)

    def _handle_clear(self):
        for c in self.chat_scroll.winfo_children():
            c.destroy()
        self.add_assistant_bubble("**Conversation cleared.** Ready for your next command.")
        self.on_clear_chat()

    def _handle_chat_click(self):
        q = self.input_box.get().strip()
        if not q:
            return
        self.input_box.delete(0, "end")
        self.add_user_bubble(q)
        self.on_ask_text(q)

    def _handle_screen_click(self):
        q = self.input_box.get().strip() or "Inspect the screen and help me with what is currently open."
        self.input_box.delete(0, "end")
        self.add_user_bubble(f"🖥️ [Vision Task]: {q}")
        self.on_ask_screen(q)