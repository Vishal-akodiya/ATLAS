import os
import re
import sys
import math
import threading
from datetime import datetime, timedelta
from typing import Callable, List, Dict, Any, Optional

import numpy as np
import psutil
import sounddevice as sd
from PySide6 import QtCore, QtWidgets, QtGui

from core.solar_hud import AtomicSolarHUD
from core.spectrum_hud import AudioSpectrumHUD
from actions.reminder import parse_due_datetime


# =====================================================================
# PROCEDURAL SCI-FI UI SOUND SYNTHESIZER (Zero External Assets Needed)
# =====================================================================
class CyberSoundEngine:
    """Synthesizes ultra-short, tactile sci-fi UI sounds in real time via numpy + sounddevice."""

    SAMPLE_RATE = 44100

    def __init__(self):
        self.enabled = True
        self._cache: Dict[str, np.ndarray] = {}
        self._prebuild_sounds()

    def _prebuild_sounds(self):
        sr = self.SAMPLE_RATE

        # 1. Hover tick (6ms ultra-subtle high-frequency capacitive tick)
        t_hov = np.linspace(0, 0.006, int(sr * 0.006), False)
        env_hov = np.exp(-t_hov * 450.0)
        self._cache["hover"] = (np.sin(2 * np.pi * 2600 * t_hov) * env_hov * 0.045).astype(np.float32)

        # 2. Standard button click (24ms crisp dual-tone cyber latch)
        t_clk = np.linspace(0, 0.024, int(sr * 0.024), False)
        env_clk = np.exp(-t_clk * 140.0)
        freq_clk = np.linspace(980, 1520, len(t_clk))
        wave_clk = np.sin(2 * np.pi * np.cumsum(freq_clk) / sr) + 0.35 * np.sin(2 * np.pi * 2400 * t_clk)
        self._cache["click"] = (wave_clk * env_clk * 0.12).astype(np.float32)

        # 3. Tab / Mode switch (45ms smooth frequency sweep)
        t_sw = np.linspace(0, 0.045, int(sr * 0.045), False)
        env_sw = np.sin(np.pi * (t_sw / 0.045)) ** 0.8
        freq_sw = np.linspace(620, 1280, len(t_sw))
        self._cache["switch"] = (np.sin(2 * np.pi * np.cumsum(freq_sw) / sr) * env_sw * 0.11).astype(np.float32)

        # 4. Command Send / Execute (90ms ascending two-note confirmation)
        t_snd = np.linspace(0, 0.090, int(sr * 0.090), False)
        half = len(t_snd) // 2
        w1 = np.sin(2 * np.pi * 880 * t_snd[:half]) * np.exp(-t_snd[:half] * 35.0)
        w2 = np.sin(2 * np.pi * 1318.5 * t_snd[half:]) * np.exp(-(t_snd[half:] - 0.045) * 30.0)
        self._cache["send"] = (np.concatenate([w1, w2]) * 0.14).astype(np.float32)

        # 5. Alert / Approval Prompt (160ms double amber pulse)
        t_al = np.linspace(0, 0.160, int(sr * 0.160), False)
        pulse = (np.sin(2 * np.pi * 12.5 * t_al) > 0).astype(np.float32)
        carrier = np.sin(2 * np.pi * 1046.5 * t_al) + 0.4 * np.sin(2 * np.pi * 523.25 * t_al)
        self._cache["alert"] = (carrier * pulse * np.exp(-t_al * 8.0) * 0.16).astype(np.float32)

        # 6. Emergency Stop / Deny (140ms descending power-down)
        t_err = np.linspace(0, 0.140, int(sr * 0.140), False)
        freq_err = np.linspace(520, 160, len(t_err))
        env_err = np.exp(-t_err * 16.0)
        self._cache["stop"] = (np.sin(2 * np.pi * np.cumsum(freq_err) / sr) * env_err * 0.18).astype(np.float32)

    def play(self, name: str):
        if not self.enabled or name not in self._cache:
            return
        samples = self._cache[name]

        def _Play_async():
            try:
                sd.play(samples, self.SAMPLE_RATE, blocking=False)
            except Exception:
                pass

        threading.Thread(target=_Play_async, daemon=True).start()


# =====================================================================
# TOP CYBERNETIC HEADER BANNER WITH LIVE TELEMETRY
# =====================================================================
class CyberHeaderBanner(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        self.cpu_pct = 0.0
        self.ram_pct = 0.0
        self.active_mode = "AUTO"
        self.clock_str = datetime.now().strftime("%H:%M:%S")

        self._telem_timer = QtCore.QTimer(self)
        self._telem_timer.timeout.connect(self._refresh_telemetry)
        self._telem_timer.start(1500)
        self._refresh_telemetry()

    def _refresh_telemetry(self):
        try:
            self.cpu_pct = psutil.cpu_percent(interval=None)
            self.ram_pct = psutil.virtual_memory().percent
            self.clock_str = datetime.now().strftime("%H:%M:%S")
            self.update()
        except Exception:
            pass

    def set_mode_badge(self, mode: str):
        self.active_mode = mode.upper()
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx = w / 2.0

        painter.fillRect(self.rect(), QtGui.QColor(5, 10, 18))

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
        grad.setColorAt(0.0, QtGui.QColor(12, 24, 38, 235))
        grad.setColorAt(1.0, QtGui.QColor(7, 14, 24, 245))
        painter.setBrush(QtGui.QBrush(grad))

        border_pen = QtGui.QPen(QtGui.QColor(35, 95, 120, 200))
        border_pen.setWidthF(1.6)
        painter.setPen(border_pen)
        painter.drawPolygon(top_poly)

        # Glowing cyan bottom lip under "ATLAS"
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

        # Left Circular Tech Emblem + Title
        emblem_cx, emblem_cy = 38.0, 26.0
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 225, 220, 210), 2.2))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QtCore.QPointF(emblem_cx, emblem_cy), 14, 14)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 225, 220, 130), 1.4, QtCore.Qt.PenStyle.DotLine))
        painter.drawEllipse(QtCore.QPointF(emblem_cx, emblem_cy), 9, 9)
        painter.setBrush(QtGui.QColor(0, 240, 215))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(QtCore.QPointF(emblem_cx, emblem_cy), 3.2, 3.2)

        gem_font = QtGui.QFont("Bahnschrift", 12, QtGui.QFont.Weight.Bold)
        gem_font.setLetterSpacing(QtGui.QFont.SpacingType.AbsoluteSpacing, 1.2)
        painter.setFont(gem_font)
        painter.setPen(QtGui.QColor(80, 215, 230))
        painter.drawText(QtCore.QPointF(62, 23), "GEMINI 3.1")

        sub_font = QtGui.QFont("Bahnschrift", 8, QtGui.QFont.Weight.DemiBold)
        sub_font.setLetterSpacing(QtGui.QFont.SpacingType.AbsoluteSpacing, 0.8)
        painter.setFont(sub_font)
        painter.setPen(QtGui.QColor(150, 185, 200))
        painter.drawText(QtCore.QPointF(62, 37), "FLASH-LITE  |  AUTONOMOUS DESKTOP OPERATOR")

        # Right Live Telemetry Readout (CPU, RAM, Mode, Clock)
        right_base = w - 340
        if right_base > cx + 240:
            t_font = QtGui.QFont("Bahnschrift", 9, QtGui.QFont.Weight.DemiBold)
            painter.setFont(t_font)

            # CPU Pill
            painter.setPen(QtGui.QColor(130, 195, 210))
            painter.drawText(QtCore.QPointF(right_base, 22), f"CPU {int(self.cpu_pct)}%")
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor(18, 42, 58))
            painter.drawRoundedRect(QtCore.QRectF(right_base, 27, 64, 5), 2, 2)
            cpu_col = QtGui.QColor(0, 240, 212) if self.cpu_pct < 75 else QtGui.QColor(245, 158, 11)
            painter.setBrush(cpu_col)
            painter.drawRoundedRect(QtCore.QRectF(right_base, 27, max(4.0, 64 * (self.cpu_pct / 100.0)), 5), 2, 2)

            # RAM Pill
            ram_x = right_base + 82
            painter.setPen(QtGui.QColor(130, 195, 210))
            painter.drawText(QtCore.QPointF(ram_x, 22), f"RAM {int(self.ram_pct)}%")
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor(18, 42, 58))
            painter.drawRoundedRect(QtCore.QRectF(ram_x, 27, 64, 5), 2, 2)
            painter.setBrush(QtGui.QColor(56, 189, 248))
            painter.drawRoundedRect(QtCore.QRectF(ram_x, 27, max(4.0, 64 * (self.ram_pct / 100.0)), 5), 2, 2)

            # Mode Badge
            mode_x = right_base + 164
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 215, 200, 160), 1.0))
            painter.setBrush(QtGui.QColor(10, 42, 52, 200))
            painter.drawRoundedRect(QtCore.QRectF(mode_x, 13, 68, 22), 4, 4)
            painter.setPen(QtGui.QColor(110, 250, 230))
            painter.drawText(QtCore.QRectF(mode_x, 13, 68, 22), QtCore.Qt.AlignmentFlag.AlignCenter, self.active_mode)

            # Clock
            clk_font = QtGui.QFont("Bahnschrift", 11, QtGui.QFont.Weight.Bold)
            painter.setFont(clk_font)
            painter.setPen(QtGui.QColor(195, 235, 248))
            painter.drawText(QtCore.QRectF(mode_x + 76, 12, 85, 24), QtCore.Qt.AlignmentFlag.AlignVCenter, self.clock_str)

        painter.end()


