from PIL import Image, ImageDraw
import customtkinter as ctk


class IconFactory:
    """Renders crisp, anti-aliased vector icons using 4x supersampling in Pillow."""

    _cache = {}

    @classmethod
    def get(cls, name: str, size: int = 18, color: str = "#f3f4f6") -> ctk.CTkImage:
        key = (name, size, color)
        if key in cls._cache:
            return cls._cache[key]

        scale = 4
        s = size * scale
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        w = max(6, int(s * 0.095))

        if name == "mic":
            d.rounded_rectangle((s * 0.34, s * 0.12, s * 0.66, s * 0.58), radius=s * 0.16, outline=color, width=w)
            d.arc((s * 0.20, s * 0.26, s * 0.80, s * 0.74), start=0, end=180, fill=color, width=w)
            d.line((s * 0.50, s * 0.74, s * 0.50, s * 0.88), fill=color, width=w)
            d.line((s * 0.32, s * 0.88, s * 0.68, s * 0.88), fill=color, width=w)

        elif name == "mic_off":
            d.rounded_rectangle((s * 0.34, s * 0.12, s * 0.66, s * 0.58), radius=s * 0.16, outline=color, width=w)
            d.arc((s * 0.20, s * 0.26, s * 0.80, s * 0.74), start=0, end=180, fill=color, width=w)
            d.line((s * 0.16, s * 0.16, s * 0.84, s * 0.84), fill="#ef4444", width=w + 2)

        elif name == "screen":
            d.rounded_rectangle((s * 0.10, s * 0.16, s * 0.90, s * 0.70), radius=s * 0.08, outline=color, width=w)
            d.line((s * 0.36, s * 0.86, s * 0.64, s * 0.86), fill=color, width=w)
            d.line((s * 0.50, s * 0.70, s * 0.50, s * 0.86), fill=color, width=w)
            # Target reticle inside monitor
            d.ellipse((s * 0.40, s * 0.33, s * 0.60, s * 0.53), outline=color, width=max(4, w - 2))

        elif name == "send":
            pts = [(s * 0.14, s * 0.50), (s * 0.86, s * 0.16), (s * 0.62, s * 0.86), (s * 0.46, s * 0.58)]
            d.polygon(pts, outline=color, width=w)
            d.line((s * 0.46, s * 0.58, s * 0.86, s * 0.16), fill=color, width=w)

        elif name == "stop":
            d.rounded_rectangle((s * 0.22, s * 0.22, s * 0.78, s * 0.78), radius=s * 0.10, fill=color)

        elif name == "tasks":
            d.rounded_rectangle((s * 0.18, s * 0.16, s * 0.82, s * 0.88), radius=s * 0.08, outline=color, width=w)
            d.line((s * 0.32, s * 0.38, s * 0.68, s * 0.38), fill=color, width=w)
            d.line((s * 0.32, s * 0.56, s * 0.68, s * 0.56), fill=color, width=w)
            d.line((s * 0.32, s * 0.72, s * 0.54, s * 0.72), fill=color, width=w)

        elif name == "memory":
            nodes = [(s * 0.30, s * 0.30), (s * 0.70, s * 0.28), (s * 0.50, s * 0.52), (s * 0.28, s * 0.72), (s * 0.72, s * 0.72)]
            edges = [(0, 1), (0, 2), (1, 2), (2, 3), (2, 4), (3, 4)]
            for i, j in edges:
                d.line((nodes[i][0], nodes[i][1], nodes[j][0], nodes[j][1]), fill=color, width=max(4, w - 2))
            r = s * 0.09
            for nx, ny in nodes:
                d.ellipse((nx - r, ny - r, nx + r, ny + r), fill=color)

        elif name == "sun":
            d.ellipse((s * 0.30, s * 0.30, s * 0.70, s * 0.70), outline=color, width=w)
            import math
            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                x1 = s * 0.5 + math.cos(rad) * (s * 0.28)
                y1 = s * 0.5 + math.sin(rad) * (s * 0.28)
                x2 = s * 0.5 + math.cos(rad) * (s * 0.40)
                y2 = s * 0.5 + math.sin(rad) * (s * 0.40)
                d.line((x1, y1, x2, y2), fill=color, width=w)

        elif name == "undo":
            d.arc((s * 0.24, s * 0.28, s * 0.82, s * 0.82), start=200, end=45, fill=color, width=w)
            d.line((s * 0.20, s * 0.42, s * 0.38, s * 0.22), fill=color, width=w)
            d.line((s * 0.20, s * 0.42, s * 0.42, s * 0.46), fill=color, width=w)

        elif name == "bell":
            d.arc((s * 0.22, s * 0.16, s * 0.78, s * 0.76), start=180, end=0, fill=color, width=w)
            d.line((s * 0.22, s * 0.46, s * 0.18, s * 0.72), fill=color, width=w)
            d.line((s * 0.78, s * 0.46, s * 0.82, s * 0.72), fill=color, width=w)
            d.line((s * 0.14, s * 0.72, s * 0.86, s * 0.72), fill=color, width=w)
            d.ellipse((s * 0.44, s * 0.76, s * 0.56, s * 0.88), fill=color)

        elif name == "bell_off":
            d.arc((s * 0.22, s * 0.16, s * 0.78, s * 0.76), start=180, end=0, fill=color, width=w)
            d.line((s * 0.14, s * 0.72, s * 0.86, s * 0.72), fill=color, width=w)
            d.line((s * 0.16, s * 0.16, s * 0.84, s * 0.84), fill="#f59e0b", width=w + 2)

        elif name == "pin":
            d.ellipse((s * 0.30, s * 0.16, s * 0.70, s * 0.56), outline=color, width=w)
            d.line((s * 0.50, s * 0.56, s * 0.50, s * 0.88), fill=color, width=w)

        elif name == "trash":
            d.line((s * 0.20, s * 0.26, s * 0.80, s * 0.26), fill=color, width=w)
            d.rounded_rectangle((s * 0.26, s * 0.26, s * 0.74, s * 0.86), radius=s * 0.06, outline=color, width=w)
            d.line((s * 0.38, s * 0.16, s * 0.62, s * 0.16), fill=color, width=w)

        elif name == "check":
            d.line((s * 0.20, s * 0.52, s * 0.42, s * 0.74), fill=color, width=w + 2)
            d.line((s * 0.42, s * 0.74, s * 0.82, s * 0.26), fill=color, width=w + 2)

        elif name == "sparkle":
            pts = [
                (s * 0.50, s * 0.10), (s * 0.60, s * 0.40),
                (s * 0.90, s * 0.50), (s * 0.60, s * 0.60),
                (s * 0.50, s * 0.90), (s * 0.40, s * 0.60),
                (s * 0.10, s * 0.50), (s * 0.40, s * 0.40),
            ]
            d.polygon(pts, fill=color)

        elif name == "whatsapp":
            d.ellipse((s * 0.14, s * 0.14, s * 0.86, s * 0.84), outline=color, width=w)
            d.polygon([(s * 0.16, s * 0.86), (s * 0.24, s * 0.66), (s * 0.38, s * 0.78)], fill=color)
            d.arc((s * 0.34, s * 0.32, s * 0.68, s * 0.66), start=30, end=210, fill=color, width=w)

        elif name == "rocket":
            d.ellipse((s * 0.28, s * 0.14, s * 0.72, s * 0.78), outline=color, width=w)
            d.line((s * 0.28, s * 0.64, s * 0.16, s * 0.82), fill=color, width=w)
            d.line((s * 0.72, s * 0.64, s * 0.84, s * 0.82), fill=color, width=w)

        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        ctk_icon = ctk.CTkImage(light_image=resized, dark_image=resized, size=(size, size))
        cls._cache[key] = ctk_icon
        return ctk_icon
