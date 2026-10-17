import math
import numpy as np
import sounddevice as sd
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtOpenGLWidgets import QOpenGLWidget


class AudioSpectrumHUD(QOpenGLWidget):
    """Top-center dual-lobe frequency spectrum that reacts to the USER's microphone."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(165)

        self.raw_audio_level = 0.0
        self.smooth_audio_level = 0.0
        self.status_text = "Ready"
        self.status_color = QtGui.QColor(95, 220, 175, 240)

        self.mic_sensitivity = 18.0
        self.noise_gate = 0.004
        self.idle_amplitude = 0.68

        self.bars_per_side = 68
        self.raw_fft_bins = np.zeros(self.bars_per_side, dtype=np.float32)
        self.smooth_fft_bins = np.zeros(self.bars_per_side, dtype=np.float32)

        self.base_time = 0.0
        self.phase_time = 0.0

        rng = np.random.default_rng(42)
        self.bar_jitter_left = rng.uniform(0.82, 1.18, self.bars_per_side)
        self.bar_jitter_right = rng.uniform(0.82, 1.18, self.bars_per_side)

        self.audio_stream = None
        self.init_audio_stream()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)

    def init_audio_stream(self):
        try:
            self.audio_stream = sd.InputStream(
                channels=1, samplerate=44100, blocksize=1024, callback=self._audio_callback
            )
            self.audio_stream.start()
        except Exception as e:
            print(f"[AudioSpectrumHUD] Mic stream fallback active: {e}")
            self.audio_stream = None

    def _audio_callback(self, indata, frames, time_info, status):
        mono = indata[:, 0]
        rms = float(np.sqrt(np.mean(mono ** 2)))

        if rms < self.noise_gate:
            self.raw_audio_level = 0.0
            self.raw_fft_bins.fill(0.0)
            return

        self.raw_audio_level = rms
        windowed = mono * np.hanning(len(mono))
        fft_mag = np.abs(np.fft.rfft(windowed))
        useful_bins = fft_mag[1:min(len(fft_mag), 150)]
        if len(useful_bins) > 0:
            resampled = np.interp(
                np.linspace(0, len(useful_bins) - 1, self.bars_per_side),
                np.arange(len(useful_bins)),
                useful_bins,
            )
            self.raw_fft_bins = np.clip(resampled * (self.mic_sensitivity * 0.45), 0.0, 1.5)

    def push_external_mic_levels(self, levels: list[float]):
        """Fallback feed from PyAudio STTEngine so the spectrum stays reactive during voice capture."""
        if not levels:
            return
        avg = sum(levels) / len(levels)
        if avg > self.raw_audio_level:
            self.raw_audio_level = avg * 0.08
            resampled = np.interp(
                np.linspace(0, len(levels) - 1, self.bars_per_side),
                np.arange(len(levels)),
                levels,
            )
            self.raw_fft_bins = np.clip(resampled * 1.2, 0.0, 1.5)

    def set_status_display(self, text: str, hex_color: str = "#10b981"):
        self.status_text = text
        self.status_color = QtGui.QColor(hex_color)

    def closeEvent(self, event):
        if self.audio_stream:
            try:
                self.audio_stream.stop()
                self.audio_stream.close()
            except Exception:
                pass
        super().closeEvent(event)

    @staticmethod
    def _lobe_envelope(u, is_left=True):
        edge_taper = math.sin(u * math.pi) ** 1.35
        if is_left:
            p1 = 1.00 * math.exp(-((u - 0.77) / 0.078) ** 2)
            p2 = 0.84 * math.exp(-((u - 0.56) / 0.074) ** 2)
            p3 = 0.66 * math.exp(-((u - 0.36) / 0.082) ** 2)
            tail = 0.16 * math.exp(-((u - 0.18) / 0.11) ** 2)
        else:
            p1 = 0.96 * math.exp(-((u - 0.78) / 0.078) ** 2)
            p2 = 0.76 * math.exp(-((u - 0.60) / 0.072) ** 2)
            p3 = 0.62 * math.exp(-((u - 0.42) / 0.076) ** 2)
            tail = 0.34 * math.exp(-((u - 0.25) / 0.085) ** 2)
        return (p1 + p2 + p3 + tail) * edge_taper

    def compute_bar_height(self, idx, is_left, max_half_height):
        u = idx / (self.bars_per_side - 1)
        env = self._lobe_envelope(u, is_left=is_left)

        dir_sign = 1.0 if is_left else -1.0
        carrier_1 = 0.72 + 0.28 * math.sin(idx * 1.65 - dir_sign * self.phase_time * 2.4)
        carrier_2 = 0.85 + 0.15 * math.cos(idx * 0.75 + dir_sign * self.phase_time * 1.5)
        breathing = 0.92 + 0.08 * math.sin(self.base_time * 2.2 + u * 4.0 + (0.0 if is_left else 1.2))
        jitter = self.bar_jitter_left[idx] if is_left else self.bar_jitter_right[idx]

        audio_boost = self.smooth_audio_level
        fft_val = float(self.smooth_fft_bins[idx])

        active_gain = self.idle_amplitude + (1.0 - self.idle_amplitude) * min(1.0, audio_boost * 1.35)
        fft_surge = fft_val * env * 0.75 * (0.4 + 0.6 * carrier_1)

        normalized = env * carrier_1 * carrier_2 * breathing * jitter * active_gain + fft_surge
        normalized = min(1.12, max(0.0, normalized))
        return normalized * max_half_height

    def draw_glowing_bar(self, painter, x, cy, half_h, rgb):
        r, g, b = rgb
        if half_h < 1.8:
            dot_alpha = int(170 + 60 * (half_h / 1.8))
            glow_pen = QtGui.QPen(QtGui.QColor(r, g, b, int(dot_alpha * 0.35)))
            glow_pen.setWidthF(7.5)
            glow_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            painter.setPen(glow_pen)
            painter.drawPoint(QtCore.QPointF(x, cy))

            core_pen = QtGui.QPen(QtGui.QColor(min(255, r + 95), min(255, g + 95), min(255, b + 95), dot_alpha))
            core_pen.setWidthF(2.6)
            core_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            painter.setPen(core_pen)
            painter.drawPoint(QtCore.QPointF(x, cy))
            return

        p1 = QtCore.QPointF(x, cy - half_h)
        p2 = QtCore.QPointF(x, cy + half_h)

        pen_glow = QtGui.QPen(QtGui.QColor(r, g, b, 42))
        pen_glow.setWidthF(11.0)
        pen_glow.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_glow)
        painter.drawLine(p1, p2)

        pen_mid = QtGui.QPen(QtGui.QColor(r, g, b, 110))
        pen_mid.setWidthF(5.5)
        pen_mid.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_mid)
        painter.drawLine(p1, p2)

        pen_core = QtGui.QPen(QtGui.QColor(min(255, r + 105), min(255, g + 105), min(255, b + 105), 245))
        pen_core.setWidthF(2.2)
        pen_core.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_core)
        painter.drawLine(p1, p2)

    def draw_hud_frame(self, painter):
        painter.save()
        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceOver)

        bracket_color = QtGui.QColor(65, 165, 155, 205)
        pen = QtGui.QPen(bracket_color)
        pen.setWidthF(2.2)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.SquareCap)
        pen.setJoinStyle(QtCore.Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)

        left_x, right_x = -428.0, 428.0
        top_y, bot_y = -68.0, 76.0
        arm = 14.0

        painter.drawPolyline([QtCore.QPointF(left_x, top_y + arm), QtCore.QPointF(left_x, top_y), QtCore.QPointF(left_x + arm, top_y)])
        painter.drawPolyline([QtCore.QPointF(right_x - arm, top_y), QtCore.QPointF(right_x, top_y), QtCore.QPointF(right_x, top_y + arm)])
        painter.drawPolyline([QtCore.QPointF(left_x, bot_y - arm), QtCore.QPointF(left_x, bot_y), QtCore.QPointF(left_x + arm, bot_y)])
        painter.drawPolyline([QtCore.QPointF(right_x - arm, bot_y), QtCore.QPointF(right_x, bot_y), QtCore.QPointF(right_x, bot_y - arm)])

        title_font = QtGui.QFont("Bahnschrift", 13, QtGui.QFont.Weight.DemiBold)
        title_font.setLetterSpacing(QtGui.QFont.SpacingType.AbsoluteSpacing, 0.9)
        painter.setFont(title_font)
        painter.setPen(QtGui.QColor(115, 195, 200, 230))
        painter.drawText(QtCore.QPointF(left_x, top_y - 12.0), "AUDIO SPECTRUM")

        status_font = QtGui.QFont("Bahnschrift", 14, QtGui.QFont.Weight.DemiBold)
        painter.setFont(status_font)
        status_rect = QtCore.QRectF(-180.0, bot_y - 20.0, 360.0, 30.0)

        glow_c = QtGui.QColor(self.status_color)
        glow_c.setAlpha(int(75 + self.smooth_audio_level * 100))
        painter.setPen(glow_c)
        painter.drawText(status_rect.translated(0, 0.6), QtCore.Qt.AlignmentFlag.AlignCenter, self.status_text)

        main_c = QtGui.QColor(self.status_color)
        main_c.setAlpha(240)
        painter.setPen(main_c)
        painter.drawText(status_rect, QtCore.Qt.AlignmentFlag.AlignCenter, self.status_text)

        painter.restore()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(5, 10, 18))

        w, h = self.width(), self.height()
        painter.translate(w / 2.0, h / 2.0 + 6.0)
        scale = min(w / 900.0, h / 205.0)
        painter.scale(scale, scale)

        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Plus)

        center_gap = 7.5
        outer_span = 408.0
        step = (outer_span - center_gap) / (self.bars_per_side - 1)
        max_half_height = 72.0
        cy = 2.0

        for i in range(self.bars_per_side):
            u = i / (self.bars_per_side - 1)
            x = -(center_gap + i * step)
            half_h = self.compute_bar_height(i, is_left=True, max_half_height=max_half_height)
            r = 0
            g = int(205 + 30 * (1.0 - u))
            b = int(255 - 25 * (1.0 - u))
            self.draw_glowing_bar(painter, x, cy, half_h, (r, g, b))

        for i in range(self.bars_per_side):
            u = i / (self.bars_per_side - 1)
            x = +(center_gap + i * step)
            half_h = self.compute_bar_height(i, is_left=False, max_half_height=max_half_height)
            r = 0
            g = int(235 + 15 * u)
            b = int(185 - 45 * u)
            self.draw_glowing_bar(painter, x, cy, half_h, (r, g, b))

        self.draw_hud_frame(painter)
        painter.end()

    def update_animation(self):
        self.base_time += 0.016
        target = min(1.0, self.raw_audio_level * self.mic_sensitivity)
        if target > self.smooth_audio_level:
            self.smooth_audio_level += (target - self.smooth_audio_level) * 0.45
        else:
            self.smooth_audio_level += (target - self.smooth_audio_level) * 0.09

        fft_diff = self.raw_fft_bins - self.smooth_fft_bins
        attack_mask = fft_diff > 0
        self.smooth_fft_bins[attack_mask] += fft_diff[attack_mask] * 0.50
        self.smooth_fft_bins[~attack_mask] += fft_diff[~attack_mask] * 0.12

        # Decay raw fallback gradually if driven externally
        self.raw_audio_level *= 0.92
        self.raw_fft_bins *= 0.90

        self.phase_time += 0.016 * (1.0 + self.smooth_audio_level * 2.2)
        self.update()