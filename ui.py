import os
import re
import sys
import math
from datetime import datetime
from typing import Callable, List, Dict, Any

from PySide6 import QtCore, QtWidgets, QtGui
from core.solar_hud import AtomicSolarHUD
from core.spectrum_hud import AudioSpectrumHUD


# =====================================================================
# TOP CYBERNETIC HEADER BANNER (No "60 FPS" text per Requirement 4)
# =====================================================================
class CyberHeaderBanner(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx = w / 2.0

        # Background fill
        painter.fillRect(self.rect(), QtGui.QColor(5, 10, 18))

        # Top cybernetic polygon frame
        top_poly = QtGui.QPolygonF([
            QtCore.QPointF(12, 6),
            QtCore.QPointF(w - 12, 6),
            QtCore.QPointF(w - 12, 46),
            QtCore.QPointF(cx + 150, 46),
            QtCore.QPointF(cx + 120, 60),
            QtCore.QPointF(cx - 120, 60),
            QtCore.QPointF(cx - 150, 46),
            QtCore.QPointF(12, 46),
        ])

        grad = QtGui.QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QtGui.QColor(12, 24, 38, 230))
        grad.setColorAt(1.0, QtGui.QColor(7, 14, 24, 240))
        painter.setBrush(QtGui.QBrush(grad))

        border_pen = QtGui.QPen(QtGui.QColor(35, 95, 120, 200))
        border_pen.setWidthF(1.6)
        painter.setPen(border_pen)
        painter.drawPolygon(top_poly)

        # Glowing cyan bottom lip under "ATLAS" center trapezoid
        glow_pen = QtGui.QPen(QtGui.QColor(0, 235, 255, 90))
        glow_pen.setWidthF(6.0)
        glow_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(glow_pen)
        painter.drawLine(QtCore.QPointF(cx - 52, 59), QtCore.QPointF(cx + 52, 59))

        core_pen = QtGui.QPen(QtGui.QColor(120, 250, 255, 255))
        core_pen.setWidthF(2.2)
        painter.setPen(core_pen)
        painter.drawLine(QtCore.QPointF(cx - 52, 59), QtCore.QPointF(cx + 52, 59))

        # Left & Right angled telemetry accents flanking ATLAS
        accent_pen = QtGui.QPen(QtGui.QColor(0, 205, 225, 150))
        accent_pen.setWidthF(2.0)
        painter.setPen(accent_pen)
        for i in range(3):
            lx = cx - 225 + i * 11
            painter.drawLine(QtCore.QPointF(lx, 14), QtCore.QPointF(lx + 10, 34))
            rx = cx + 225 - i * 11
            painter.drawLine(QtCore.QPointF(rx, 14), QtCore.QPointF(rx - 10, 34))

        # Center "ATLAS" Title
        atlas_font = QtGui.QFont("Bahnschrift", 26, QtGui.QFont.Weight.Bold)
        atlas_font.setLetterSpacing(QtGui.QFont.SpacingType.AbsoluteSpacing, 6.0)
        painter.setFont(atlas_font)
        painter.setPen(QtGui.QColor(225, 248, 255))
        painter.drawText(QtCore.QRectF(cx - 140, 6, 280, 48), QtCore.Qt.AlignmentFlag.AlignCenter, "ATLAS")

        # Left Circular Tech Emblem + "GEMINI 3.1 / FLASH-LITE • FULL SYSTEM OPERATOR"
        emblem_cx, emblem_cy = 38.0, 26.0
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 225, 220, 210), 2.2))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QtCore.QPointF(emblem_cx, emblem_cy), 14, 14)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 225, 220, 130), 1.4, QtCore.Qt.PenStyle.DotLine))
        painter.drawEllipse(QtCore.QPointF(emblem_cx, emblem_cy), 9, 9)
        painter.setBrush(QtGui.QColor(0, 240, 215))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(QtCore.QPointF(emblem_cx, emblem_cy), 3.2, 3.2)

        gem_font = QtGui.QFont("Bahnschrift", 13, QtGui.QFont.Weight.Bold)
        gem_font.setLetterSpacing(QtGui.QFont.SpacingType.AbsoluteSpacing, 1.2)
        painter.setFont(gem_font)
        painter.setPen(QtGui.QColor(80, 215, 230))
        painter.drawText(QtCore.QPointF(62, 23), "GEMINI 3.1")

        sub_font = QtGui.QFont("Bahnschrift", 8, QtGui.QFont.Weight.DemiBold)
        sub_font.setLetterSpacing(QtGui.QFont.SpacingType.AbsoluteSpacing, 0.8)
        painter.setFont(sub_font)
        painter.setPen(QtGui.QColor(150, 185, 200))
        painter.drawText(QtCore.QPointF(62, 37), "FLASH-LITE • FULL SYSTEM OPERATOR")

        painter.end()


