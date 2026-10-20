import math
import random
from PySide6 import QtCore, QtWidgets, QtGui

class AtomicSolarHUD(QtWidgets.QWidget):
    """Left-column 3D orbital hologram that reacts exclusively to the AI's voice (TTS)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 260)
        self.raw_audio_level = 0.0
        self.smooth_audio_level = 0.0
        self.ai_sensitivity = 1.35
        self.base_time = 0.0
        self.orbit_time = 0.0
        self.track_time = 0.0
        self.plasma_time = 0.0
        self.dust_time = 0.0
        random.seed(42)

        self.wave_shell_particles = []
        num_shell_particles = 2000
        for i in range(num_shell_particles):
            angle = (i / num_shell_particles) * 2.0 * math.pi
            ribbon = i % 3
            palette = [(0, 230, 255), (40, 255, 190), (80, 190, 255)]
            r, g, b = random.choice(palette)
            self.wave_shell_particles.append({
                "base_angle": angle,
                "ribbon": ribbon,
                "radial_jitter": random.gauss(0.0, 4.0),
                "z": random.uniform(-35.0, 35.0),
                "speed": random.uniform(0.12, 0.25),
                "size": random.uniform(0.8, 1.9),
                "alpha": random.randint(75, 190),
                "rgb": (r, g, b),
                "phase": random.uniform(0, 2 * math.pi),
            })

        self.mint_ring_particles = []
        for i in range(800):
            angle = random.uniform(0, 2 * math.pi)
            cluster = math.sin(angle * 7.0) * 3.0 + math.cos(angle * 13.0) * 2.0
            self.mint_ring_particles.append({
                "angle": angle,
                "r_off": random.gauss(0.0, 3.2) + cluster * 0.6,
                "z_off": random.gauss(0.0, 4.0),
                "speed": random.uniform(0.15, 0.35),
                "size": random.uniform(1.0, 2.6),
                "alpha": random.randint(60, 210),
                "is_hotspot": random.random() < 0.08,
            })

        self.core_dust = []
        for _ in range(160):
            self.core_dust.append({
                "r": random.uniform(5.0, 85.0),
                "angle": random.uniform(0, 2 * math.pi),
                "speed": random.uniform(-0.15, 0.15),
                "size": random.uniform(0.7, 1.6),
                "alpha": random.randint(30, 110),
            })

        self.ambient_sparks = []
        for _ in range(36):
            self.ambient_sparks.append({
                "angle": random.uniform(0, 2 * math.pi),
                "dist": random.uniform(195.0, 255.0),
                "speed": random.uniform(-0.06, 0.06),
                "size": random.uniform(2.5, 6.5),
                "rgb": random.choice([(0, 255, 170), (0, 210, 255), (70, 140, 255)]),
                "pulse_speed": random.uniform(1.5, 3.5),
                "phase": random.uniform(0, 2 * math.pi),
            })

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)

    def set_ai_voice_level(self, level: float):
        """Called by TTSEngine when ATLAS speaks (0.0 when silent, up to 1.0 on syllables)."""
        self.raw_audio_level = max(0.0, min(1.0, float(level)))

    @staticmethod
    def project_3d(x, y, z, rx, ry, rz):
        cos_x, sin_x = math.cos(rx), math.sin(rx)
        y1 = y * cos_x - z * sin_x
        z1 = y * sin_x + z * cos_x
        x1 = x

        cos_y, sin_y = math.cos(ry), math.sin(ry)
        x2 = x1 * cos_y + z1 * sin_y
        z2 = -x1 * sin_y + z1 * cos_y
        y2 = y1

        cos_z, sin_z = math.cos(rz), math.sin(rz)
        x3 = x2 * cos_z - y2 * sin_z
        y3 = x2 * sin_z + y2 * cos_z
        z3 = z2
        return x3, y3, z3

    def draw_glowing_node(self, painter, x, y, radius, rgb, intensity=1.0):
        r, g, b = rgb
        glow_radius = radius * 4.2
        grad = QtGui.QRadialGradient(QtCore.QPointF(x, y), glow_radius)
        grad.setColorAt(0.0, QtGui.QColor(255, 255, 255, int(255 * intensity)))
        grad.setColorAt(0.18, QtGui.QColor(min(255, r + 90), min(255, g + 90), min(255, b + 90), int(240 * intensity)))
        grad.setColorAt(0.45, QtGui.QColor(r, g, b, int(140 * intensity)))
        grad.setColorAt(0.75, QtGui.QColor(r, g, b, int(40 * intensity)))
        grad.setColorAt(1.0, QtGui.QColor(r, g, b, 0))

        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QBrush(grad))
        painter.drawEllipse(QtCore.QPointF(x, y), glow_radius, glow_radius)

    def draw_comet_orbit(self, painter, rx_radius, ry_radius, rx, ry, rz, rgb, base_width, nodes, base_alpha=70):
        segments = 140
        pts = []
        for i in range(segments + 1):
            a = (i / segments) * 2.0 * math.pi
            bx, by = rx_radius * math.cos(a), ry_radius * math.sin(a)
            sx, sy, sz = self.project_3d(bx, by, 0.0, rx, ry, rz)
            pts.append((sx, sy, sz, a))

        r, g, b = rgb
        boost = self.smooth_audio_level

        if base_alpha > 0:
            effective_alpha = min(255, int(base_alpha * (1.0 + boost * 0.8)))
            for pass_width, pass_alpha in [(base_width * 3.0, effective_alpha * 0.3), (base_width, effective_alpha)]:
                pen = QtGui.QPen(QtGui.QColor(r, g, b, int(pass_alpha)))
                pen.setWidthF(pass_width)
                pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                for i in range(segments):
                    painter.drawLine(QtCore.QPointF(pts[i][0], pts[i][1]), QtCore.QPointF(pts[i + 1][0], pts[i + 1][1]))

        for node in nodes:
            speed, phase = node["speed"], node["phase"]
            tail_len = node.get("tail_len", 1.8) * (1.0 + boost * 0.5)
            node_size = node.get("size", 5.0) * (1.0 + boost * 0.4)
            direction = 1.0 if speed >= 0 else -1.0
            head_angle = (self.orbit_time * speed + phase) % (2.0 * math.pi)

            tail_steps = 45
            for s in range(tail_steps):
                t0, t1 = s / tail_steps, (s + 1) / tail_steps
                a0 = head_angle - direction * (t0 * tail_len)
                a1 = head_angle - direction * (t1 * tail_len)
                x0, y0, _ = self.project_3d(rx_radius * math.cos(a0), ry_radius * math.sin(a0), 0.0, rx, ry, rz)
                x1, y1, _ = self.project_3d(rx_radius * math.cos(a1), ry_radius * math.sin(a1), 0.0, rx, ry, rz)

                fade = (1.0 - t0) ** 1.7
                glow_pen = QtGui.QPen(QtGui.QColor(r, g, b, int(110 * fade)))
                glow_pen.setWidthF(base_width * 3.6 * fade + 0.5)
                glow_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
                painter.setPen(glow_pen)
                painter.drawLine(QtCore.QPointF(x0, y0), QtCore.QPointF(x1, y1))

                core_pen = QtGui.QPen(QtGui.QColor(
                    int(r + (255 - r) * (fade ** 2)),
                    int(g + (255 - g) * (fade ** 2)),
                    int(b + (255 - b) * (fade ** 2)),
                    int(245 * fade),
                ))
                core_pen.setWidthF(base_width * 1.4 * fade + 0.4)
                core_pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
                painter.setPen(core_pen)
                painter.drawLine(QtCore.QPointF(x0, y0), QtCore.QPointF(x1, y1))

            hx, hy, hz = self.project_3d(rx_radius * math.cos(head_angle), ry_radius * math.sin(head_angle), 0.0, rx, ry, rz)
            depth_scale = 1.0 + (hz / max(rx_radius, 1.0)) * 0.18
            self.draw_glowing_node(painter, hx, hy, node_size * depth_scale, rgb, intensity=min(1.0, 0.9 + boost * 0.4))

    def draw_concentric_glow_ring(self, painter, radius, rx, ry, rz, rgb, width, gap_angle=None, gap_span=0.6):
        segments = 120
        r, g, b = rgb
        pts = []
        for i in range(segments + 1):
            a = (i / segments) * 2.0 * math.pi
            sx, sy, _ = self.project_3d(radius * math.cos(a), radius * math.sin(a), 0.0, rx, ry, rz)
            pts.append((sx, sy, a))

        for i in range(segments):
            a = pts[i][2]
            fade = 1.0
            if gap_angle is not None:
                diff = abs((a - gap_angle + math.pi) % (2 * math.pi) - math.pi)
                if diff < gap_span:
                    fade = (diff / gap_span) ** 1.5
            if fade < 0.05:
                continue

            p1, p2 = QtCore.QPointF(pts[i][0], pts[i][1]), QtCore.QPointF(pts[i + 1][0], pts[i + 1][1])
            pen_glow = QtGui.QPen(QtGui.QColor(r, g, b, int(65 * fade)))
            pen_glow.setWidthF(width * 3.5)
            pen_glow.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_glow)
            painter.drawLine(p1, p2)

            pen_core = QtGui.QPen(QtGui.QColor(min(255, r + 60), min(255, g + 60), min(255, b + 60), int(210 * fade)))
            pen_core.setWidthF(width)
            pen_core.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_core)
            painter.drawLine(p1, p2)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(5, 10, 18))

        w, h = self.width(), self.height()
        painter.translate(w / 2.0, h / 2.0)
        scale = min(w, h) / 510.0
        painter.scale(scale, scale)
        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Plus)

        audio = self.smooth_audio_level

        nebula_radius = 210.0 + audio * 45.0
        nebula_grad = QtGui.QRadialGradient(QtCore.QPointF(0, 0), nebula_radius)
        nebula_grad.setColorAt(0.0, QtGui.QColor(0, 110, 130, int(55 + audio * 130)))
        nebula_grad.setColorAt(0.35, QtGui.QColor(0, 75, 110, int(35 + audio * 85)))
        nebula_grad.setColorAt(0.75, QtGui.QColor(15, 30, 70, 15))
        nebula_grad.setColorAt(1.0, QtGui.QColor(0, 0, 0, 0))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QBrush(nebula_grad))
        painter.drawEllipse(QtCore.QPointF(0, 0), nebula_radius, nebula_radius)

        for d in self.core_dust:
            ang = d["angle"] + self.dust_time * d["speed"]
            dust_r = d["r"] * (1.0 + audio * 0.18)
            painter.setBrush(QtGui.QColor(80, 240, 255, min(255, int(d["alpha"] * (1.0 + audio * 1.5)))))
            painter.drawEllipse(QtCore.QPointF(dust_r * math.cos(ang), dust_r * math.sin(ang)), d["size"], d["size"])

        base_shell_radius = 198.0 + audio * 24.0
        wave_boost = 1.0 + audio * 2.6
        for p in self.wave_shell_particles:
            ang = p["base_angle"] + self.base_time * 0.08 * (1 if p["ribbon"] % 2 == 0 else -1)
            rib_phase = p["ribbon"] * (2.0 * math.pi / 3.0)

            wave1 = 8.5 * wave_boost * math.sin(5.0 * ang + self.base_time * 1.1 + rib_phase)
            wave2 = 5.5 * wave_boost * math.cos(8.0 * ang - self.base_time * 0.8 - rib_phase)
            wave3 = 3.5 * wave_boost * math.sin(13.0 * ang + self.base_time * 1.6)

            r = base_shell_radius + wave1 + wave2 + wave3 + p["radial_jitter"]
            sx, sy, _ = self.project_3d(r * math.cos(ang), r * math.sin(ang), p["z"] * math.sin(3.0 * ang + self.base_time * 0.5), 0.18, 0.15, 0.0)

            twinkle = 0.75 + 0.25 * math.sin(self.base_time * 2.5 + p["phase"])
            alpha = int(max(25, min(255, p["alpha"] * twinkle * (1.0 + audio * 0.8))))
            painter.setBrush(QtGui.QColor(p["rgb"][0], p["rgb"][1], p["rgb"][2], alpha))
            painter.drawEllipse(QtCore.QPointF(sx, sy), p["size"], p["size"])

        self.draw_concentric_glow_ring(
            painter, 66.0 + audio * 8.0, 0.22 * math.sin(self.base_time * 0.5), 0.22 * math.cos(self.base_time * 0.5), 0.0,
            (0, 235, 215), 2.0, -0.55 + self.track_time * 0.35, 0.55
        )
        self.draw_concentric_glow_ring(painter, 96.0 + audio * 5.0, 0.32, -0.18, self.track_time * 0.12, (115, 90, 255), 2.2)
        self.draw_concentric_glow_ring(painter, 104.0 + audio * 4.0, -0.25, 0.28, -self.track_time * 0.15, (95, 110, 255), 1.2, 1.8 - self.track_time * 0.2, 0.9)
        self.draw_concentric_glow_ring(painter, 134.0 + audio * 6.0, 0.14, -0.12, self.track_time * 0.05, (20, 255, 165), 2.4, 0.15, 0.45)

        for mp in self.mint_ring_particles:
            ang = mp["angle"] + self.plasma_time * mp["speed"] * 0.25
            plasma_shake = audio * random.uniform(-4.0, 4.0)
            r = 134.0 + mp["r_off"] + audio * 6.0 + 2.2 * math.sin(ang * 6.0 - self.base_time * 1.4) + plasma_shake
            sx, sy, _ = self.project_3d(r * math.cos(ang), r * math.sin(ang), mp["z_off"], 0.14, -0.12, 0.0)

            p_alpha = min(255, int(mp["alpha"] * (1.0 + audio * 0.6)))
            painter.setBrush(QtGui.QColor(200, 255, 230, p_alpha) if mp["is_hotspot"] else QtGui.QColor(30, 255, 175, p_alpha))
            sz = mp["size"] * 1.3 if mp["is_hotspot"] else mp["size"]
            painter.drawEllipse(QtCore.QPointF(sx, sy), sz, sz)

        wobble_x = 0.06 * math.sin(self.base_time * 0.7)
        wobble_y = 0.06 * math.cos(self.base_time * 0.6)

        self.draw_comet_orbit(
            painter, 158.0, 158.0, 1.18 + wobble_x, 0.15 + wobble_y, -0.68 + (self.track_time * 0.15),
            (0, 195, 255), 2.0, [{"speed": 0.85, "phase": 2.6, "tail_len": 2.2, "size": 6.0}, {"speed": 0.85, "phase": 5.7, "tail_len": 1.6, "size": 5.5}], 85
        )
        self.draw_comet_orbit(
            painter, 142.0, 142.0, 1.02 - wobble_x, -0.22 + wobble_y, -0.52 - (self.track_time * 0.12),
            (20, 225, 255), 1.8, [{"speed": -0.95, "phase": 0.4, "tail_len": 1.9, "size": 4.8}, {"speed": -0.95, "phase": 3.5, "tail_len": 1.5, "size": 4.5}], 75
        )
        self.draw_comet_orbit(
            painter, 116.0, 116.0, 0.92 + wobble_y, 0.35 - wobble_x, -0.78 + (self.track_time * 0.11),
            (0, 240, 230), 1.6, [{"speed": 1.15, "phase": 1.1, "tail_len": 1.7, "size": 4.5}], 65
        )
        self.draw_comet_orbit(
            painter, 172.0, 162.0, 0.38, 0.42, 2.2 + (self.track_time * 0.08),
            (65, 135, 255), 1.6, [{"speed": 0.55, "phase": 1.9, "tail_len": 2.5, "size": 3.8}], 40
        )
        self.draw_comet_orbit(
            painter, 180.0, 172.0, 0.35 + wobble_x * 0.5, -0.38 + wobble_y * 0.5, -0.45 - (self.track_time * 0.2),
            (0, 195, 255), 3.0, [{"speed": -0.65, "phase": -0.55, "tail_len": 2.6, "size": 8.2}], 15
        )

        for sp in self.ambient_sparks:
            ang = sp["angle"] + self.base_time * sp["speed"]
            r = sp["dist"] + audio * 15.0 + 4.0 * math.sin(self.base_time * 0.8 + sp["phase"])
            pulse = 0.55 + 0.45 * math.sin(self.base_time * sp["pulse_speed"] + sp["phase"])
            self.draw_glowing_node(painter, r * math.cos(ang), r * math.sin(ang), sp["size"] * 0.5, sp["rgb"], intensity=pulse)

        painter.end()

    def update_animation(self):
        self.base_time += 0.016
        target = min(1.0, self.raw_audio_level * self.ai_sensitivity)
        if target > self.smooth_audio_level:
            self.smooth_audio_level += (target - self.smooth_audio_level) * 0.42
        else:
            self.smooth_audio_level += (target - self.smooth_audio_level) * 0.08

        self.orbit_time += 0.016 * (1.0 + self.smooth_audio_level * 1.6)
        self.track_time += 0.016 * (1.0 + self.smooth_audio_level * 2.1)
        self.plasma_time += 0.016 * (1.0 + self.smooth_audio_level * 1.6)
        self.dust_time += 0.016 * (1.0 + self.smooth_audio_level * 2.0)
        self.update()