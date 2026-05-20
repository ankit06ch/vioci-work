"""Generate the synthetic example diagram set.

Runs as a script (``python -m examples.generate_fixtures``) and writes
example PNGs into ``examples/``. The diagrams are intentionally minimal
but cover each of the four canonical input shapes (electrical schematic,
mechanical truss, control block diagram, and a plotted line graph).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent


def _font(size: int = 14):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except OSError:
        return ImageFont.load_default()


def make_rc_circuit() -> Image.Image:
    img = Image.new("RGB", (600, 300), "white")
    d = ImageDraw.Draw(img)
    f = _font(16)
    # resistor
    d.rectangle([120, 100, 200, 140], outline="black", width=3)
    d.text((140, 70), "R = 10kΩ", fill="black", font=f)
    # capacitor (two parallel plates)
    d.line([380, 90, 380, 150], fill="black", width=3)
    d.line([400, 90, 400, 150], fill="black", width=3)
    d.text((360, 60), "C = 1µF", fill="black", font=f)
    # source
    d.ellipse([20, 100, 70, 150], outline="black", width=3)
    d.text((30, 70), "Vs", fill="black", font=f)
    d.text((38, 117), "+", fill="black", font=f)
    # wires
    d.line([70, 120, 120, 120], fill="black", width=3)
    d.line([200, 120, 380, 120], fill="black", width=3)
    d.line([400, 120, 470, 120], fill="black", width=3)
    # bottom rail (ground)
    d.line([45, 150, 45, 230], fill="black", width=3)
    d.line([470, 120, 470, 230], fill="black", width=3)
    d.line([45, 230, 470, 230], fill="black", width=3)
    # ground symbol
    d.line([245, 230, 285, 230], fill="black", width=3)
    d.line([255, 240, 275, 240], fill="black", width=3)
    d.line([262, 250, 268, 250], fill="black", width=3)
    d.text((220, 255), "GND", fill="black", font=f)
    d.text((10, 10), "RC Low-Pass Filter", fill="black", font=_font(20))
    return img


def make_truss() -> Image.Image:
    img = Image.new("RGB", (600, 360), "white")
    d = ImageDraw.Draw(img)
    f = _font(14)
    # 5 nodes
    nodes = {
        "A": (60, 280),
        "B": (180, 100),
        "C": (300, 280),
        "D": (420, 100),
        "E": (540, 280),
    }
    # members
    members = [
        ("A", "B"), ("B", "C"), ("A", "C"),
        ("C", "D"), ("B", "D"),
        ("D", "E"), ("C", "E"),
    ]
    for a, b in members:
        d.line([nodes[a], nodes[b]], fill="black", width=3)
    for name, (x, y) in nodes.items():
        d.ellipse([x - 7, y - 7, x + 7, y + 7], outline="black", fill="white", width=2)
        d.text((x + 8, y - 18), name, fill="black", font=f)
    # supports
    d.polygon([(45, 295), (75, 295), (60, 320)], outline="black")
    d.polygon([(525, 295), (555, 295), (540, 320)], outline="black")
    # load arrow on B
    d.line([(180, 50), (180, 95)], fill="black", width=3)
    d.polygon([(175, 88), (185, 88), (180, 100)], fill="black")
    d.text((190, 50), "P = 5 kN", fill="black", font=f)
    d.text((10, 10), "Simple Planar Truss", fill="black", font=_font(20))
    return img


def make_block_diagram() -> Image.Image:
    img = Image.new("RGB", (700, 240), "white")
    d = ImageDraw.Draw(img)
    f = _font(16)
    boxes = [
        ("Input", 40, 90, 160, 150),
        ("Plant", 230, 90, 360, 150),
        ("Sensor", 430, 90, 560, 150),
    ]
    for label, x0, y0, x1, y1 in boxes:
        d.rectangle([x0, y0, x1, y1], outline="black", width=3)
        d.text((x0 + 20, (y0 + y1) // 2 - 10), label, fill="black", font=f)
    # arrows
    def arrow(x1, y, x2):
        d.line([(x1, y), (x2 - 10, y)], fill="black", width=3)
        d.polygon([(x2 - 10, y - 6), (x2 - 10, y + 6), (x2, y)], fill="black")

    arrow(160, 120, 230)
    arrow(360, 120, 430)
    # feedback
    d.line([(560, 120), (590, 120)], fill="black", width=3)
    d.line([(590, 120), (590, 200)], fill="black", width=3)
    d.line([(590, 200), (40, 200)], fill="black", width=3)
    d.line([(40, 200), (40, 130)], fill="black", width=3)
    d.polygon([(34, 130), (46, 130), (40, 120)], fill="black")
    d.text((10, 10), "Closed-Loop Control Block Diagram", fill="black", font=_font(20))
    return img


def make_plot() -> Image.Image:
    import math

    img = Image.new("RGB", (640, 360), "white")
    d = ImageDraw.Draw(img)
    f = _font(14)
    # axes
    ox, oy = 70, 300
    d.line([(ox, oy), (600, oy)], fill="black", width=2)
    d.line([(ox, oy), (ox, 40)], fill="black", width=2)
    d.text((280, 320), "t (s)", fill="black", font=f)
    d.text((20, 150), "V", fill="black", font=f)
    # series: 1 - exp(-t/tau)
    tau = 1.0
    pts = []
    for i in range(0, 200):
        t = i / 40.0
        v = 1 - math.exp(-t / tau)
        x = ox + i * 2.5
        y = oy - v * 230
        pts.append((x, y))
    for a, b in zip(pts, pts[1:]):
        d.line([a, b], fill="black", width=2)
    d.text((10, 10), "Step Response: 1 - exp(-t/tau)", fill="black", font=_font(18))
    return img


def make_handdrawn_circuit() -> Image.Image:
    """Synthesize a hand-drawn-looking RC circuit on a slightly noisy paper background."""
    import random

    random.seed(7)
    img = Image.new("RGB", (640, 360), (250, 247, 235))  # paper-cream background
    d = ImageDraw.Draw(img)

    def jitter_line(p0, p1, width=4, segments=14, jitter=2.2):
        x0, y0 = p0
        x1, y1 = p1
        pts = [(x0, y0)]
        for i in range(1, segments):
            t = i / segments
            jx = random.uniform(-jitter, jitter)
            jy = random.uniform(-jitter, jitter)
            pts.append((x0 + (x1 - x0) * t + jx, y0 + (y1 - y0) * t + jy))
        pts.append((x1, y1))
        d.line(pts, fill=(35, 35, 35), width=width)

    def jitter_rect(x0, y0, x1, y1):
        jitter_line((x0, y0), (x1, y0))
        jitter_line((x1, y0), (x1, y1))
        jitter_line((x1, y1), (x0, y1))
        jitter_line((x0, y1), (x0, y0))

    # resistor (zig-zag)
    zigs_x = [180, 200, 220, 240, 260, 280]
    pts = [(zigs_x[0], 150)]
    for i, x in enumerate(zigs_x[1:]):
        pts.append((x, 130 if i % 2 == 0 else 170))
    pts.append((300, 150))
    for a, b in zip(pts, pts[1:]):
        jitter_line(a, b, jitter=1.5)

    # capacitor (parallel plates)
    jitter_line((420, 110), (420, 190), jitter=1.5)
    jitter_line((445, 110), (445, 190), jitter=1.5)

    # wires
    jitter_line((50, 150), (180, 150))
    jitter_line((300, 150), (420, 150))
    jitter_line((445, 150), (560, 150))
    # bottom rail (ground path)
    jitter_line((50, 150), (50, 270))
    jitter_line((50, 270), (560, 270))
    jitter_line((560, 150), (560, 270))

    # voltage source on the left (circle)
    d.ellipse([28, 130, 72, 170], outline=(35, 35, 35), width=3)
    d.text((42, 138), "Vs", fill=(35, 35, 35), font=_font(16))

    # ground symbol
    jitter_line((280, 270), (320, 270))
    jitter_line((290, 282), (310, 282))
    jitter_line((297, 294), (303, 294))

    # labels
    d.text((205, 95), "R = 10kΩ", fill=(35, 35, 35), font=_font(16))
    d.text((415, 85), "C = 1µF", fill=(35, 35, 35), font=_font(16))
    d.text((275, 300), "GND", fill=(35, 35, 35), font=_font(14))
    d.text((20, 20), "RC filter (hand-drawn)", fill=(35, 35, 35), font=_font(18))

    return img


def main() -> None:
    HERE.mkdir(exist_ok=True)
    out = {
        "electrical_rc_circuit.png": make_rc_circuit(),
        "truss_diagram.png": make_truss(),
        "block_diagram.png": make_block_diagram(),
        "step_response_plot.png": make_plot(),
        "handdrawn_rc_circuit.png": make_handdrawn_circuit(),
    }
    for name, img in out.items():
        img.save(HERE / name)
        print(f"wrote {HERE / name}")


if __name__ == "__main__":
    main()