# =====================================================================
# TOP-RIGHT GLOWING MATRIX BUTTON WITH MICRO-SOUND FEEDBACK
# =====================================================================
class GlowGridButton(QtWidgets.QPushButton):
    """Square cybernetic icon+label button with neon teal glow and acoustic feedback."""

    def __init__(
        self,
        label: str,
        icon_type: str,
        checkable: bool = False,
        sound_engine: Optional[CyberSoundEngine] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.label_text = label
        self.icon_type = icon_type
        self.sfx = sound_engine
        self.setCheckable(checkable)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(62, 54)

    def enterEvent(self, event):
        if self.sfx:
            self.sfx.play("hover")
        self.update()
        super().enterEvent(event)

    def mousePressEvent(self, event):
        if self.sfx:
            self.sfx.play("click")
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        selected = self.isChecked() or self.isDown()
        hovered = self.underMouse()

        rect = QtCore.QRectF(3, 3, self.width() - 6, self.height() - 6)

        if selected:
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
            bg_col = QtGui.QColor(16, 28, 42, 235) if hovered else QtGui.QColor(10, 17, 27, 220)
            painter.setBrush(bg_col)
            border_pen = QtGui.QPen(QtGui.QColor(55, 125, 150, 210) if hovered else QtGui.QColor(45, 95, 115, 130), 1.2)
            icon_color = QtGui.QColor(165, 235, 250) if hovered else QtGui.QColor(110, 175, 195)
            text_color = QtGui.QColor(195, 225, 238) if hovered else QtGui.QColor(145, 175, 190)

        painter.setPen(border_pen)
        painter.drawRoundedRect(rect, 7, 7)

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

        lbl_font = QtGui.QFont("Bahnschrift", 8, QtGui.QFont.Weight.DemiBold)
        painter.setFont(lbl_font)
        painter.setPen(text_color)
        painter.drawText(QtCore.QRectF(0, 31, self.width(), 18), QtCore.Qt.AlignmentFlag.AlignCenter, self.label_text)
        painter.end()


# =====================================================================
# CLEAN SCREEN PREVIEW WIDGET (With Click-to-Inspect & Scan Sweep)
# =====================================================================
class CleanScreenPreview(QtWidgets.QWidget):
    """Displays the live screen capture inside corner HUD brackets with click-to-zoom."""

    clicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap: Optional[QtGui.QPixmap] = None
        self.last_image_path: str = ""
        self.last_capture_time: str = "Awaiting Capture"
        self.scan_y: float = -1.0
        self.setMinimumHeight(180)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        self._scan_timer = QtCore.QTimer(self)
        self._scan_timer.timeout.connect(self._step_scan)

    def set_image(self, image_path: str):
        if os.path.exists(image_path):
            self.last_image_path = image_path
            self.pixmap = QtGui.QPixmap(image_path)
            self.last_capture_time = datetime.now().strftime("%H:%M:%S")
            self.scan_y = 0.0
            self._scan_timer.start(16)
            self.update()

    def _step_scan(self):
        self.scan_y += 0.045
        if self.scan_y > 1.0:
            self.scan_y = -1.0
            self._scan_timer.stop()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

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

            # Subtle timestamp pill in bottom-right corner
            pill_r = QtCore.QRectF(inner.right() - 78, inner.bottom() - 22, 72, 18)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor(5, 12, 20, 200))
            painter.drawRoundedRect(pill_r, 4, 4)
            painter.setFont(QtGui.QFont("Bahnschrift", 8))
            painter.setPen(QtGui.QColor(90, 225, 240))
            painter.drawText(pill_r, QtCore.Qt.AlignmentFlag.AlignCenter, self.last_capture_time)
        else:
            grid_pen = QtGui.QPen(QtGui.QColor(18, 48, 68, 95), 1.0)
            painter.setPen(grid_pen)
            for gx in range(int(inner.left()), int(inner.right()), 24):
                painter.drawLine(gx, int(inner.top()), gx, int(inner.bottom()))
            for gy in range(int(inner.top()), int(inner.bottom()), 24):
                painter.drawLine(int(inner.left()), gy, int(inner.right()), gy)

            font = QtGui.QFont("Bahnschrift", 10)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(70, 165, 190, 190))
            painter.drawText(
                inner,
                QtCore.Qt.AlignmentFlag.AlignCenter,
                "LIVE SCREEN FEED READY\nClick '⟳' to capture desktop",
            )

        # Animated scanline sweep on fresh capture
        if 0.0 <= self.scan_y <= 1.0:
            sy = inner.top() + self.scan_y * inner.height()
            scan_pen = QtGui.QPen(QtGui.QColor(0, 245, 212, 190), 2.0)
            painter.setPen(scan_pen)
            painter.drawLine(QtCore.QPointF(inner.left(), sy), QtCore.QPointF(inner.right(), sy))

        # Corner Cyan L-Brackets
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
    OPERATING_MODES = ["AUTO", "VISION", "STEALTH"]

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
        on_create_task: Optional[Callable[[str, str, str], None]] = None,
        on_save_memory: Optional[Callable[[str, str, str], None]] = None,
        on_refresh_screen: Optional[Callable[[], None]] = None,
        on_read_logs: Optional[Callable[[], str]] = None,
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
        self.on_create_task = on_create_task
        self.on_save_memory = on_save_memory
        self.on_refresh_screen = on_refresh_screen
        self.on_read_logs = on_read_logs

        self.sfx = CyberSoundEngine()
        self._bridge = _UISignalBridge()
        self._bridge.call_signal.connect(self._execute_callable)

        self.is_pinned = False
        self.is_muted = False
        self.is_quiet = False
        self.mode_idx = 0
        self.operator_mode = self.OPERATING_MODES[0]
        self.active_right_tab = "tasks"
        self._cached_tasks: List[Dict[str, Any]] = []
        self._cached_memories: Dict[str, Any] = {}

        self.setWindowTitle("ATLAS - Personal AI System Operator")
        self.resize(1380, 820)
        self.setMinimumSize(1120, 700)
        self.setStyleSheet("QMainWindow { background-color: #050a12; }")

        self._build_ui()
        self._task_clock = QtCore.QTimer(self)
        self._task_clock.setInterval(1000)
        self._task_clock.timeout.connect(self._refresh_task_due_labels)
        self._task_clock.start()

    @QtCore.Slot(object)
    def _execute_callable(self, fn):
        try:
            fn()
        except Exception as e:
            print(f"[UI Signal Error]: {e}")

    def safe_call(self, func, *args, **kwargs):
        self._bridge.call_signal.emit(lambda: func(*args, **kwargs))

    def withdraw(self):
        self.hide()

    def deiconify(self):
        self.show()

    def mainloop(self):
        self.show()
        self._qt_app.exec()

    # =================================================================
    # BUILD PROPORTIONAL 3-COLUMN HUD LAYOUT
    # =================================================================
    def _build_ui(self):
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        root_vbox = QtWidgets.QVBoxLayout(central)
        # Wider gutters and calmer spacing let the dark background breathe.
        root_vbox.setContentsMargins(24, 16, 24, 18)
        root_vbox.setSpacing(14)

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
                f"QPushButton:hover {{ opacity: 0.9; }}"
            )
            b.clicked.connect(lambda _=False, c=code: self._resolve_approval(c))
            app_layout.addWidget(b)
        self.approval_bar.hide()
        root_vbox.addWidget(self.approval_bar)

        # 3. THREE-COLUMN MAIN BODY (Left 27%, Center 46%, Right 27%)
        body_hbox = QtWidgets.QHBoxLayout()
        body_hbox.setSpacing(22)
        root_vbox.addLayout(body_hbox, 1)

        # -------------------------------------------------------------
        # LEFT COLUMN: AtomicSolarHUD (AI Voice) + Clean Screen Preview
        # -------------------------------------------------------------
        left_col = QtWidgets.QVBoxLayout()
        left_col.setSpacing(14)
        body_hbox.addLayout(left_col, 24)

        self.solar_hud = AtomicSolarHUD(self)
        left_col.addWidget(self.solar_hud, 58)

        sp_title = QtWidgets.QLabel("SCREEN PREVIEW")
        sp_title.setStyleSheet(
            "color: #6fb8c4; font-family: 'Bahnschrift'; font-size: 13px; font-weight: 600; letter-spacing: 1px;"
        )
        left_col.addWidget(sp_title)

        self.screen_card = QtWidgets.QFrame()
        self.screen_card.setObjectName("ScreenCard")
        self.screen_card.setStyleSheet(
            "QFrame#ScreenCard { background-color: #08111d; border: 1.5px solid #1b4558; border-radius: 6px; }"
        )
        sc_vbox = QtWidgets.QVBoxLayout(self.screen_card)
        sc_vbox.setContentsMargins(2, 2, 2, 2)
        sc_vbox.setSpacing(0)

        sc_hdr = QtWidgets.QFrame()
        sc_hdr.setFixedHeight(28)
        sc_hdr.setStyleSheet("background-color: #0d1b2a; border-bottom: 1px solid #1b4558;")
        sc_hdr_l = QtWidgets.QHBoxLayout(sc_hdr)
        sc_hdr_l.setContentsMargins(10, 0, 6, 0)
        sc_hdr_l.setSpacing(4)

        self.preview_title_lbl = QtWidgets.QLabel("Vision Target Ready")
        self.preview_title_lbl.setStyleSheet(
            "color: #d8f3f8; font-family: 'Segoe UI'; font-size: 12px; font-weight: 600; border: none;"
        )
        sc_hdr_l.addWidget(self.preview_title_lbl)
        sc_hdr_l.addStretch()

        btn_snap = QtWidgets.QPushButton("⟳")
        btn_snap.setToolTip("Capture Live Screenshot Now")
        btn_snap.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn_snap.setFixedSize(22, 22)
        btn_snap.setStyleSheet(
            "QPushButton { background: transparent; color: #6fb8c4; font-size: 13px; border: none; }"
            "QPushButton:hover { color: #00f5d4; }"
        )
        btn_snap.clicked.connect(self._handle_refresh_preview)
        sc_hdr_l.addWidget(btn_snap)

        btn_zoom = QtWidgets.QPushButton("⤢")
        btn_zoom.setToolTip("Expand Fullscreen Preview")
        btn_zoom.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn_zoom.setFixedSize(22, 22)
        btn_zoom.setStyleSheet(
            "QPushButton { background: transparent; color: #6fb8c4; font-size: 13px; border: none; }"
            "QPushButton:hover { color: #00f5d4; }"
        )
        btn_zoom.clicked.connect(self._open_preview_lightbox)
        sc_hdr_l.addWidget(btn_zoom)

        sc_vbox.addWidget(sc_hdr)

        self.clean_preview = CleanScreenPreview(self.screen_card)
        self.clean_preview.clicked.connect(self._open_preview_lightbox)
        sc_vbox.addWidget(self.clean_preview, 1)
        left_col.addWidget(self.screen_card, 42)

        # -------------------------------------------------------------
        # CENTER COLUMN: AudioSpectrumHUD + Chat Stream + Input
        # -------------------------------------------------------------
        center_col = QtWidgets.QVBoxLayout()
        center_col.setSpacing(12)
        body_hbox.addLayout(center_col, 49)

        self.spectrum_hud = AudioSpectrumHUD(self)
        center_col.addWidget(self.spectrum_hud, 22)

        chat_hdr_row = QtWidgets.QHBoxLayout()
        chat_hdr_row.setContentsMargins(2, 0, 4, 0)
        chat_title = QtWidgets.QLabel("CHAT STREAM")
        chat_title.setStyleSheet(
            "color: #6fb8c4; font-family: 'Bahnschrift'; font-size: 13px; font-weight: 600; letter-spacing: 1px;"
        )
        chat_hdr_row.addWidget(chat_title)
        chat_hdr_row.addStretch()

        self.msg_count_lbl = QtWidgets.QLabel("ONLINE")
        self.msg_count_lbl.setStyleSheet("color: #48b8a8; font-family: 'Bahnschrift'; font-size: 11px;")
        chat_hdr_row.addWidget(self.msg_count_lbl)
        center_col.addLayout(chat_hdr_row)

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
        self.chat_vbox = QtWidgets.QVBLayout(self.chat_container) if hasattr(QtWidgets, "QVBLayout") else QtWidgets.QVBoxLayout(self.chat_container)
        self.chat_vbox.setContentsMargins(8, 8, 8, 8)
        self.chat_vbox.setSpacing(12)
        self.chat_vbox.addStretch(1)
        self.chat_scroll.setWidget(self.chat_container)
        cf_vbox.addWidget(self.chat_scroll)
        center_col.addWidget(self.chat_frame, 68)

        # Center Input Box
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
        send_plane_btn.setToolTip("Execute Command")
        send_plane_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        send_plane_btn.setFixedSize(32, 32)
        send_plane_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #529bb5; font-size: 16px; border: none; }"
            "QPushButton:hover { color: #00f0d4; }"
        )
        send_plane_btn.clicked.connect(self._handle_send_click)
        in_hbox.addWidget(send_plane_btn)
        center_col.addWidget(self.input_wrap)

        # -------------------------------------------------------------
        # RIGHT COLUMN: Glowing Button Matrix + Multi-Tab Inspector
        # -------------------------------------------------------------
        right_col = QtWidgets.QVBoxLayout()
        right_col.setSpacing(14)
        body_hbox.addLayout(right_col, 27)

        self.matrix_frame = QtWidgets.QFrame()
        self.matrix_frame.setObjectName("MatrixFrame")
        self.matrix_frame.setStyleSheet(
            "QFrame#MatrixFrame { background-color: #070e18; border: 1.5px solid #1a3c4e; border-radius: 8px; }"
        )
        m_grid = QtWidgets.QGridLayout(self.matrix_frame)
        m_grid.setContentsMargins(8, 8, 8, 8)
        m_grid.setSpacing(6)

        self.btn_tasks = GlowGridButton("Tasks", "tasks", checkable=True, sound_engine=self.sfx)
        self.btn_tasks.setChecked(True)
        self.btn_tasks.clicked.connect(lambda: self._switch_right_tab("tasks"))

        self.btn_memory = GlowGridButton("Memory", "memory", checkable=True, sound_engine=self.sfx)
        self.btn_memory.clicked.connect(lambda: self._switch_right_tab("memory"))

        self.btn_briefing = GlowGridButton("Briefing", "briefing", checkable=False, sound_engine=self.sfx)
        self.btn_briefing.clicked.connect(self.on_briefing)

        self.btn_undo = GlowGridButton("Undo", "undo", checkable=False, sound_engine=self.sfx)
        self.btn_undo.clicked.connect(self.on_undo)

        self.btn_quiet = GlowGridButton("Quiet", "quiet", checkable=True, sound_engine=self.sfx)
        self.btn_quiet.clicked.connect(self._handle_quiet_toggle)

        m_grid.addWidget(self.btn_tasks, 0, 0)
        m_grid.addWidget(self.btn_memory, 0, 1)
        m_grid.addWidget(self.btn_briefing, 0, 2)
        m_grid.addWidget(self.btn_undo, 0, 3)
        m_grid.addWidget(self.btn_quiet, 0, 4)

        # Row 2: Interactive Mode Selector (< AUTO >) + Pin + Clear + Mute
        mode_selector = QtWidgets.QFrame()
        mode_selector.setFixedHeight(54)
        mode_selector.setStyleSheet(
            "QFrame { background-color: #0a111b; border: 1.2px solid #264d5e; border-radius: 7px; }"
        )
        ms_l = QtWidgets.QHBoxLayout(mode_selector)
        ms_l.setContentsMargins(4, 4, 4, 4)
        ms_l.setSpacing(2)

        btn_mode_prev = QtWidgets.QPushButton("‹")
        btn_mode_prev.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn_mode_prev.setFixedSize(22, 36)
        btn_mode_prev.setStyleSheet(
            "QPushButton { background: transparent; color: #6fb8c4; font-size: 18px; font-weight: bold; border: none; }"
            "QPushButton:hover { color: #00f5d4; }"
        )
        btn_mode_prev.clicked.connect(lambda: self._cycle_operator_mode(-1))

        self.lbl_mode_val = QtWidgets.QLabel("AUTO")
        self.lbl_mode_val.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lbl_mode_val.setStyleSheet(
            "color: #00f5d4; font-family: 'Bahnschrift'; font-size: 11px; font-weight: bold; border: none;"
        )

        btn_mode_next = QtWidgets.QPushButton("›")
        btn_mode_next.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn_mode_next.setFixedSize(22, 36)
        btn_mode_next.setStyleSheet(
            "QPushButton { background: transparent; color: #6fb8c4; font-size: 18px; font-weight: bold; border: none; }"
            "QPushButton:hover { color: #00f5d4; }"
        )
        btn_mode_next.clicked.connect(lambda: self._cycle_operator_mode(1))

        ms_l.addWidget(btn_mode_prev)
        ms_l.addWidget(self.lbl_mode_val, 1)
        ms_l.addWidget(btn_mode_next)
        m_grid.addWidget(mode_selector, 1, 0, 1, 2)

        self.btn_pin = GlowGridButton("Pin", "pin", checkable=True, sound_engine=self.sfx)
        self.btn_pin.clicked.connect(self._handle_pin_toggle)

        self.btn_clear = GlowGridButton("Clear", "clear", checkable=False, sound_engine=self.sfx)
        self.btn_clear.clicked.connect(self._handle_clear_click)

        self.btn_mute = GlowGridButton("Mute", "mute", checkable=True, sound_engine=self.sfx)
        self.btn_mute.clicked.connect(self._handle_mute_toggle)

        m_grid.addWidget(self.btn_pin, 1, 2)
        m_grid.addWidget(self.btn_clear, 1, 3)
        m_grid.addWidget(self.btn_mute, 1, 4)

        right_col.addWidget(self.matrix_frame)

        # Active Tasks / Memory / Audit Logs Frame
        self.tasks_frame = QtWidgets.QFrame()
        self.tasks_frame.setObjectName("TasksFrame")
        self.tasks_frame.setStyleSheet(
            "QFrame#TasksFrame { background-color: #070e18; border: 1.5px solid #1a3f52; border-radius: 8px; }"
        )
        tf_vbox = QtWidgets.QVBoxLayout(self.tasks_frame)
        tf_vbox.setContentsMargins(16, 14, 16, 14)
        tf_vbox.setSpacing(12)

        tf_hdr = QtWidgets.QHBoxLayout()
        self.right_panel_title = QtWidgets.QLabel("Active Tasks & Reminders")
        self.right_panel_title.setStyleSheet(
            "color: #dceef5; font-family: 'Segoe UI'; font-size: 14px; font-weight: 600;"
        )
        tf_hdr.addWidget(self.right_panel_title)
        tf_hdr.addStretch()

        self.btn_toggle_add = QtWidgets.QPushButton("+ NEW")
        self.btn_toggle_add.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_add.setFixedHeight(22)
        self.btn_toggle_add.setStyleSheet(
            "QPushButton { background-color: #0d2b38; color: #00f5d4; font-family: 'Bahnschrift'; "
            "font-size: 10px; padding: 0 8px; border: 1px solid #1e6b7b; border-radius: 4px; }"
            "QPushButton:hover { background-color: #144254; }"
        )
        self.btn_toggle_add.clicked.connect(self._toggle_quick_add_bar)
        tf_hdr.addWidget(self.btn_toggle_add)

        self.btn_logs_tab = QtWidgets.QPushButton("LOGS")
        self.btn_logs_tab.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_logs_tab.setFixedHeight(22)
        self.btn_logs_tab.setStyleSheet(
            "QPushButton { background-color: #0c1926; color: #79a6b8; font-family: 'Bahnschrift'; "
            "font-size: 10px; padding: 0 8px; border: 1px solid #1e4258; border-radius: 4px; }"
            "QPushButton:hover { color: #dceef5; border-color: #38bdf8; }"
        )
        self.btn_logs_tab.clicked.connect(lambda: self._switch_right_tab("logs"))
        tf_hdr.addWidget(self.btn_logs_tab)

        tf_vbox.addLayout(tf_hdr)

        # Collapsible Inline Quick-Add Bar (for creating Tasks or Memories directly)
        self.quick_add_frame = QtWidgets.QFrame()
        self.quick_add_frame.setStyleSheet(
            "QFrame { background-color: #0b1928; border: 1px solid #1f556e; border-radius: 6px; }"
        )
        qa_hbox = QtWidgets.QHBoxLayout(self.quick_add_frame)
        qa_hbox.setContentsMargins(8, 4, 8, 4)
        qa_hbox.setSpacing(6)
        self.quick_add_input = QtWidgets.QLineEdit()
        self.quick_add_input.setPlaceholderText("Task title (e.g. Call team @ 18:00)...")
        self.quick_add_input.setStyleSheet(
            "QLineEdit { background: transparent; color: #e2f1f8; font-size: 12px; border: none; }"
        )
        self.quick_add_input.returnPressed.connect(self._submit_quick_add)
        qa_hbox.addWidget(self.quick_add_input, 1)

        qa_save_btn = QtWidgets.QPushButton("Save")
        qa_save_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        qa_save_btn.setFixedHeight(22)
        qa_save_btn.setStyleSheet(
            "QPushButton { background-color: #00f5d4; color: #041418; font-weight: bold; "
            "font-size: 11px; padding: 0 8px; border-radius: 4px; border: none; }"
        )
        qa_save_btn.clicked.connect(self._submit_quick_add)
        qa_hbox.addWidget(qa_save_btn)
        self.quick_add_frame.hide()
        tf_vbox.addWidget(self.quick_add_frame)

        div = QtWidgets.QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background-color: #193a4d;")
        tf_vbox.addWidget(div)

        # Scrollable 2-Column Grid for Task / Memory / Log Cards
        self.cards_scroll = QtWidgets.QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.cards_scroll.setStyleSheet("background: transparent; border: none;")
        self.cards_host = QtWidgets.QWidget()
        self.cards_grid = QtWidgets.QGridLayout(self.cards_host)
        self.cards_grid.setContentsMargins(4, 8, 4, 8)
        self.cards_grid.setHorizontalSpacing(12)
        self.cards_grid.setVerticalSpacing(12)
        self.cards_grid.setColumnStretch(0, 1)
        self.cards_grid.setColumnStretch(1, 1)
        self.cards_scroll.setWidget(self.cards_host)
        tf_vbox.addWidget(self.cards_scroll, 1)

        star_row = QtWidgets.QHBoxLayout()
        self.right_footer_lbl = QtWidgets.QLabel("0 ACTIVE ITEMS")
        self.right_footer_lbl.setStyleSheet("color: #4f7b8c; font-family: 'Bahnschrift'; font-size: 10px;")
        star_row.addWidget(self.right_footer_lbl)
        star_row.addStretch()
        star_lbl = QtWidgets.QLabel("✦")
        star_lbl.setStyleSheet("color: rgba(130, 215, 230, 110); font-size: 18px;")
        star_row.addWidget(star_lbl)
        tf_vbox.addLayout(star_row)

        right_col.addWidget(self.tasks_frame, 1)

        # =============================================================
        # 4. COLLAPSIBLE QUICK-COMMAND CHIPS BAR (Above Bottom Dock)
        # =============================================================
        self.quick_chips_bar = QtWidgets.QFrame()
        self.quick_chips_bar.setStyleSheet(
            "QFrame { background-color: #07121e; border: 1px solid #194256; border-radius: 6px; }"
        )
        qc_hbox = QtWidgets.QHBoxLayout(self.quick_chips_bar)
        qc_hbox.setContentsMargins(10, 5, 10, 5)
        qc_hbox.setSpacing(8)
        qc_lbl = QtWidgets.QLabel("QUICK MACROS:")
        qc_lbl.setStyleSheet("color: #5ec8b8; font-family: 'Bahnschrift'; font-size: 11px; border: none;")
        qc_hbox.addWidget(qc_lbl)

        for chip_title, chip_cmd, is_vis in [
            ("⚡ System Health", "Check system status", False),
            ("☀ Daily Briefing", "Generate my daily briefing", False),
            ("👁 Inspect Active Window", "Inspect the screen and summarize the active window", True),
            ("🗂 Scan Workspace Duplicates", "Scan workspace for duplicate or large files", False),
            ("📋 List Pending Tasks", "List tasks", False),
        ]:
            chip = QtWidgets.QPushButton(chip_title)
            chip.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            chip.setStyleSheet(
                "QPushButton { background-color: #0d2132; color: #bfe8f5; font-family: 'Segoe UI'; "
                "font-size: 11px; padding: 4px 10px; border: 1px solid #1e5268; border-radius: 5px; }"
                "QPushButton:hover { background-color: #14354d; color: #00f5d4; border-color: #00f5d4; }"
            )
            chip.clicked.connect(lambda _=False, c=chip_cmd, v=is_vis: self._run_quick_macro(c, v))
            qc_hbox.addWidget(chip)
        qc_hbox.addStretch()
        self.quick_chips_bar.hide()
        root_vbox.addWidget(self.quick_chips_bar)

        # =============================================================
        # 5. BOTTOM FULL-WIDTH COMMAND DOCK
        # =============================================================
        bottom_hbox = QtWidgets.QHBoxLayout()
        bottom_hbox.setSpacing(12)
        root_vbox.addLayout(bottom_hbox)

        self.bottom_cmd_bar = QtWidgets.QFrame()
        self.bottom_cmd_bar.setFixedHeight(44)
        self.bottom_cmd_bar.setObjectName("BottomCmdBar")
        self.bottom_cmd_bar.setStyleSheet(
            "QFrame#BottomCmdBar { background-color: #08111c; border: 1.5px solid #1b4357; border-radius: 7px; }"
        )
        bc_l = QtWidgets.QHBoxLayout(self.bottom_cmd_bar)
        bc_l.setContentsMargins(16, 0, 12, 0)

        status_dot = QtWidgets.QLabel("●")
        status_dot.setStyleSheet("color: #00f5d4; font-size: 12px; border: none;")
        bc_l.addWidget(status_dot)

        self.action_status_lbl = QtWidgets.QLabel("SYSTEM TELEMETRY  |  READY FOR COMMAND")
        self.action_status_lbl.setStyleSheet(
            "color: #6cd4dc; font-family: 'Bahnschrift'; font-size: 13px; font-weight: 600; letter-spacing: 0.8px; border: none;"
        )
        bc_l.addWidget(self.action_status_lbl)
        bc_l.addStretch()

        self.btn_up_chev = QtWidgets.QPushButton("▲ MACROS")
        self.btn_up_chev.setToolTip("Toggle Quick Command Macros")
        self.btn_up_chev.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_up_chev.setStyleSheet(
            "QPushButton { background-color: #0d2233; color: #78c6d8; font-family: 'Bahnschrift'; "
            "font-size: 11px; padding: 4px 10px; border: 1px solid #1f5068; border-radius: 5px; }"
            "QPushButton:hover { color: #00f5d4; border-color: #00f5d4; }"
        )
        self.btn_up_chev.clicked.connect(self._toggle_macros_drawer)
        bc_l.addWidget(self.btn_up_chev)
        bottom_hbox.addWidget(self.bottom_cmd_bar, 1)

        # Glowing Cyan "Vision + Screen Task" Button
        self.btn_vision_task = QtWidgets.QPushButton("👁  Vision + Screen Task")
        self.btn_vision_task.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_vision_task.setFixedSize(200, 44)
        self.btn_vision_task.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00f5d4, stop:1 #00bbdc);"
            "  color: #031519; font-family: 'Segoe UI'; font-size: 13px; font-weight: bold;"
            "  border: 2px solid #88fff0; border-radius: 9px;"
            "}"
            "QPushButton:hover {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38ffe5, stop:1 #1ad1f0);"
            "}"
        )
        self.btn_vision_task.clicked.connect(self._handle_screen_click)
        bottom_hbox.addWidget(self.btn_vision_task)

        # Glowing Indigo "Execute / Send" Button
        self.btn_exec_send = QtWidgets.QPushButton("⚡  Execute / Send")
        self.btn_exec_send.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_exec_send.setFixedSize(175, 44)
        self.btn_exec_send.setStyleSheet(
            "QPushButton {"
            "  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #727cf5, stop:1 #5458e8);"
            "  color: #080b1a; font-family: 'Segoe UI'; font-size: 13px; font-weight: bold;"
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
        self.btn_round_mic.setToolTip("Push-to-Talk Voice Command")
        self.btn_round_mic.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_round_mic.setFixedSize(44, 44)
        self.btn_round_mic.setStyleSheet(
            "QPushButton { background-color: #0a1926; color: #00f0d4; font-size: 17px; "
            "border: 1.8px solid #00c8b8; border-radius: 22px; }"
            "QPushButton:hover { background-color: #102e42; border-color: #5effef; }"
        )
        self.btn_round_mic.clicked.connect(self._handle_mic_click)
        bottom_hbox.addWidget(self.btn_round_mic)

        # Circular Red Stop Button
        self.btn_round_stop = QtWidgets.QPushButton("■")
        self.btn_round_stop.setToolTip("Emergency Stop All Actions & Speech")
        self.btn_round_stop.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.btn_round_stop.setFixedSize(44, 44)
        self.btn_round_stop.setStyleSheet(
            "QPushButton { background-color: #211018; color: #ff4d5e; font-size: 16px; "
            "border: 1.8px solid #ef4444; border-radius: 22px; }"
            "QPushButton:hover { background-color: #3d1826; border-color: #ff808b; }"
        )
        self.btn_round_stop.clicked.connect(self._handle_stop_click)
        bottom_hbox.addWidget(self.btn_round_stop)

        # Initial Welcome Assistant Card
        self.add_assistant_bubble(
            "**ATLAS Operator Online.**\n"
            "Advanced autonomous personal AI desktop assistant.\n"
            "- **Orbital AI & Voice Engine:** Solar HUD reacts to AI speech; Spectrum HUD tracks your microphone.\n"
            "- **Vision & App Control:** Locates UI controls visually and opens any installed PC application.\n"
            "- **Verified Guardrails:** Reversible task execution with instant hardware & desktop alerts."
        )

    # =================================================================
    # CHAT STREAM BUBBLES
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
                "background-color: #23274a; color: #9da8ff; font-size: 15px; "
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
            you_lbl = QtWidgets.QLabel("OPERATOR")
            you_lbl.setStyleSheet("color: #70c8d8; font-family: 'Bahnschrift'; font-weight: bold; font-size: 11px; border: none;")
            time_lbl = QtWidgets.QLabel(stamp)
            time_lbl.setStyleSheet("color: #6c8294; font-size: 11px; border: none;")
            hdr.addWidget(you_lbl)
            hdr.addStretch()
            hdr.addWidget(time_lbl)
            b_vbox.addLayout(hdr)

            msg_lbl = QtWidgets.QLabel(text)
            msg_lbl.setWordWrap(True)
            msg_lbl.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            msg_lbl.setStyleSheet("color: #e6f1f8; font-family: 'Segoe UI'; font-size: 13px; border: none;")
            b_vbox.addWidget(msg_lbl)

            row_l.addWidget(bubble, 1)
            self.chat_vbox.insertWidget(self.chat_vbox.count() - 1, row_w)
            QtCore.QTimer.singleShot(30, self._scroll_chat_bottom)

        self.safe_call(_add)

    def add_assistant_bubble(self, text: str):
        def _add():
            stamp = datetime.now().strftime("%I:%M %p").lstrip("0")
            row_w = QtWidgets.QWidget()
            row_l = QtWidgets.QHBoxLayout(row_w)
            row_l.setContentsMargins(4, 2, 4, 2)
            row_l.setSpacing(10)

            avatar = QtWidgets.QLabel("❖")
            avatar.setFixedSize(34, 34)
            avatar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            avatar.setStyleSheet(
                "background-color: #0b2530; color: #00f0d4; font-size: 17px; "
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
            asst_lbl = QtWidgets.QLabel("ATLAS CORE")
            asst_lbl.setStyleSheet("color: #00f5d4; font-family: 'Bahnschrift'; font-size: 11px; font-weight: bold; border: none;")
            new_lbl = QtWidgets.QLabel(f"VERIFIED  •  {stamp}")
            new_lbl.setStyleSheet("color: #48b8a8; font-size: 11px; border: none;")
            hdr.addWidget(asst_lbl)
            hdr.addStretch()
            hdr.addWidget(new_lbl)
            c_vbox.addLayout(hdr)

            lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
            icons = ["◈", "⚡", "🛡", "✦"]
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
                elif ln.startswith(("-", "*", "•")):
                    item_text = clean_ln.lstrip("-*• ").strip()
                    feat_row = QtWidgets.QHBoxLayout()
                    feat_row.setSpacing(10)
                    ic = QtWidgets.QLabel(icons[bullet_idx % len(icons)])
                    ic.setFixedSize(26, 26)
                    ic.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                    ic.setStyleSheet(
                        "background-color: #0d2b38; color: #00e5ff; font-size: 13px; "
                        "border: 1px solid #186478; border-radius: 6px;"
                    )
                    feat_row.addWidget(ic, 0, QtCore.Qt.AlignmentFlag.AlignTop)

                    flbl = QtWidgets.QLabel(item_text)
                    flbl.setWordWrap(True)
                    flbl.setTextFormat(QtCore.Qt.TextFormat.RichText)
                    flbl.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
                    flbl.setStyleSheet("color: #d6eaf2; font-family: 'Segoe UI'; font-size: 13px; border: none;")
                    feat_row.addWidget(flbl, 1)
                    c_vbox.addLayout(feat_row)
                    bullet_idx += 1
                else:
                    blbl = QtWidgets.QLabel(clean_ln)
                    blbl.setWordWrap(True)
                    blbl.setTextFormat(QtCore.Qt.TextFormat.RichText)
                    blbl.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
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
    # RIGHT PANEL: TASKS, MEMORIES, AND AUDIT LOGS
    # =================================================================
    def _switch_right_tab(self, tab: str):
        self.sfx.play("switch")
        self.active_right_tab = tab
        self.btn_tasks.setChecked(tab == "tasks")
        self.btn_memory.setChecked(tab == "memory")
        self.btn_tasks.update()
        self.btn_memory.update()

        if tab == "tasks":
            self.right_panel_title.setText("Active Tasks & Reminders")
            self.quick_add_input.setPlaceholderText("Task title (e.g. Deploy build @ 18:30)...")
            self.render_tasks(self._cached_tasks)
        elif tab == "memory":
            self.right_panel_title.setText("Memory Inspector")
            self.quick_add_input.setPlaceholderText("key : value (e.g. ide : VS Code)...")
            self.render_memories(self._cached_memories)
        elif tab == "logs":
            self.right_panel_title.setText("Security & Audit Log")
            self._render_audit_logs()

    def _toggle_quick_add_bar(self):
        self.sfx.play("click")
        if self.quick_add_frame.isVisible():
            self.quick_add_frame.hide()
        else:
            if self.active_right_tab == "logs":
                self._switch_right_tab("tasks")
            self.quick_add_frame.show()
            self.quick_add_input.setFocus()

    def _submit_quick_add(self):
        raw = self.quick_add_input.text().strip()
        if not raw:
            return
        self.sfx.play("send")
        self.quick_add_input.clear()
        self.quick_add_frame.hide()

        if self.active_right_tab == "tasks":
            due_dt = datetime.now() + timedelta(hours=1)
            title = raw
            if "@" in raw:
                title, time_part = (part.strip() for part in raw.split("@", 1))
                try:
                    parsed_due = parse_due_datetime(time_part)
                    due_str = parsed_due.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError as exc:
                    self.add_assistant_bubble(
                        "**I couldn't parse that reminder time.** Use `Task @ 18:30`, `Task @ 2026-10-18 18:30`, or `Task @ in 10 seconds`."
                    )
                    self.quick_add_input.setText(raw)
                    self.quick_add_frame.show()
                    self.quick_add_input.setFocus()
                    return
            else:
                due_str = due_dt.strftime("%Y-%m-%d %H:%M:%S")

            if not title:
                self.add_assistant_bubble("**Please enter a task title before the `@` time.**")
                return
            if self.on_create_task:
                self.on_create_task(title, due_str, "medium")
        elif self.active_right_tab == "memory":
            if ":" in raw:
                k, v = raw.split(":", 1)
            elif "=" in raw:
                k, v = raw.split("=", 1)
            else:
                k, v = "note", raw
            if self.on_save_memory:
                self.on_save_memory("workspace", k.strip(), v.strip())

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
        on_primary_action: Optional[Callable] = None,
        primary_symbol: str = "✓",
        primary_tooltip: str = "Complete",
        on_secondary_action: Optional[Callable] = None,
        secondary_symbol: str = "+15m",
        secondary_tooltip: str = "Snooze 15m",
    ) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setMinimumHeight(134)
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
        t_lbl.setStyleSheet(
            "color: #e4f2f8; font-family: 'Segoe UI'; font-size: 12px; font-weight: 600; border: none;"
        )
        vbox.addWidget(t_lbl, 1)

        foot = QtWidgets.QFrame()
        foot.setFixedHeight(26)
        foot.setStyleSheet("background-color: #091420; border: 1px solid #183848; border-radius: 4px;")
        f_hbox = QtWidgets.QHBoxLayout(foot)
        f_hbox.setContentsMargins(6, 0, 6, 0)
        f_hbox.setSpacing(4)

        fl_lbl = QtWidgets.QLabel(footer_left)
        fl_lbl.setStyleSheet("color: #5ec8b8; font-family: 'Bahnschrift'; font-size: 10px; border: none;")
        f_hbox.addWidget(fl_lbl)
        f_hbox.addStretch()

        if on_secondary_action:
            sec_btn = QtWidgets.QPushButton(secondary_symbol)
            sec_btn.setToolTip(secondary_tooltip)
            sec_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            sec_btn.setFixedHeight(18)
            sec_btn.setStyleSheet(
                "QPushButton { background-color: #122838; color: #fbbf24; font-family: 'Bahnschrift'; "
                "font-size: 9px; padding: 0 5px; border-radius: 3px; border: 1px solid #78350f; }"
                "QPushButton:hover { background-color: #78350f; color: #ffffff; }"
            )
            sec_btn.clicked.connect(lambda: (self.sfx.play("click"), on_secondary_action()))
            f_hbox.addWidget(sec_btn)

        if on_primary_action:
            act_btn = QtWidgets.QPushButton(primary_symbol)
            act_btn.setToolTip(primary_tooltip)
            act_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            act_btn.setFixedSize(22, 18)
            act_btn.setStyleSheet(
                "QPushButton { background-color: #0e363e; color: #00f5d4; font-size: 11px; "
                "font-weight: bold; border-radius: 3px; border: 1px solid #1e707e; }"
                "QPushButton:hover { background-color: #00f5d4; color: #041218; }"
            )
            act_btn.clicked.connect(lambda: (self.sfx.play("send"), on_primary_action()))
            f_hbox.addWidget(act_btn)

        vbox.addWidget(foot)
        return card

    @staticmethod
    def _format_task_due(due: datetime) -> tuple[str, str]:
        seconds_left = (due - datetime.now()).total_seconds()
        if seconds_left <= 0:
            return "Due now", "#fb7185"
        if seconds_left < 60:
            return f"Due in {max(1, int(seconds_left + 0.999))} sec", "#fbbf24"
        if seconds_left < 3600:
            minutes_left = max(1, int((seconds_left + 59) // 60))
            return f"Due in {minutes_left} min", "#7dd3fc"
        now = datetime.now()
        if due.date() == now.date():
            return f"Today · {due.strftime('%H:%M')}", "#7dd3fc"
        if due.date() == now.date() + timedelta(days=1):
            return f"Tomorrow · {due.strftime('%H:%M')}", "#7dd3fc"
        return due.strftime("%b %d · %H:%M"), "#7dd3fc"

    def _refresh_task_due_labels(self):
        # Update only the small countdown labels; cards are not rebuilt every second.
        for index in range(self.cards_grid.count()):
            widget = self.cards_grid.itemAt(index).widget()
            if widget is None or widget.objectName() != "TaskCard":
                continue
            for label in widget.findChildren(QtWidgets.QLabel):
                if label.objectName() != "TaskDueLabel":
                    continue
                raw_due = label.property("due_at")
                if not raw_due:
                    continue
                try:
                    due = datetime.fromisoformat(str(raw_due))
                except ValueError:
                    continue
                text, color = self._format_task_due(due)
                if label.text() != text:
                    label.setText(text)
                if label.property("due_color") != color:
                    label.setProperty("due_color", color)
                    label.setStyleSheet(
                        f"QLabel {{ color: {color}; font-family: 'Segoe UI'; font-size: 11px; "
                        "background: transparent; border: none; }"
                    )

    def _create_task_card(self, task: Dict[str, Any]) -> QtWidgets.QFrame:
        task_id = int(task.get("id", 0))
        priority = str(task.get("priority", "medium")).lower()
        priority_colors = {
            "high": ("#fb7185", "#321821", "#773344"),
            "medium": ("#fbbf24", "#302713", "#705522"),
            "low": ("#6ee7b7", "#102b25", "#226c55"),
        }
        color, badge_bg, badge_border = priority_colors.get(priority, priority_colors["medium"])

        card = QtWidgets.QFrame()
        card.setObjectName("TaskCard")
        card.setMinimumHeight(100)
        card.setStyleSheet(
            "QFrame#TaskCard { background-color: #0a1420; border: 1px solid #20394b; border-radius: 12px; }"
            "QFrame#TaskCard:hover { background-color: #0c1a28; border-color: #32647a; }"
        )
        row = QtWidgets.QHBoxLayout(card)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(14)

        accent = QtWidgets.QFrame()
        accent.setFixedWidth(3)
        accent.setStyleSheet(f"background-color: {color}; border: none; border-radius: 1px;")
        row.addWidget(accent)

        icon = QtWidgets.QLabel("◷")
        icon.setFixedSize(38, 38)
        icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            "QLabel { background-color: #102333; color: #80d9e8; font-size: 21px; "
            "border: 1px solid #25485d; border-radius: 10px; }"
        )
        row.addWidget(icon)

        details = QtWidgets.QVBoxLayout()
        details.setContentsMargins(0, 0, 0, 0)
        details.setSpacing(7)
        title = QtWidgets.QLabel(str(task.get("title", "Untitled reminder")))
        title.setWordWrap(True)
        title.setStyleSheet(
            "QLabel { color: #e8f3fa; font-family: 'Segoe UI'; font-size: 13px; "
            "font-weight: 600; background: transparent; border: none; }"
        )
        details.addWidget(title)

        meta_row = QtWidgets.QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(8)
        due_datetime = None
        try:
            due_datetime = parse_due_datetime(str(task.get("due_time", "")))
            due_text, due_color = self._format_task_due(due_datetime)
        except ValueError:
            due_text = str(task.get("due_time", "Time not set"))
            due_color = "#7dd3fc"

        due_label = QtWidgets.QLabel(due_text)
        due_label.setObjectName("TaskDueLabel")
        if due_datetime is not None:
            due_label.setProperty("due_at", due_datetime.isoformat(sep=" "))
        due_label.setProperty("due_color", due_color)
        due_label.setStyleSheet(
            f"QLabel {{ color: {due_color}; font-family: 'Segoe UI'; font-size: 11px; "
            "background: transparent; border: none; }"
        )
        meta_row.addWidget(due_label)

        priority_label = QtWidgets.QLabel(priority.upper())
        priority_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        priority_label.setStyleSheet(
            f"QLabel {{ background-color: {badge_bg}; color: {color}; border: 1px solid {badge_border}; "
            "border-radius: 6px; padding: 2px 7px; font-family: 'Bahnschrift'; "
            "font-size: 9px; font-weight: 700; }"
        )
        meta_row.addWidget(priority_label, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
        meta_row.addStretch(1)
        details.addLayout(meta_row)
        row.addLayout(details, 1)

        actions = QtWidgets.QVBoxLayout()
        actions.setSpacing(7)
        snooze_btn = QtWidgets.QPushButton("Snooze 15m")
        snooze_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        snooze_btn.setFixedSize(94, 29)
        snooze_btn.setStyleSheet(
            "QPushButton { background-color: #171f2b; color: #c0d2df; border: 1px solid #344556; "
            "border-radius: 7px; font-size: 10px; padding: 3px 6px; }"
            "QPushButton:hover { background-color: #2a2618; color: #fbbf24; border-color: #8a6b24; }"
        )
        snooze_btn.setToolTip("Remind me again in 15 minutes")
        snooze_btn.clicked.connect(lambda _=False, tid=task_id: self.on_snooze_task(tid))

        done_btn = QtWidgets.QPushButton("✓  Done")
        done_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        done_btn.setFixedSize(94, 29)
        done_btn.setStyleSheet(
            "QPushButton { background-color: #0b2b2a; color: #7ce8d4; border: 1px solid #24665e; "
            "border-radius: 7px; font-size: 10px; font-weight: 600; padding: 3px 8px; }"
            "QPushButton:hover { background-color: #00bfae; color: #041417; border-color: #62ffea; }"
        )
        done_btn.setToolTip("Mark this reminder complete")
        done_btn.clicked.connect(lambda _=False, tid=task_id: self.on_complete_task(tid))
        actions.addWidget(snooze_btn)
        actions.addWidget(done_btn)
        row.addLayout(actions)
        return card

    def render_tasks(self, tasks: List[Dict[str, Any]]):
        def _r():
            self._cached_tasks = list(tasks)
            if self.active_right_tab != "tasks":
                return
            self._clear_cards_grid()
            count = len(tasks)
            self.right_footer_lbl.setText(f"{count} ACTIVE REMINDER{'S' if count != 1 else ''}")

            if not tasks:
                empty = QtWidgets.QFrame()
                empty.setObjectName("EmptyTasksCard")
                empty.setMinimumHeight(180)
                empty.setStyleSheet(
                    "QFrame#EmptyTasksCard { background-color: #091521; border: 1px dashed #29485b; border-radius: 14px; }"
                )
                empty_layout = QtWidgets.QVBoxLayout(empty)
                empty_layout.setContentsMargins(18, 22, 18, 22)
                empty_layout.setSpacing(10)
                empty_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

                icon = QtWidgets.QLabel("✦")
                icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                icon.setStyleSheet("color: #5bc9c2; font-size: 24px; background: transparent; border: none;")
                empty_layout.addWidget(icon)

                title = QtWidgets.QLabel("You're all caught up")
                title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                title.setStyleSheet("color: #e3f1f8; font-size: 14px; font-weight: 600; background: transparent; border: none;")
                empty_layout.addWidget(title)

                detail = QtWidgets.QLabel("Your next reminder will appear here.")
                detail.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                detail.setStyleSheet("color: #7897a9; font-size: 11px; background: transparent; border: none;")
                empty_layout.addWidget(detail)

                create_btn = QtWidgets.QPushButton("＋  New reminder")
                create_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
                create_btn.setFixedSize(146, 34)
                create_btn.setStyleSheet(
                    "QPushButton { background-color: #0d2b38; color: #63e8d7; border: 1px solid #267568; "
                    "border-radius: 8px; font-size: 11px; font-weight: 600; padding: 4px 10px; }"
                    "QPushButton:hover { background-color: #123e4c; border-color: #5eead4; }"
                )
                create_btn.clicked.connect(self._toggle_quick_add_bar)
                empty_layout.addWidget(create_btn, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
                self.cards_grid.addWidget(empty, 0, 0, 1, 2)
                return

            for idx, task in enumerate(tasks):
                card = self._create_task_card(task)
                # One calm, full-width row per task is easier to scan than tiny tiles.
                self.cards_grid.addWidget(card, idx, 0, 1, 2)

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

            self.right_footer_lbl.setText(f"{len(entries)} STORED MEMORIES")

            if not entries:
                card = self._create_cyber_card(
                    "🧠",
                    "No Saved Memories\nClick '+ NEW' or say 'Remember that...'",
                    "MEM 0/0",
                    is_teal_glow=True,
                    on_primary_action=self._toggle_quick_add_bar,
                    primary_symbol="+",
                    primary_tooltip="Add Memory Item",
                )
                self.cards_grid.addWidget(card, 0, 0, 1, 2)
                return

            for idx, (cat, k, val) in enumerate(entries):
                card = self._create_cyber_card(
                    "🧠",
                    f"{k.title()}:\n{val}",
                    cat.upper(),
                    is_teal_glow=(idx % 2 == 0),
                    on_primary_action=lambda c=cat, key=k: self.on_delete_memory(c, key),
                    primary_symbol="×",
                    primary_tooltip="Delete Memory",
                )
                self.cards_grid.addWidget(card, idx // 2, idx % 2)

        self.safe_call(_rm)

    def _render_audit_logs(self):
        self._clear_cards_grid()
        log_text = self.on_read_logs() if self.on_read_logs else "Audit log reader not bound."
        viewer = QtWidgets.QPlainTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(log_text)
        viewer.setStyleSheet(
            "QPlainTextEdit { background-color: #08121e; color: #7ce8ff; "
            "font-family: 'Consolas', monospace; font-size: 11px; "
            "border: 1px solid #1b4558; border-radius: 6px; padding: 6px; }"
        )
        self.cards_grid.addWidget(viewer, 0, 0, 1, 2)
        self.right_footer_lbl.setText("AUDIT STREAM ACTIVE")

    # =================================================================
    # THREAD-SAFE STATE & AUDIO ROUTING METHODS
    # =================================================================
    def set_status(self, text: str, color: str = "#10b981", disable_buttons: bool = False):
        def _u():
            self.spectrum_hud.set_status_display(text, color)
            self.btn_vision_task.setEnabled(not disable_buttons)
            self.btn_exec_send.setEnabled(not disable_buttons)
            current = (text or "Ready").upper()
            prefix = "ACTIVE  |  " if disable_buttons else "STATUS  |  "
            self.action_status_lbl.setText(f"{prefix}{current}")

        self.safe_call(_u)

    def set_action_banner(self, text: str):
        def _b():
            self.action_status_lbl.setText(text.upper() if text else f"MODE: {self.operator_mode}  |  READY")

        self.safe_call(_b)

    def update_visualizer(self, levels: List[float]):
        if not self.is_muted:
            self.safe_call(lambda: self.spectrum_hud.push_external_mic_levels(levels))

    def set_ai_voice_level(self, level: float):
        self.safe_call(lambda: self.solar_hud.set_ai_voice_level(level))

    def update_input_box(self, text: str):
        def _s():
            self.input_box.setText(text)
            self.input_box.setFocus()

        self.safe_call(_s)

    def show_screen_preview(self, image_path: str):
        def _sh():
            self.preview_title_lbl.setText(f"Target Locked ({datetime.now().strftime('%H:%M:%S')})")
            self.clean_preview.set_image(image_path)

        self.safe_call(_sh)

    def show_approval_prompt(self, payload: Dict[str, str]):
        def _p():
            self.sfx.play("alert")
            txt = (
                f"⚠  {payload['level']}  |  Action: {payload['action']}  |  "
                f"Target: {payload['target']}  |  Consequences: {payload['consequences']}"
            )
            self.approval_lbl.setText(txt)
            self.approval_bar.show()

        self.safe_call(_p)

    def _resolve_approval(self, choice: str):
        self.sfx.play("send" if choice == "approve_once" else "stop")
        self.approval_bar.hide()
        self.on_approval_decision(choice)

    # =================================================================
    # INTERACTIVE CONTROLS & BUTTON HANDLERS
    # =================================================================
    def _cycle_operator_mode(self, delta: int):
        self.sfx.play("switch")
        self.mode_idx = (self.mode_idx + delta) % len(self.OPERATING_MODES)
        self.operator_mode = self.OPERATING_MODES[self.mode_idx]
        self.lbl_mode_val.setText(self.operator_mode)
        self.header_banner.set_mode_badge(self.operator_mode)
        self.action_status_lbl.setText(f"MODE SWITCHED TO {self.operator_mode}")

        if self.operator_mode == "STEALTH":
            if not self.is_quiet:
                self.btn_quiet.setChecked(True)
                self._handle_quiet_toggle()

    def _toggle_macros_drawer(self):
        self.sfx.play("click")
        if self.quick_chips_bar.isVisible():
            self.quick_chips_bar.hide()
            self.btn_up_chev.setText("▲ MACROS")
        else:
            self.quick_chips_bar.show()
            self.btn_up_chev.setText("▼ MACROS")

    def _run_quick_macro(self, cmd: str, with_vision: bool = False):
        self.sfx.play("send")
        self.quick_chips_bar.hide()
        self.btn_up_chev.setText("▲ MACROS")
        if with_vision:
            self.add_user_bubble(f"[Vision Task]: {cmd}")
            self.on_ask_screen(cmd)
        else:
            self.add_user_bubble(cmd)
            self.on_ask_text(cmd)

    def _handle_refresh_preview(self):
        self.sfx.play("click")
        self.preview_title_lbl.setText("Capturing Desktop...")
        if self.on_refresh_screen:
            self.on_refresh_screen()

    def _open_preview_lightbox(self):
        if not self.clean_preview.pixmap or self.clean_preview.pixmap.isNull():
            self._handle_refresh_preview()
            return
        self.sfx.play("switch")
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"ATLAS Vision Inspector - {self.clean_preview.last_capture_time}")
        dlg.resize(1024, 600)
        dlg.setStyleSheet("QDialog { background-color: #050a12; }")
        vbox = QtWidgets.QVBoxLayout(dlg)
        lbl = QtWidgets.QLabel()
        lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        lbl.setPixmap(
            self.clean_preview.pixmap.scaled(
                980,
                560,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        )
        vbox.addWidget(lbl)
        dlg.exec()

    def _handle_send_click(self):
        q = self.input_box.text().strip()
        if not q:
            return
        self.sfx.play("send")
        self.input_box.clear()
        if self.operator_mode == "VISION":
            self.add_user_bubble(f"[Vision Mode]: {q}")
            self.on_ask_screen(q)
        else:
            self.add_user_bubble(q)
            self.on_ask_text(q)

    def _handle_screen_click(self):
        self.sfx.play("send")
        q = self.input_box.text().strip() or "Inspect the screen and help me with what is currently open."
        self.input_box.clear()
        self.add_user_bubble(f"[Vision Task]: {q}")
        self.on_ask_screen(q)

    def _handle_mic_click(self):
        self.sfx.play("click")
        self.on_manual_voice()

    def _handle_stop_click(self):
        self.sfx.play("stop")
        self.on_stop_all()

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
        # Also pause/resume the AudioSpectrumHUD mic stream so it stops reacting while muted
        if self.spectrum_hud.audio_stream:
            try:
                if self.is_muted:
                    self.spectrum_hud.audio_stream.stop()
                else:
                    self.spectrum_hud.audio_stream.start()
            except Exception:
                pass
        self.on_toggle_mute(self.is_muted)

    def _handle_quiet_toggle(self):
        self.is_quiet = self.btn_quiet.isChecked()
        self.sfx.enabled = not self.is_quiet
        self.on_toggle_quiet(self.is_quiet)