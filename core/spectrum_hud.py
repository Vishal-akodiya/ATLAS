import sys
import math
import numpy as np
import sounddevice as sd

from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtOpenGLWidgets import QOpenGLWidget


class AudioSpectrumHUD(QOpenGLWidget):
    """Top-center 3D liquid-silk plasma spectrum with exact mic dynamics and fine tapered ends."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(175)

        # -----------------------------------------------------------------
        # AUDIO & TIME STATE (Matched to audio_spectrum_hud.py)
        # -----------------------------------------------------------------
        self.raw_audio_level = 0.0
        self.smooth_audio_level = 0.0
        self.status_text = "Ready"
        self.status_color = QtGui.QColor(95, 200, 165, 235)

        # TWEAK THESE IF NEEDED:
        self.mic_sensitivity = 18.0   # Overall microphone gain multiplier
        self.noise_gate = 0.004       # Ignores tiny background noises
        self.idle_amplitude = 0.72    # Baseline wave height when silent

        # Number of discrete frequency bins per side
        self.bars_per_side = 68
        self.raw_fft_bins = np.zeros(self.bars_per_side, dtype=np.float32)
        self.smooth_fft_bins = np.zeros(self.bars_per_side, dtype=np.float32)

        # Separate monotonic clocks so waves never reverse when volume drops
        self.base_time = 0.0
        self.phase_time = 0.0

        self.audio_stream = None
        self.init_audio_stream()

        # 60 FPS Render Loop
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

        # Compute windowed FFT magnitude for real-time frequency-band reactivity
        windowed = mono * np.hanning(len(mono))
        fft_mag = np.abs(np.fft.rfft(windowed))
        useful_bins = fft_mag[1:min(len(fft_mag), 150)]
        if len(useful_bins) > 0:
            resampled = np.interp(
                np.linspace(0, len(useful_bins) - 1, self.bars_per_side),
                np.arange(len(useful_bins)),
                useful_bins
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
        if hasattr(self, "audio_stream") and self.audio_stream:
            try:
                self.audio_stream.stop()
                self.audio_stream.close()
            except Exception:
                pass
        super().closeEvent(event)

    @staticmethod
    def _build_smooth_path(points: list[QtCore.QPointF]) -> QtGui.QPainterPath:
        """Catmull-Rom spline with tension tuned for curling liquid hooks."""
        path = QtGui.QPainterPath()
        n = len(points)
        if n == 0:
            return path
        path.moveTo(points[0])
        if n < 3:
            for p in points[1:]:
                path.lineTo(p)
            return path

        for i in range(n - 1):
            p0 = points[max(0, i - 1)]
            p1 = points[i]
            p2 = points[i + 1]
            p3 = points[min(n - 1, i + 2)]

            cp1 = QtCore.QPointF(p1.x() + (p2.x() - p0.x()) / 5.8, p1.y() + (p2.y() - p0.y()) / 5.8)
            cp2 = QtCore.QPointF(p2.x() - (p3.x() - p1.x()) / 5.8, p2.y() - (p3.y() - p1.y()) / 5.8)
            path.cubicTo(cp1, cp2, p2)
        return path

    @staticmethod
    def _build_closed_ribbon(pts_a: list[QtCore.QPointF], pts_b: list[QtCore.QPointF]) -> QtGui.QPainterPath:
        """Creates a closed volumetric silk veil between two 2D parametric curves."""
        path = AudioSpectrumHUD._build_smooth_path(pts_a)
        rev_b = list(reversed(pts_b))
        n = len(rev_b)
        if n > 0:
            path.lineTo(rev_b[0])
            for i in range(n - 1):
                p0 = rev_b[max(0, i - 1)]
                p1 = rev_b[i]
                p2 = rev_b[i + 1]
                p3 = rev_b[min(n - 1, i + 2)]

                cp1 = QtCore.QPointF(p1.x() + (p2.x() - p0.x()) / 5.8, p1.y() + (p2.y() - p0.y()) / 5.8)
                cp2 = QtCore.QPointF(p2.x() - (p3.x() - p1.x()) / 5.8, p2.y() - (p3.y() - p1.y()) / 5.8)
                path.cubicTo(cp1, cp2, p2)
        path.closeSubpath()
        return path

    def _sample_fft_field(self, u: np.ndarray) -> np.ndarray:
        """Vectorized FFT sampling across the horizontal normalized coordinate array u."""
        center_dist = np.abs(u - 0.5) * 2.0
        idx_f = (1.0 - center_dist) * (self.bars_per_side - 1)
        return np.interp(idx_f, np.arange(self.bars_per_side), self.smooth_fft_bins)

    def _compute_fluid_strands(self, num_pts: int = 140):
        """
        Generates 7 parametric 2D (X + Y) fluid strands with needle-fine tapered ends
        and exact microphone reactivity matching audio_spectrum_hud.py.
        """
        u = np.linspace(0.0, 1.0, num_pts)
        span_x = 404.0
        base_x = -span_x + u * (2.0 * span_x)
        cy = 0.0

        p = self.phase_time
        t = self.base_time
        audio_boost = self.smooth_audio_level
        fft_val = self._sample_fft_field(u)

        # Ultra-fine needle taper at the ends (power 2.65 pinches ends into a fine thread)
        fine_tip_taper = np.sin(u * np.pi) ** 2.65

        # Asymmetric fluid lobes for natural S-curve wave body
        lobe_1 = 0.58 * np.exp(-((u - 0.19) / 0.075) ** 2)   # Left gentle swell
        lobe_2 = 0.80 * np.exp(-((u - 0.30) / 0.078) ** 2)   # Left-mid dip
        lobe_3 = 0.98 * np.exp(-((u - 0.44) / 0.090) ** 2)   # Center-left crest
        lobe_4 = 1.15 * np.exp(-((u - 0.58) / 0.088) ** 2)   # Center-right deep trough
        lobe_5 = 1.30 * np.exp(-((u - 0.72) / 0.072) ** 2)   # Right tall curling peak
        lobe_6 = 0.72 * np.exp(-((u - 0.82) / 0.058) ** 2)   # Far-right delicate hook

        env = fine_tip_taper * (0.12 + 0.88 * (lobe_1 + lobe_2 + lobe_3 + lobe_4 + lobe_5 + lobe_6))

        # Exact gain & FFT surge formula from audio_spectrum_hud.py
        carrier_ref = 0.72 + 0.28 * np.sin(u * 35.0 - p * 2.4)
        breathing = 0.92 + 0.08 * np.sin(t * 2.2 + u * 4.0)
        active_gain = self.idle_amplitude + (1.0 - self.idle_amplitude) * min(1.0, audio_boost * 1.2)
        fft_surge = fft_val * env * 0.65 * (0.4 + 0.6 * carrier_ref)

        amp = np.clip(env * breathing * active_gain + fft_surge, 0.0, 1.35)

        # Master carrier wave sculpted to match the S-curve rhythm of the image
        spine_y = (
            -19.0 * np.sin(u * 4.3 * np.pi - p * 1.05 + 0.25)
            + 14.5 * np.cos(u * 6.7 * np.pi + p * 0.72 - 0.85)
            - 11.0 * np.sin(u * 9.8 * np.pi - p * 1.40 + 1.30)
            + 6.5 * np.cos(u * 14.2 * np.pi + p * 1.85) * (0.4 + 0.6 * u)
        ) * amp

        # Horizontal curl displacement (creates overhanging wave hooks & folding loops)
        curl_x_base = (
            14.0 * np.cos(u * 6.7 * np.pi + p * 0.72 - 0.85)
            - 11.5 * np.sin(u * 10.5 * np.pi - p * 1.35 + 0.6)
        ) * (amp ** 1.3)

        # 7 distinct twisting ribbons around the spine
        strand_configs = [
            (3.2,  1.25, 0.00,  24.0,  1.15, "cyan_high"),     # 0: Upper curling crest edge
            (4.6, -1.10, 1.15,  19.5, -0.85, "azure_deep"),    # 1: Deep blue twisting fold
            (5.8,  1.55, 2.30,  22.0,  0.95, "emerald_silk"),  # 2: Emerald main body ribbon
            (3.9, -1.40, 3.60, -21.0,  1.05, "cyan_bright"),   # 3: Lower sweeping caustic rim
            (7.1,  1.80, 0.75,  14.5, -1.10, "aqua_core"),     # 4: Inner tight vortex filament
            (6.4, -1.65, 4.40, -16.5,  0.75, "blue_fold"),     # 5: Secondary under-curl
            (8.5,  2.10, 1.90,   9.5, -0.60, "white_caustic"), # 6: High-energy core tendril
        ]

        strands = []
        for freq, spd, ph, y_rad, x_curl, c_mode in strand_configs:
            angle = u * freq * np.pi + p * spd + ph
            wave_y = np.sin(angle) + 0.32 * np.sin(2.0 * angle + 0.6)
            wave_x = np.cos(angle - 0.4) * x_curl

            # Extra tip pinch ensures all strands collapse to a single fine point at u=0 and u=1
            sx = base_x + (curl_x_base * 0.65 + wave_x * 9.5 * (amp ** 1.25)) * fine_tip_taper
            sy = cy + spine_y * (0.82 + 0.18 * np.cos(angle * 0.5)) + wave_y * y_rad * amp

            pts = [QtCore.QPointF(float(sx[i]), float(sy[i])) for i in range(num_pts)]
            strands.append((pts, c_mode, sx, sy))

        return strands, span_x, cy

    def _make_silk_gradient(self, span_x: float, mode: str, alpha_scale: float = 1.0) -> QtGui.QLinearGradient:
        """
        Multi-stop horizontal gradients with feathered tip alpha so the ends look
        delicate, sharp, and finely tapered rather than thick or blunt.
        """
        grad = QtGui.QLinearGradient(-span_x, 0, span_x, 0)
        a = lambda val: int(max(0, min(255, val * alpha_scale)))

        if mode == "cyan_high":
            grad.setColorAt(0.00, QtGui.QColor(110, 255, 245, a(15)))
            grad.setColorAt(0.07, QtGui.QColor(100, 255, 245, a(185)))
            grad.setColorAt(0.18, QtGui.QColor(45, 235, 255, a(210)))
            grad.setColorAt(0.42, QtGui.QColor(30, 250, 210, a(225)))
            grad.setColorAt(0.62, QtGui.QColor(50, 195, 255, a(195)))
            grad.setColorAt(0.78, QtGui.QColor(40, 255, 195, a(235)))
            grad.setColorAt(0.93, QtGui.QColor(100, 255, 245, a(185)))
            grad.setColorAt(1.00, QtGui.QColor(110, 255, 245, a(15)))
        elif mode == "azure_deep":
            grad.setColorAt(0.00, QtGui.QColor(40, 210, 235, a(10)))
            grad.setColorAt(0.08, QtGui.QColor(40, 210, 235, a(145)))
            grad.setColorAt(0.22, QtGui.QColor(25, 115, 245, a(195)))
            grad.setColorAt(0.50, QtGui.QColor(15, 175, 220, a(165)))
            grad.setColorAt(0.65, QtGui.QColor(20, 95, 235, a(210)))
            grad.setColorAt(0.86, QtGui.QColor(30, 145, 240, a(185)))
            grad.setColorAt(0.93, QtGui.QColor(55, 225, 235, a(145)))
            grad.setColorAt(1.00, QtGui.QColor(55, 225, 235, a(10)))
        elif mode == "emerald_silk":
            grad.setColorAt(0.00, QtGui.QColor(70, 255, 220, a(12)))
            grad.setColorAt(0.07, QtGui.QColor(70, 255, 220, a(175)))
            grad.setColorAt(0.28, QtGui.QColor(15, 230, 170, a(215)))
            grad.setColorAt(0.52, QtGui.QColor(25, 245, 185, a(220)))
            grad.setColorAt(0.74, QtGui.QColor(10, 235, 165, a(225)))
            grad.setColorAt(0.93, QtGui.QColor(80, 255, 225, a(175)))
            grad.setColorAt(1.00, QtGui.QColor(80, 255, 225, a(12)))
        elif mode == "cyan_bright":
            grad.setColorAt(0.00, QtGui.QColor(130, 255, 250, a(15)))
            grad.setColorAt(0.07, QtGui.QColor(130, 255, 250, a(190)))
            grad.setColorAt(0.32, QtGui.QColor(45, 245, 215, a(215)))
            grad.setColorAt(0.58, QtGui.QColor(35, 185, 255, a(225)))
            grad.setColorAt(0.82, QtGui.QColor(55, 255, 195, a(235)))
            grad.setColorAt(0.93, QtGui.QColor(130, 255, 250, a(190)))
            grad.setColorAt(1.00, QtGui.QColor(130, 255, 250, a(15)))
        elif mode == "blue_fold":
            grad.setColorAt(0.00, QtGui.QColor(30, 180, 220, a(10)))
            grad.setColorAt(0.08, QtGui.QColor(30, 180, 220, a(130)))
            grad.setColorAt(0.25, QtGui.QColor(35, 105, 230, a(175)))
            grad.setColorAt(0.58, QtGui.QColor(15, 130, 245, a(190)))
            grad.setColorAt(0.85, QtGui.QColor(25, 195, 185, a(165)))
            grad.setColorAt(0.93, QtGui.QColor(45, 220, 225, a(130)))
            grad.setColorAt(1.00, QtGui.QColor(45, 220, 225, a(10)))
        else:  # aqua_core / white_caustic
            grad.setColorAt(0.00, QtGui.QColor(225, 255, 252, a(40)))
            grad.setColorAt(0.05, QtGui.QColor(215, 255, 250, a(220)))
            grad.setColorAt(0.20, QtGui.QColor(165, 250, 255, a(230)))
            grad.setColorAt(0.48, QtGui.QColor(175, 255, 235, a(240)))
            grad.setColorAt(0.68, QtGui.QColor(140, 225, 255, a(215)))
            grad.setColorAt(0.85, QtGui.QColor(180, 255, 235, a(240)))
            grad.setColorAt(0.95, QtGui.QColor(215, 255, 250, a(220)))
            grad.setColorAt(1.00, QtGui.QColor(225, 255, 252, a(40)))
        return grad

    def draw_liquid_spectrum(self, painter: QtGui.QPainter):
        strands, span_x, cy = self._compute_fluid_strands(num_pts=140)
        spline_paths = [(self._build_smooth_path(pts), mode) for pts, mode, _, _ in strands]

        # -------------------------------------------------------------------------
        # LAYER 1: Soft Atmospheric Sub-Surface Glow
        # -------------------------------------------------------------------------
        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Plus)
        halo_ribbon = self._build_closed_ribbon(strands[0][0], strands[3][0])
        halo_grad = QtGui.QLinearGradient(-span_x, -45, span_x, 45)
        halo_grad.setColorAt(0.00, QtGui.QColor(10, 180, 190, 0))
        halo_grad.setColorAt(0.10, QtGui.QColor(10, 180, 190, 18))
        halo_grad.setColorAt(0.25, QtGui.QColor(15, 95, 210, 28))
        halo_grad.setColorAt(0.52, QtGui.QColor(10, 195, 155, 32))
        halo_grad.setColorAt(0.75, QtGui.QColor(15, 130, 220, 28))
        halo_grad.setColorAt(0.90, QtGui.QColor(15, 195, 185, 18))
        halo_grad.setColorAt(1.00, QtGui.QColor(15, 195, 185, 0))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QBrush(halo_grad))
        painter.drawPath(halo_ribbon)

        # -------------------------------------------------------------------------
        # LAYER 2: Translucent Folding Silk Veils
        # -------------------------------------------------------------------------
        veil_pairs = [
            (0, 2, "emerald_silk", 0.20),
            (1, 3, "azure_deep",   0.24),
            (2, 4, "cyan_high",    0.18),
            (3, 5, "blue_fold",    0.22),
            (0, 4, "emerald_silk", 0.15),
            (4, 6, "cyan_bright",  0.20),
        ]
        for idx_a, idx_b, mode, alpha_mul in veil_pairs:
            veil_path = self._build_closed_ribbon(strands[idx_a][0], strands[idx_b][0])
            veil_grad = self._make_silk_gradient(span_x, mode, alpha_scale=alpha_mul)
            painter.setBrush(QtGui.QBrush(veil_grad))
            painter.drawPath(veil_path)

        # -------------------------------------------------------------------------
        # LAYER 3: Deep Internal Fold Shadows (3D hollow glass pockets)
        # -------------------------------------------------------------------------
        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceOver)
        pocket_1 = self._build_closed_ribbon(strands[1][0], strands[5][0])
        pocket_2 = self._build_closed_ribbon(strands[2][0], strands[3][0])

        shadow_grad = QtGui.QLinearGradient(0, -45, 0, 45)
        shadow_grad.setColorAt(0.0, QtGui.QColor(3, 9, 15, 40))
        shadow_grad.setColorAt(0.5, QtGui.QColor(3, 9, 15, 140))
        shadow_grad.setColorAt(1.0, QtGui.QColor(3, 9, 15, 40))
        painter.setBrush(QtGui.QBrush(shadow_grad))
        painter.drawPath(pocket_1)

        shadow_grad_2 = QtGui.QLinearGradient(0, -35, 0, 35)
        shadow_grad_2.setColorAt(0.0, QtGui.QColor(4, 12, 22, 25))
        shadow_grad_2.setColorAt(0.5, QtGui.QColor(3, 9, 15, 95))
        shadow_grad_2.setColorAt(1.0, QtGui.QColor(4, 12, 22, 25))
        painter.setBrush(QtGui.QBrush(shadow_grad_2))
        painter.drawPath(pocket_2)

        # -------------------------------------------------------------------------
        # LAYER 4: Silky Multi-Pass Rim Glow Along Every Folding Edge
        # -------------------------------------------------------------------------
        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Plus)
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)

        stroke_passes = [
            (11.5, 0.07),   # Soft atmospheric outer sheen
            (5.8,  0.16),   # Mid liquid body glow
            (2.9,  0.38),   # Defined ribbon fold boundary
            (1.4,  0.80),   # Fine refractive edge
        ]

        strand_weights = [1.15, 0.90, 1.08, 1.12, 0.95, 0.80, 0.85]

        for base_w, alpha_mul in stroke_passes:
            for (path, mode), w_mul in zip(spline_paths, strand_weights):
                grad = self._make_silk_gradient(span_x, mode, alpha_scale=alpha_mul)
                pen = QtGui.QPen(QtGui.QBrush(grad), base_w * w_mul)
                pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(path)

        # -------------------------------------------------------------------------
        # LAYER 5: Razor-Sharp Specular Caustic Highlights
        # -------------------------------------------------------------------------
        caustic_grad = self._make_silk_gradient(span_x, "white_caustic", alpha_scale=0.92)
        primary_indices = [0, 2, 3, 4, 6]
        for idx in primary_indices:
            path, _ = spline_paths[idx]
            thick = 1.15 if idx in (0, 3) else 0.82
            pen = QtGui.QPen(QtGui.QBrush(caustic_grad), thick)
            pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)

        # -------------------------------------------------------------------------
        # LAYER 6: Delicate Needle-Fine Glowing Filaments at Left & Right Ends
        # -------------------------------------------------------------------------
        for side_sign in (-1.0, 1.0):
            tip_x = side_sign * span_x
            # Subtle, tight radial glow so the tip stays fine and delicate
            tip_glow = QtGui.QRadialGradient(tip_x - side_sign * 14.0, cy, 24.0)
            tip_glow.setColorAt(0.0, QtGui.QColor(180, 255, 245, 135))
            tip_glow.setColorAt(0.35, QtGui.QColor(40, 240, 215, 55))
            tip_glow.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))

            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QBrush(tip_glow))
            painter.drawEllipse(QtCore.QPointF(tip_x - side_sign * 14.0, cy), 24.0, 3.2)

            # Tapered 1.2px needle core fading out cleanly at the very tip
            tip_line_grad = QtGui.QLinearGradient(tip_x, cy, tip_x - side_sign * 34.0, cy)
            tip_line_grad.setColorAt(0.0, QtGui.QColor(160, 255, 250, 0))
            tip_line_grad.setColorAt(0.25, QtGui.QColor(210, 255, 250, 195))
            tip_line_grad.setColorAt(1.0, QtGui.QColor(140, 250, 240, 90))

            core_line_pen = QtGui.QPen(QtGui.QBrush(tip_line_grad), 1.35)
            core_line_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            painter.setPen(core_line_pen)
            painter.drawLine(
                QtCore.QPointF(tip_x, cy),
                QtCore.QPointF(tip_x - side_sign * 34.0, cy),
            )

    def draw_hud_frame(self, painter):
        painter.save()
        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceOver)

        bracket_color = QtGui.QColor(65, 165, 155, 200)
        pen = QtGui.QPen(bracket_color)
        pen.setWidthF(2.2)
        pen.setCapStyle(QtCore.Qt.PenCapStyle.SquareCap)
        pen.setJoinStyle(QtCore.Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)

        left_x, right_x = -428.0, 428.0
        top_y, bot_y = -74.0, 78.0
        arm = 14.0

        painter.drawPolyline([
            QtCore.QPointF(left_x, top_y + arm),
            QtCore.QPointF(left_x, top_y),
            QtCore.QPointF(left_x + arm, top_y)
        ])
        painter.drawPolyline([
            QtCore.QPointF(right_x - arm, top_y),
            QtCore.QPointF(right_x, top_y),
            QtCore.QPointF(right_x, top_y + arm)
        ])
        painter.drawPolyline([
            QtCore.QPointF(left_x, bot_y - arm),
            QtCore.QPointF(left_x, bot_y),
            QtCore.QPointF(left_x + arm, bot_y)
        ])
        painter.drawPolyline([
            QtCore.QPointF(right_x - arm, bot_y),
            QtCore.QPointF(right_x, bot_y),
            QtCore.QPointF(right_x, bot_y - arm)
        ])

        title_font = QtGui.QFont("Bahnschrift", 13, QtGui.QFont.Weight.DemiBold)
        title_font.setStyleStrategy(QtGui.QFont.StyleStrategy.PreferAntialias)
        title_font.setLetterSpacing(QtGui.QFont.SpacingType.AbsoluteSpacing, 0.8)
        painter.setFont(title_font)
        painter.setPen(QtGui.QColor(95, 178, 180, 225))
        painter.drawText(QtCore.QPointF(left_x - 1.0, top_y - 12.0), "AUDIO SPECTRUM")

        status_font = QtGui.QFont("Bahnschrift", 14, QtGui.QFont.Weight.DemiBold)
        status_font.setStyleStrategy(QtGui.QFont.StyleStrategy.PreferAntialias)
        painter.setFont(status_font)

        status_rect = QtCore.QRectF(-180.0, bot_y - 18.0, 360.0, 30.0)
        glow_c = QtGui.QColor(self.status_color)
        glow_c.setAlpha(int(65 + self.smooth_audio_level * 90))
        painter.setPen(glow_c)
        painter.drawText(status_rect.translated(0, 0.5), QtCore.Qt.AlignmentFlag.AlignCenter, self.status_text)

        main_c = QtGui.QColor(self.status_color)
        main_c.setAlpha(235)
        painter.setPen(main_c)
        painter.drawText(status_rect, QtCore.Qt.AlignmentFlag.AlignCenter, self.status_text)

        painter.restore()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Deep dark navy-slate HUD background matched to audio_spectrum_hud.py
        painter.fillRect(self.rect(), QtGui.QColor(3, 9, 15))

        w, h = self.width(), self.height()
        painter.translate(w / 2.0, h / 2.0)

        scale = min(w / 920.0, h / 230.0)
        painter.scale(scale, scale)

        self.draw_liquid_spectrum(painter)
        self.draw_hud_frame(painter)

        painter.end()

    def update_animation(self):
        # Exact update_animation dynamics from audio_spectrum_hud.py
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

        # Only decay raw levels manually if sounddevice stream isn't running (external push fallback)
        if self.audio_stream is None:
            self.raw_audio_level *= 0.92
            self.raw_fft_bins *= 0.90

        self.phase_time += 0.016 * (1.0 + self.smooth_audio_level * 2.2)
        self.update()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    fmt = QtGui.QSurfaceFormat()
    fmt.setSamples(4)
    QtGui.QSurfaceFormat.setDefaultFormat(fmt)

    window = QtWidgets.QMainWindow()
    window.setWindowTitle("Atlas Core Engine - Audio Spectrum HUD")
    window.resize(920, 250)

    hud = AudioSpectrumHUD(window)
    window.setCentralWidget(hud)
    window.show()
    sys.exit(app.exec())