# =====================================================================
# TOP-RIGHT GLOWING MATRIX BUTTON (Requirement 1)
# =====================================================================
class GlowGridButton(QtWidgets.QPushButton):
    """Square cybernetic icon+label button that renders a neon teal glow when selected."""

    def __init__(self, label: str, icon_type: str, checkable: bool = False, parent=None):
        super().__init__(parent)
        self.label_text = label
        self.icon_type = icon_type
        self.setCheckable(checkable)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(62, 54)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        selected = self.isChecked() or self.isDown()
        hovered = self.underMouse()
        rect = QtCore.QRectF(3, 3, self.width() - 6, self.height() - 6)

        if selected:
            # Outer & Inner Neon Teal Glow (matches "Tasks" button in image_f9d099.jpg)
            for expand, alpha in [(2.5, 45), (1.2, 95)]:
                glow_r = rect.adjusted(-expand, -expand, expand, expand)
                g_pen = QtGui.QPen(QtGui.QColor(0, 245, 212, alpha))
                g_pen.setWidthF(2.5)
                painter.setPen(g_pen)
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(glow_r, 8, 8)

            bg_grad = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
            bg_grad.setColorAt(0.0, QtGui.QColor(12, 68, 74, 235))
            bg_grad.setColorAt(1.0, QtGui.QColor(8, 38, 46, 240))
            painter.setBrush(QtGui.QBrush(bg_grad))
            border_pen = QtGui.QPen(QtGui.QColor(60, 255, 225, 255), 1.8)
            icon_color = QtGui.QColor(160, 255, 240)
            text_color = QtGui.QColor(220, 255, 250)
        else:
            bg_col = QtGui.QColor(16, 26, 38, 230) if hovered else QtGui.QColor(10, 17, 27, 220)
            painter.setBrush(bg_col)
            border_pen = QtGui.QPen(QtGui.QColor(45, 95, 115, 190 if hovered else 130), 1.2)
            icon_color = QtGui.QColor(110, 175, 195) if not hovered else QtGui.QColor(160, 230, 245)
            text_color = QtGui.QColor(145, 175, 190)

        painter.setPen(border_pen)
        painter.drawRoundedRect(rect, 7, 7)

        # Draw Crisp Vector Icon
        cx = self.width() / 2.0
        cy = 19.0
        ic_pen = QtGui.QPen(icon_color, 1.6)
        ic_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        ic_pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
        painter.setPen(ic_pen)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        if self.icon_type == "tasks":
            painter.drawRoundedRect(QtCore.QRectF(cx - 7, cy - 7, 14, 15), 2, 2)
            painter.drawLine(QtCore.QPointF(cx - 3, cy - 1), QtCore.QPointF(cx - 1, cy + 2))
            painter.drawLine(QtCore.QPointF(cx - 1, cy + 2), QtCore.QPointF(cx + 4, cy - 3))
        elif self.icon_type == "memory":
            painter.drawRoundedRect(QtCore.QRectF(cx - 6, cy - 7, 12, 14), 2, 2)
            painter.drawLine(QtCore.QPointF(cx - 3, cy - 2), QtCore.QPointF(cx + 3, cy - 2))
            painter.drawLine(QtCore.QPointF(cx - 3, cy + 2), QtCore.QPointF(cx + 3, cy + 2))
        elif self.icon_type == "briefing":
            painter.drawRoundedRect(QtCore.QRectF(cx - 7, cy - 7, 14, 14), 2, 2)
            for dy in (-3, 0, 3):
                painter.drawLine(QtCore.QPointF(cx - 4, cy + dy), QtCore.QPointF(cx + 4, cy + dy))
        elif self.icon_type == "undo":
            painter.drawArc(QtCore.QRectF(cx - 6, cy - 5, 12, 11), 30 * 16, 240 * 16)
            painter.drawLine(QtCore.QPointF(cx - 6, cy - 2), QtCore.QPointF(cx - 2, cy - 6))
            painter.drawLine(QtCore.QPointF(cx - 6, cy - 2), QtCore.QPointF(cx - 2, cy + 1))
        elif self.icon_type == "quiet":
            painter.drawPolygon([
                QtCore.QPointF(cx - 6, cy - 2),
                QtCore.QPointF(cx - 2, cy - 2),
                QtCore.QPointF(cx + 2, cy - 6),
                QtCore.QPointF(cx + 2, cy + 6),
                QtCore.QPointF(cx - 2, cy + 2),
                QtCore.QPointF(cx - 6, cy + 2),
            ])
            painter.drawLine(QtCore.QPointF(cx - 6, cy - 6), QtCore.QPointF(cx + 6, cy + 6))
        elif self.icon_type == "pin":
            painter.drawRoundedRect(QtCore.QRectF(cx - 5, cy - 6, 10, 7), 1.5, 1.5)
            painter.drawLine(QtCore.QPointF(cx, cy + 1), QtCore.QPointF(cx, cy + 7))
        elif self.icon_type == "clear":
            painter.drawRoundedRect(QtCore.QRectF(cx - 5, cy - 4, 10, 11), 1.5, 1.5)
            painter.drawLine(QtCore.QPointF(cx - 7, cy - 4), QtCore.QPointF(cx + 7, cy - 4))
        elif self.icon_type == "mute":
            painter.drawRoundedRect(QtCore.QRectF(cx - 3, cy - 7, 6, 9), 3, 3)
            painter.drawArc(QtCore.QRectF(cx - 6, cy - 4, 12, 9), 180 * 16, 180 * 16)
            painter.drawLine(QtCore.QPointF(cx - 6, cy - 6), QtCore.QPointF(cx + 6, cy + 6))

        # Label text
        lbl_font = QtGui.QFont("Bahnschrift", 8, QtGui.QFont.Weight.DemiBold)
        painter.setFont(lbl_font)
        painter.setPen(text_color)
        painter.drawText(QtCore.QRectF(0, 31, self.width(), 18), QtCore.Qt.AlignmentFlag.AlignCenter, self.label_text)
        painter.end()


# =====================================================================
# CLEAN SCREEN PREVIEW WIDGET (No Crosshair per Requirement 2)
# =====================================================================
class CleanScreenPreview(QtWidgets.QWidget):
    """Displays the live screen capture inside corner HUD brackets WITHOUT any center crosshair."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap: QtGui.QPixmap | None = None
        self.setMinimumHeight(180)

    def set_image(self, image_path: str):
        if os.path.exists(image_path):
            self.pixmap = QtGui.QPixmap(image_path)
            self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QtGui.QColor(6, 13, 22))

        inner = QtCore.QRectF(12, 10, w - 24, h - 20)
        if self.pixmap and not self.pixmap.isNull():
            scaled = self.pixmap.scaled(
                inner.size().toSize(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            src_rect = QtCore.QRect(0, 0, int(inner.width()), int(inner.height()))
            painter.drawPixmap(inner.toRect(), scaled, src_rect)
        else:
            # Subtle grid background when awaiting first capture
            grid_pen = QtGui.QPen(QtGui.QColor(18, 48, 68, 95), 1.0)
            painter.setPen(grid_pen)
            for gx in range(int(inner.left()), int(inner.right()), 24):
                painter.drawLine(gx, int(inner.top()), gx, int(inner.bottom()))
            for gy in range(int(inner.top()), int(inner.bottom()), 24):
                painter.drawLine(int(inner.left()), gy, int(inner.right()), gy)

            font = QtGui.QFont("Bahnschrift", 10)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(70, 165, 190, 190))
            painter.drawText(inner, QtCore.Qt.AlignmentFlag.AlignCenter, "LIVE SCREEN FEED READY")

        # Corner Cyan L-Brackets only (No center crosshair!)
        b_pen = QtGui.QPen(QtGui.QColor(0, 215, 245, 220), 2.2)
        painter.setPen(b_pen)
        arm = 18.0
        l, r, t, b = inner.left(), inner.right(), inner.top(), inner.bottom()
        painter.drawPolyline([QtCore.QPointF(l, t + arm), QtCore.QPointF(l, t), QtCore.QPointF(l + arm, t)])
        painter.drawPolyline([QtCore.QPointF(r - arm, t), QtCore.QPointF(r, t), QtCore.QPointF(r, t + arm)])
        painter.drawPolyline([QtCore.QPointF(l, b - arm), QtCore.QPointF(l, b), QtCore.QPointF(l + arm, b)])
        painter.drawPolyline([QtCore.QPointF(r - arm, b), QtCore.QPointF(r, b), QtCore.QPointF(r, b - arm)])

        painter.end()


# =====================================================================
# MAIN PYSIDE6 ATLAS CYBERNETIC OPERATOR UI
# =====================================================================
class _UISignalBridge(QtCore.QObject):
    call_signal = QtCore.Signal(object)


class AtlasUI(QtWidgets.QMainWindow):
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
        self._qt_app = QtWidgets.QApplication.instance()
        if not self._qt_app:
            fmt = QtGui.QSurfaceFormat()
            fmt.setSamples(4)
            QtGui.QSurfaceFormat.setDefaultFormat(fmt)
            self._qt_app = QtWidgets.QApplication(sys.argv)

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

        self._bridge = _UISignalBridge()
        self._bridge.call_signal.connect(self._execute_callable)

        self.is_pinned = False
        self.is_muted = False
        self.is_quiet = False
        self.active_right_tab = "tasks"
        self._cached_tasks: List[Dict[str, Any]] = []
        self._cached_memories: Dict[str, Any] = {}

        self.setWindowTitle("ATLAS - Personal AI System Operator")
        self.resize(1380, 820)
        self.setMinimumSize(1120, 700)
        self.setStyleSheet("QMainWindow { background-color: #050a12; }")

        self._build_ui()

    @QtCore.Slot(object)
    def _execute_callable(self, fn):
        try:
            fn()
        except Exception as e:
            print(f"[UI Signal Error]: {e}")

    def safe_call(self, func, *args, **kwargs):
        self._bridge.call_signal.emit(lambda: func(*args, **kwargs))

    # Compatibility wrappers for main.py screen capture hide/show
    def withdraw(self):
        self.hide()

    def deiconify(self):
        self.show()

    def mainloop(self):
        self.show()
        self._qt_app.exec()

    # =================================================================
    # BUILD EXACT PROPORTIONAL HUD LAYOUT (Matching image_f9d099.jpg)
    # =================================================================
    def _build_ui(self):
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        root_vbox = QtWidgets.QVBoxLayout(central)
        root_vbox.setContentsMargins(10, 4, 10, 10)
        root_vbox.setSpacing(8)

        # 1. TOP CYBERNETIC BANNER
        self.header_banner = CyberHeaderBanner(self)
        root_vbox.addWidget(self.header_banner)

        # 2. APPROVAL BANNER (Hidden until Level 2/3 action requests confirmation)
        self.approval_bar = QtWidgets.QFrame()
        self.approval_bar.setStyleSheet(
            "QFrame { background-color: #1f1424; border: 1.5px solid #f59e0b; border-radius: 8px; }"
        )
        app_layout = QtWidgets.QHBoxLayout(self.approval_bar)
        app_layout.setContentsMargins(12, 8, 12, 8)
        self.approval_lbl = QtWidgets.QLabel("")
        self.approval_lbl.setStyleSheet("color: #f3f4f6; font-family: 'Segoe UI'; font-size: 12px; border: none;")
        self.approval_lbl.setWordWrap(True)
        app_layout.addWidget(self.approval_lbl, 1)

        for label, code, col in [
            ("Approve Once", "approve_once", "#10b981"),
            ("Deny", "deny", "#f59e0b"),
            ("Cancel Task", "cancel_task", "#ef4444"),
        ]:
            b = QtWidgets.QPushButton(label)
            b.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ background-color: {col}; color: #040810; font-weight: bold; "
                f"padding: 6px 12px; border-radius: 5px; border: none; }}"
            )
            b.clicked.connect(lambda _=False, c=code: self._resolve_approval(c))
            app_layout.addWidget(b)
        self.approval_bar.hide()
        root_vbox.addWidget(self.approval_bar)

        # 3. THREE-COLUMN MAIN BODY (Proportions: Left 27%, Center 46%, Right 27%)
        body_hbox = QtWidgets.QHBoxLayout()
        body_hbox.setSpacing(12)
        root_vbox.addLayout(body_hbox, 1)

        # -------------------------------------------------------------
        # LEFT COLUMN: AtomicSolarHUD (AI Voice) + Clean Screen Preview
        # -------------------------------------------------------------
        left_col = QtWidgets.QVBoxLayout()
        left_col.setSpacing(8)
        body_hbox.addLayout(left_col, 27)

        self.solar_hud = AtomicSolarHUD(self)
        left_col.addWidget(self.solar_hud, 58)

        sp_title = QtWidgets.QLabel("SCREEN PREVIEW")
        sp_title.setStyleSheet(
            "color: #6fb8c4; font-family: 'Bahnschrift'; font-size: 13px; font-weight: 600; letter-spacing: 1px;"
        )
        left_col.addWidget(sp_title)

        self.screen_card = QtWidgets.QFrame()
        self.screen_card.setStyleSheet(
            "QFrame#ScreenCard { background-color: #08111d; border: 1.5px solid #1b4558; border-radius: 6px; }"
        )
        self.screen_card.setObjectName("ScreenCard")
        sc_vbox = QtWidgets.QVBoxLayout(self.screen_card)
        sc_vbox.setContentsMargins(2, 2, 2, 2)
        sc_vbox.setSpacing(0)

        sc_hdr = QtWidgets.QFrame()
        sc_hdr.setFixedHeight(28)
        sc_hdr.setStyleSheet("background-color: #0d1b2a; border-bottom: 1px solid #1b4558;")
        sc_hdr_l = QtWidgets.QHBoxLayout(sc_hdr)
        sc_hdr_l.setContentsMargins(10, 0, 10, 0)
        self.preview_title_lbl = QtWidgets.QLabel("Vision Target Locked")
        self.preview_title_lbl.setStyleSheet("color: #d8f3f8; font-family: 'Segoe UI'; font-size: 12px; font-weight: 600; border: none;")
        sc_hdr_l.addWidget(self.preview_title_lbl)
        sc_hdr_l.addStretch()
        win_ctrls = QtWidgets.QLabel("—   ✕")
        win_ctrls.setStyleSheet("color: #6b96a8; font-size: 11px; border: none;")
        sc_hdr_l.addWidget(win_ctrls)
        sc_vbox.addWidget(sc_hdr)

        self.clean_preview = CleanScreenPreview(self.screen_card)
        sc_vbox.addWidget(self.clean_preview, 1)
        left_col.addWidget(self.screen_card, 42)

        # -------------------------------------------------------------
        # CENTER COLUMN: AudioSpectrumHUD (User Voice) + Chat Stream + Input
        # -------------------------------------------------------------
        center_col = QtWidgets.QVBoxLayout()
        center_col.setSpacing(8)
        body_hbox.addLayout(center_col, 46)

        self.spectrum_hud = AudioSpectrumHUD(self)
        center_col.addWidget(self.spectrum_hud, 28)

        # Chat Stream Header Row
        chat_hdr_row = QtWidgets.QHBoxLayout()
        chat_hdr_row.setContentsMargins(2, 0, 4, 0)
        chat_title = QtWidgets.QLabel("CHAT STREAM")
        chat_title.setStyleSheet(
            "color: #6fb8c4; font-family: 'Bahnschrift'; font-size: 13px; font-weight: 600; letter-spacing: 1px;"
        )
        chat_hdr_row.addWidget(chat_title)
        chat_hdr_row.addStretch()
        chat_min_close = QtWidgets.QLabel("—   ✕")
        chat_min_close.setStyleSheet("color: #6b96a8; font-size: 12px;")
        chat_hdr_row.addWidget(chat_min_close)
        center_col.addLayout(chat_hdr_row)

        # Chat Stream Scroll Area
        self.chat_frame = QtWidgets.QFrame()
        self.chat_frame.setObjectName("ChatFrame")
        self.chat_frame.setStyleSheet(
            "QFrame#ChatFrame { background-color: #070e18; border: 1.5px solid #193c4e; border-radius: 6px; }"
        )
        cf_vbox = QtWidgets.QVBoxLayout(self.chat_frame)
        cf_vbox.setContentsMargins(6, 6, 6, 6)

        self.chat_scroll = QtWidgets.QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.chat_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: #070e18; width: 6px; border-radius: 3px; }"
            "QScrollBar::handle:vertical { background: #1c4b62; border-radius: 3px; }"
        )
        self.chat_container = QtWidgets.QWidget()
        self.chat_container.setStyleSheet("background: transparent;")
        self.chat_vbox = QtWidgets.QVBoxLayout(self.chat_container)
        self.chat_vbox.setContentsMargins(8, 8, 8, 8)
        self.chat_vbox.setSpacing(12)
        self.chat_vbox.addStretch(1)
        self.chat_scroll.setWidget(self.chat_container)
        cf_vbox.addWidget(self.chat_scroll)
        center_col.addWidget(self.chat_frame, 62)

        # Center Input Box ("Say 'Atlas' or type a command...")
        self.input_wrap = QtWidgets.QFrame()
        self.input_wrap.setFixedHeight(44)
        self.input_wrap.setObjectName("InputWrap")
        self.input_wrap.setStyleSheet(
            "QFrame#InputWrap { background-color: #091320; border: 1.5px solid #1d495e; border-radius: 7px; }"
        )
        in_hbox = QtWidgets.QHBoxLayout(self.input_wrap)
        in_hbox.setContentsMargins(14, 0, 10, 0)

        self.input_box = QtWidgets.QLineEdit()
        self.input_box.setPlaceholderText('Say "Atlas" or type a command...')
        self.input_box.setStyleSheet(
            "QLineEdit { background: transparent; border: none; color: #e2f1f8; "
            "font-family: 'Segoe UI'; font-size: 14px; }"
        )
        self.input_box.returnPressed.connect(self._handle_send_click)
        in_hbox.addWidget(self.input_box, 1)

        send_plane_btn = QtWidgets.QPushButton("➤")
        send_plane_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        send_plane_btn.setFixedSize(32, 32)
        send_plane_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #529bb5; font-size: 17px; border: none; }"
            "QPushButton:hover { color: #00f0d4; }"
        )
        send_plane_btn.clicked.connect(self._handle_send_click)
        in_hbox.addWidget(send_plane_btn)
        center_col.addWidget(self.input_wrap)

        # -------------------------------------------------------------
        # RIGHT COLUMN: Glowing Button Matrix + Active Tasks 2x2 Grid
        # -------------------------------------------------------------
        right_col = QtWidgets.QVBoxLayout()
        right_col.setSpacing(10)
        body_hbox.addLayout(right_col, 27)

        # Top-Right Button Matrix Frame
        self.matrix_frame = QtWidgets.QFrame()
        self.matrix_frame.setObjectName("MatrixFrame")
        self.matrix_frame.setStyleSheet(
            "QFrame#MatrixFrame { background-color: #070e18; border: 1.5px solid #1a3c4e; border-radius: 8px; }"
        )
        m_grid = QtWidgets.QGridLayout(self.matrix_frame)
        m_grid.setContentsMargins(8, 8, 8, 8)
        m_grid.setSpacing(6)

        self.btn_tasks = GlowGridButton("Tasks", "tasks", checkable=True)
        self.btn_tasks.setChecked(True)
        self.btn_tasks.clicked.connect(lambda: self._switch_right_tab("tasks"))

        self.btn_memory = GlowGridButton("Memory", "memory", checkable=True)
        self.btn_memory.clicked.connect(lambda: self._switch_right_tab("memory"))

        self.btn_briefing = GlowGridButton("Briefing", "briefing", checkable=False)
        self.btn_briefing.clicked.connect(self.on_briefing)

        self.btn_undo = GlowGridButton("Undo", "undo", checkable=False)
        self.btn_undo.clicked.connect(self.on_undo)

        self.btn_quiet = GlowGridButton("Quiet", "quiet", checkable=True)
        self.btn_quiet.clicked.connect(self._handle_quiet_toggle)

        m_grid.addWidget(self.btn_tasks, 0, 0)
        m_grid.addWidget(self.btn_memory, 0, 1)
        m_grid.addWidget(self.btn_briefing, 0, 2)
        m_grid.addWidget(self.btn_undo, 0, 3)
        m_grid.addWidget(self.btn_quiet, 0, 4)

        # Row 2: Mode Selector (< AUTO >) + Pin + Clear + Mute
        mode_selector = QtWidgets.QFrame()
        mode_selector.setFixedHeight(54)
        mode_selector.setStyleSheet(
            "QFrame { background-color: #0a111b; border: 1.2px solid #264d5e; border-radius: 7px; }"
        )
        ms_l = QtWidgets.QHBoxLayout(mode_selector)
        ms_l.setContentsMargins(8, 4, 8, 4)
        lbl_l = QtWidgets.QLabel("‹")
        lbl_l.setStyleSheet("color: #6fb8c4; font-size: 16px; border: none;")
        lbl_c = QtWidgets.QLabel("AUTO")
        lbl_c.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl_c.setStyleSheet("color: #94bac8; font-family: 'Bahnschrift'; font-size: 10px; border: none;")
        lbl_r = QtWidgets.QLabel("›")
        lbl_r.setStyleSheet("color: #6fb8c4; font-size: 16px; border: none;")
        ms_l.addWidget(lbl_l)
        ms_l.addWidget(lbl_c, 1)
        ms_l.addWidget(lbl_r)
        m_grid.addWidget(mode_selector, 1, 0, 1, 2)

        self.btn_pin = GlowGridButton("Pin", "pin", checkable=True)
        self.btn_pin.clicked.connect(self._handle_pin_toggle)

        self.btn_clear = GlowGridButton("Clear", "clear", checkable=False)
        self.btn_clear.clicked.connect(self._handle_clear_click)

        self.btn_mute = GlowGridButton("Mute", "mute", checkable=True)
        self.btn_mute.clicked.connect(self._handle_mute_toggle)

        m_grid.addWidget(self.btn_pin, 1, 2)
        m_grid.addWidget(self.btn_clear, 1, 3)
        m_grid.addWidget(self.btn_mute, 1, 4)

        right_col.addWidget(self.matrix_frame)

        # Active Tasks & Reminders / Memory Inspector Frame
        self.tasks_frame = QtWidgets.QFrame()
        self.tasks_frame.setObjectName("TasksFrame")
        self.tasks_frame.setStyleSheet(
            "QFrame#TasksFrame { background-color: #070e18; border: 1.5px solid #1a3f52; border-radius: 8px; }"
        )
        tf_vbox = QtWidgets.QVBoxLayout(self.tasks_frame)
        tf_vbox.setContentsMargins(12, 10, 12, 10)
        tf_vbox.setSpacing(8)

        tf_hdr = QtWidgets.QHBoxLayout()
        self.right_panel_title = QtWidgets.QLabel("Active Tasks & Reminders")
        self.right_panel_title.setStyleSheet(
            "color: #dceef5; font-family: 'Segoe UI'; font-size: 14px; font-weight: 600;"
        )
        tf_hdr.addWidget(self.right_panel_title)
        tf_hdr.addStretch()
        close_lbl = QtWidgets.QLabel("✕")
        close_lbl.setStyleSheet("color: #79a6b8; font-size: 13px;")
        tf_hdr.addWidget(close_lbl)
        tf_vbox.addLayout(tf_hdr)

        # Divider line
        div = QtWidgets.QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background-color: #193a4d;")
        tf_vbox.addWidget(div)

        # Scrollable 2-Column Grid for Task Cards
        self.cards_scroll = QtWidgets.QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.cards_scroll.setStyleSheet("background: transparent; border: none;")
        self.cards_host = QtWidgets.QWidget()
        self.cards_grid = QtWidgets.QGridLayout(self.cards_host)
        self.cards_grid.setContentsMargins(2, 4, 2, 4)
        self.cards_grid.setSpacing(10)
        self.cards_scroll.setWidget(self.cards_host)
        tf_vbox.addWidget(self.cards_scroll, 1)

        # Subtle 4-point star emblem at bottom-right matching reference image
        star_row = QtWidgets.QHBoxLayout()
        star_row.addStretch()
        star_lbl = QtWidgets.QLabel("✦")
        star_lbl.setStyleSheet("color: rgba(130, 175, 195, 90); font-size: 28px;")
        star_row.addWidget(star_lbl)
        tf_vbox.addLayout(star_row)

        right_col.addWidget(self.tasks_frame, 1)

        # =============================================================
        # 4. BOTTOM FULL-WIDTH COMMAND DOCK
        # =============================================================
        bottom_hbox = QtWidgets.QHBoxLayout()
        bottom_hbox.setSpacing(12)
        root_vbox.addLayout(bottom_hbox)

        # Left/Center "BOTTOM COMMAND" telemetry bar
        self.bottom_cmd_bar = QtWidgets.QFrame()
        self.bottom_cmd_bar.setFixedHeight(44)
        self.bottom_cmd_bar.setObjectName("BottomCmdBar")
        self.bottom_cmd_bar.setStyleSheet(
            "QFrame#BottomCmdBar { background-color: #08111c; border: 1.5px solid #1b4357; border-radius: 7px; }"
        )
        bc_l = QtWidgets.QHBoxLayout(self.bottom_cmd_bar)
        bc_l.setContentsMargins(16, 0, 16, 0)
        self.action_status_lbl = QtWidgets.QLabel("BOTTOM COMMAND")
        self.action_status_lbl.setStyleSheet(
            "color: #6cd4dc; font-family: 'Bahnschrift'; font-size: 13px; font-weight: 600; letter-spacing: 0.8px;"
        )
        bc_l.addWidget(self.action_status_lbl)
        bc_l.addStretch()
        up_chev = QtWidgets.QLabel("⌃")
        up_chev.setStyleSheet("color: #78a9ba; font-size: 15px; font-weight: bold;")
        bc_l.addWidget(up_chev)
        bottom_hbox.addWidget(self.bottom_cmd_bar, 1)

        # Glowing Cyan "Vision + Screen Task" Button
        self.btn_vision_task = QtWidgets.QPushButton("Vision + Screen Task")
        self.btn_vision_task.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_vision_task.setFixedSize(195, 44)
        self.btn_vision_task.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00f5d4, stop:1 #00bbdc);"
            "  color: #031519; font-family: 'Segoe UI'; font-size: 14px; font-weight: bold;"
            "  border: 2px solid #88fff0; border-radius: 9px;"
            "}"
            "QPushButton:hover {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38ffe5, stop:1 #1ad1f0);"
            "}"
        )
        self.btn_vision_task.clicked.connect(self._handle_screen_click)
        bottom_hbox.addWidget(self.btn_vision_task)

        # Glowing Indigo "Execute / Send" Button
        self.btn_exec_send = QtWidgets.QPushButton("Execute / Send")
        self.btn_exec_send.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_exec_send.setFixedSize(175, 44)
        self.btn_exec_send.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #727cf5, stop:1 #5458e8);"
            "  color: #080b1a; font-family: 'Segoe UI'; font-size: 14px; font-weight: bold;"
            "  border: 2px solid #a5b4fc; border-radius: 9px;"
            "}"
            "QPushButton:hover {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b94f8, stop:1 #686cf0);"
            "}"
        )
        self.btn_exec_send.clicked.connect(self._handle_send_click)
        bottom_hbox.addWidget(self.btn_exec_send)

        # Circular Cyan Mic Button
        self.btn_round_mic = QtWidgets.QPushButton("🎙")
        self.btn_round_mic.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_round_mic.setFixedSize(44, 44)
        self.btn_round_mic.setStyleSheet(
            "QPushButton { background-color: #0a1926; color: #00f0d4; font-size: 18px; "
            "border: 1.8px solid #00c8b8; border-radius: 22px; }"
            "QPushButton:hover { background-color: #102e42; border-color: #5effef; }"
        )
        self.btn_round_mic.clicked.connect(self.on_manual_voice)
        bottom_hbox.addWidget(self.btn_round_mic)

        # Circular Red Stop Button
        self.btn_round_stop = QtWidgets.QPushButton("■")
        self.btn_round_stop.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_round_stop.setFixedSize(44, 44)
        self.btn_round_stop.setStyleSheet(
            "QPushButton { background-color: #211018; color: #ff4d5e; font-size: 16px; "
            "border: 1.8px solid #ef4444; border-radius: 22px; }"
            "QPushButton:hover { background-color: #3d1826; border-color: #ff808b; }"
        )
        self.btn_round_stop.clicked.connect(self.on_stop_all)
        bottom_hbox.addWidget(self.btn_round_stop)

        # Initial Welcome Assistant Card matching image_f9d099.jpg
        self.add_assistant_bubble(
            "**ATLAS Operator Online.**\n"
            "Advanced autonomous personal AI desktop assistant.\n"
            "• **Orbital AI & Voice Engine:** Solar HUD reacts to AI speech; Spectrum HUD tracks your microphone.\n"
            "• **Vision & App Control:** Locates UI controls visually and opens any installed PC application.\n"
            "• **Verified Guardrails:** Reversible task execution with instant hardware & desktop alerts."
        )

    # =================================================================
    # CHAT STREAM BUBBLES (Matching Reference Image Styling)
    # =================================================================
    def add_user_bubble(self, text: str):
        def _add():
            stamp = datetime.now().strftime("%I:%M %p").lstrip("0")
            row_w = QtWidgets.QWidget()
            row_l = QtWidgets.QHBoxLayout(row_w)
            row_l.setContentsMargins(4, 2, 4, 2)
            row_l.setSpacing(10)

            avatar = QtWidgets.QLabel("👤")
            avatar.setFixedSize(34, 34)
            avatar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            avatar.setStyleSheet(
                "background-color: #23274a; color: #9da8ff; font-size: 16px; "
                "border: 1px solid #48528a; border-radius: 17px;"
            )
            row_l.addWidget(avatar, 0, QtCore.Qt.AlignmentFlag.AlignTop)

            bubble = QtWidgets.QFrame()
            bubble.setStyleSheet(
                "QFrame { background-color: #161f30; border: 1px solid #2b3b54; border-radius: 10px; }"
            )
            b_vbox = QtWidgets.QVBoxLayout(bubble)
            b_vbox.setContentsMargins(14, 8, 14, 10)
            b_vbox.setSpacing(4)

            hdr = QtWidgets.QHBoxLayout()
            you_lbl = QtWidgets.QLabel("You")
            you_lbl.setStyleSheet("color: #70c8d8; font-weight: bold; font-size: 12px; border: none;")
            time_lbl = QtWidgets.QLabel(stamp)
            time_lbl.setStyleSheet("color: #6c8294; font-size: 11px; border: none;")
            hdr.addWidget(you_lbl)
            hdr.addStretch()
            hdr.addWidget(time_lbl)
            b_vbox.addLayout(hdr)

            msg_lbl = QtWidgets.QLabel(text)
            msg_lbl.setWordWrap(True)
            msg_lbl.setStyleSheet("color: #e6f1f8; font-family: 'Segoe UI'; font-size: 13px; border: none;")
            b_vbox.addWidget(msg_lbl)

            row_l.addWidget(bubble, 1)
            row_l.addStretch()

            self.chat_vbox.insertWidget(self.chat_vbox.count() - 1, row_w)
            QtCore.QTimer.singleShot(30, self._scroll_chat_bottom)

        self.safe_call(_add)

    def add_assistant_bubble(self, text: str):
        def _add():
            row_w = QtWidgets.QWidget()
            row_l = QtWidgets.QHBoxLayout(row_w)
            row_l.setContentsMargins(4, 2, 4, 2)
            row_l.setSpacing(10)

            avatar = QtWidgets.QLabel("⚛")
            avatar.setFixedSize(34, 34)
            avatar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            avatar.setStyleSheet(
                "background-color: #0b2530; color: #00f0d4; font-size: 18px; "
                "border: 1.5px solid #00c8b8; border-radius: 17px;"
            )
            row_l.addWidget(avatar, 0, QtCore.Qt.AlignmentFlag.AlignTop)

            card = QtWidgets.QFrame()
            card.setStyleSheet(
                "QFrame { background-color: #0b1824; border: 1.5px solid #1e5263; border-radius: 10px; }"
            )
            c_vbox = QtWidgets.QVBoxLayout(card)
            c_vbox.setContentsMargins(16, 10, 16, 12)
            c_vbox.setSpacing(6)

            hdr = QtWidgets.QHBoxLayout()
            asst_lbl = QtWidgets.QLabel("Assistant")
            asst_lbl.setStyleSheet("color: #9ab8c8; font-size: 12px; font-weight: 600; border: none;")
            new_lbl = QtWidgets.QLabel("Newest 〰")
            new_lbl.setStyleSheet("color: #48b8a8; font-size: 11px; border: none;")
            hdr.addWidget(asst_lbl)
            hdr.addStretch()
            hdr.addWidget(new_lbl)
            c_vbox.addLayout(hdr)

            lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
            icons = ["🚀", "⚙️", "🛡️", "⚡"]
            bullet_idx = 0

            for idx, ln in enumerate(lines):
                clean_ln = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", ln)
                if idx == 0 and ("Online" in ln or "VERIFIED" in ln):
                    plain = re.sub(r"<[^>]+>", "", clean_ln)
                    title_lbl = QtWidgets.QLabel(plain)
                    title_lbl.setWordWrap(True)
                    title_lbl.setStyleSheet(
                        "color: #26f0a8; font-family: 'Segoe UI'; font-size: 14px; font-weight: bold; border: none;"
                    )
                    c_vbox.addWidget(title_lbl)
                elif ln.startswith(("•", "-", "*")):
                    item_text = clean_ln.lstrip("•-* ").strip()
                    feat_row = QtWidgets.QHBoxLayout()
                    feat_row.setSpacing(10)
                    ic = QtWidgets.QLabel(icons[bullet_idx % len(icons)])
                    ic.setFixedSize(26, 26)
                    ic.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                    ic.setStyleSheet(
                        "background-color: #0d2b38; color: #00e5ff; font-size: 14px; "
                        "border: 1px solid #186478; border-radius: 6px;"
                    )
                    feat_row.addWidget(ic, 0, QtCore.Qt.AlignmentFlag.AlignTop)

                    flbl = QtWidgets.QLabel(item_text)
                    flbl.setWordWrap(True)
                    flbl.setTextFormat(QtCore.Qt.TextFormat.RichText)
                    flbl.setStyleSheet("color: #d6eaf2; font-family: 'Segoe UI'; font-size: 13px; border: none;")
                    feat_row.addWidget(flbl, 1)
                    c_vbox.addLayout(feat_row)
                    bullet_idx += 1
                else:
                    blbl = QtWidgets.QLabel(clean_ln)
                    blbl.setWordWrap(True)
                    blbl.setTextFormat(QtCore.Qt.TextFormat.RichText)
                    blbl.setStyleSheet("color: #dcebf2; font-family: 'Segoe UI'; font-size: 13px; border: none;")
                    c_vbox.addWidget(blbl)

            row_l.addWidget(card, 1)
            self.chat_vbox.insertWidget(self.chat_vbox.count() - 1, row_w)
            QtCore.QTimer.singleShot(30, self._scroll_chat_bottom)

        self.safe_call(_add)

    def _scroll_chat_bottom(self):
        bar = self.chat_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    # =================================================================
    # RIGHT PANEL: 2x2 TASK & MEMORY CARDS (Matching Reference Image)
    # =================================================================
    def _switch_right_tab(self, tab: str):
        self.active_right_tab = tab
        self.btn_tasks.setChecked(tab == "tasks")
        self.btn_memory.setChecked(tab == "memory")
        self.btn_tasks.update()
        self.btn_memory.update()

        if tab == "tasks":
            self.right_panel_title.setText("Active Tasks & Reminders")
            self.render_tasks(self._cached_tasks)
        else:
            self.right_panel_title.setText("Memory Inspector")
            self.render_memories(self._cached_memories)

    def _clear_cards_grid(self):
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _create_cyber_card(
        self,
        badge_icon: str,
        title_text: str,
        footer_left: str,
        is_teal_glow: bool = False,
        on_action: Callable = None,
        action_symbol: str = "✔",
    ) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setMinimumHeight(138)
        if is_teal_glow:
            card.setStyleSheet(
                "QFrame { background-color: #0b222c; border: 1.5px solid #28b8a8; border-radius: 8px; }"
            )
        else:
            card.setStyleSheet(
                "QFrame { background-color: #0c1624; border: 1.5px solid #264862; border-radius: 8px; }"
            )

        vbox = QtWidgets.QVBoxLayout(card)
        vbox.setContentsMargins(10, 10, 10, 8)
        vbox.setSpacing(6)

        top_r = QtWidgets.QHBoxLayout()
        ic_lbl = QtWidgets.QLabel(badge_icon)
        ic_lbl.setFixedSize(26, 26)
        ic_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        ic_lbl.setStyleSheet(
            "background-color: #102a38; color: #48e5d0; font-size: 13px; "
            "border: 1px solid #287a88; border-radius: 5px;"
        )
        top_r.addWidget(ic_lbl)
        top_r.addStretch()
        dots = QtWidgets.QLabel("•••")
        dots.setStyleSheet("color: #6c92a4; font-size: 11px; border: none;")
        top_r.addWidget(dots)
        vbox.addLayout(top_r)

        t_lbl = QtWidgets.QLabel(title_text)
        t_lbl.setWordWrap(True)
        t_lbl.setStyleSheet("color: #e4f2f8; font-family: 'Segoe UI'; font-size: 12px; font-weight: 600; border: none;")
        vbox.addWidget(t_lbl, 1)

        foot = QtWidgets.QFrame()
        foot.setFixedHeight(24)
        foot.setStyleSheet("background-color: #091420; border: 1px solid #183848; border-radius: 4px;")
        f_hbox = QtWidgets.QHBoxLayout(foot)
        f_hbox.setContentsMargins(6, 0, 6, 0)
        fl_lbl = QtWidgets.QLabel(footer_left)
        fl_lbl.setStyleSheet("color: #5ec8b8; font-family: 'Bahnschrift'; font-size: 10px; border: none;")
        f_hbox.addWidget(fl_lbl)
        f_hbox.addStretch()

        if on_action:
            act_btn = QtWidgets.QPushButton(action_symbol)
            act_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            act_btn.setFixedSize(22, 18)
            act_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #00f5d4; font-size: 11px; font-weight: bold; border: none; }"
                "QPushButton:hover { color: #ffffff; }"
            )
            act_btn.clicked.connect(on_action)
            f_hbox.addWidget(act_btn)
        else:
            icons_r = QtWidgets.QLabel("🕒 ❐")
            icons_r.setStyleSheet("color: #6c9ab0; font-size: 10px; border: none;")
            f_hbox.addWidget(icons_r)

        vbox.addWidget(foot)
        return card

    def render_tasks(self, tasks: List[Dict[str, Any]]):
        def _r():
            self._cached_tasks = list(tasks)
            if self.active_right_tab != "tasks":
                return
            self._clear_cards_grid()

            # If user has no active tasks yet, show the 4 default operator status cards from the design
            if not tasks:
                placeholders = [
                    ("☑", "Command Active\nOperator Online.", "T1/2", True),
                    ("📋", "Notice Long Live\nReminders.", "T1/2", False),
                    ("📅", "Tasks Card Status\nTarget Renders.", "T1/2", True),
                    ("🔔", "Update Active\nTasks & Reminders.", "T2/2", False),
                ]
                for idx, (ic, title, ft, glow) in enumerate(placeholders):
                    card = self._create_cyber_card(ic, title, ft, is_teal_glow=glow)
                    self.cards_grid.addWidget(card, idx // 2, idx % 2)
                return

            badges = ["☑", "📋", "📅", "🔔"]
            for idx, t in enumerate(tasks):
                tid = t["id"]
                card = self._create_cyber_card(
                    badges[idx % len(badges)],
                    t["title"],
                    t.get("due_time", "T1/2")[-5:],
                    is_teal_glow=(idx % 2 == 0),
                    on_action=lambda _=False, task_id=tid: self.on_complete_task(task_id),
                    action_symbol="✔",
                )
                self.cards_grid.addWidget(card, idx // 2, idx % 2)

        self.safe_call(_r)

    def render_memories(self, data: Dict[str, Any]):
        def _rm():
            self._cached_memories = dict(data)
            if self.active_right_tab != "memory":
                return
            self._clear_cards_grid()

            entries = []
            for cat in ("profile", "workspace"):
                for k, v in data.get(cat, {}).items():
                    entries.append((cat, k, v.get("value", "")))

            if not entries:
                card = self._create_cyber_card("🧠", "No Saved Memories\nSay 'Remember that...'", "MEM 0/0", True)
                self.cards_grid.addWidget(card, 0, 0, 1, 2)
                return

            for idx, (cat, k, val) in enumerate(entries):
                card = self._create_cyber_card(
                    "🧠",
                    f"{k.title()}: {val}",
                    cat.upper(),
                    is_teal_glow=(idx % 2 == 0),
                    on_action=lambda _=False, c=cat, key=k: self.on_delete_memory(c, key),
                    action_symbol="✕",
                )
                self.cards_grid.addWidget(card, idx // 2, idx % 2)

        self.safe_call(_rm)

    # =================================================================
    # THREAD-SAFE STATE & AUDIO ROUTING METHODS
    # =================================================================
    def set_status(self, text: str, color: str = "#10b981", disable_buttons: bool = False):
        def _u():
            self.spectrum_hud.set_status_display(text, color)
            self.btn_vision_task.setEnabled(not disable_buttons)
            self.btn_exec_send.setEnabled(not disable_buttons)
            if not disable_buttons:
                self.action_status_lbl.setText("BOTTOM COMMAND")
        self.safe_call(_u)

    def set_action_banner(self, text: str):
        def _b():
            self.action_status_lbl.setText(text.upper() if text else "BOTTOM COMMAND")
        self.safe_call(_b)

    def update_visualizer(self, levels: List[float]):
        """Feeds user microphone levels into the top-center AudioSpectrumHUD."""
        self.safe_call(lambda: self.spectrum_hud.push_external_mic_levels(levels))

    def set_ai_voice_level(self, level: float):
        """Feeds AI TTS voice levels into the left AtomicSolarHUD (Requirement 5)."""
        self.safe_call(lambda: self.solar_hud.set_ai_voice_level(level))

    def update_input_box(self, text: str):
        def _s():
            self.input_box.setText(text)
            self.input_box.setFocus()
        self.safe_call(_s)

    def show_screen_preview(self, image_path: str):
        def _sh():
            self.clean_preview.set_image(image_path)
        self.safe_call(_sh)

    def show_approval_prompt(self, payload: Dict[str, str]):
        def _p():
            txt = (
                f"⚠️ {payload['level']}  |  Action: {payload['action']}  |  "
                f"Target: {payload['target']}  |  Consequences: {payload['consequences']}"
            )
            self.approval_lbl.setText(txt)
            self.approval_bar.show()
        self.safe_call(_p)

    def _resolve_approval(self, choice: str):
        self.approval_bar.hide()
        self.on_approval_decision(choice)

    # =================================================================
    # BUTTON CLICK HANDLERS
    # =================================================================
    def _handle_send_click(self):
        q = self.input_box.text().strip()
        if not q:
            return
        self.input_box.clear()
        self.add_user_bubble(q)
        self.on_ask_text(q)

    def _handle_screen_click(self):
        q = self.input_box.text().strip() or "Inspect the screen and help me with what is currently open."
        self.input_box.clear()
        self.add_user_bubble(f"🖥️ [Vision Task]: {q}")
        self.on_ask_screen(q)

    def _handle_clear_click(self):
        while self.chat_vbox.count() > 1:
            item = self.chat_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.add_assistant_bubble("**Conversation cleared.**\nReady for your next command.")
        self.on_clear_chat()

    def _handle_pin_toggle(self):
        self.is_pinned = self.btn_pin.isChecked()
        self.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, self.is_pinned)
        self.show()

    def _handle_mute_toggle(self):
        self.is_muted = self.btn_mute.isChecked()
        self.on_toggle_mute(self.is_muted)

    def _handle_quiet_toggle(self):
        self.is_quiet = self.btn_quiet.isChecked()
        self.on_toggle_quiet(self.is_quiet)