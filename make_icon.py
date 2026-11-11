"""Generates crusher.ico (and crusher.png): a hydraulic press squashing a film strip."""
from pathlib import Path

from PIL import Image, ImageDraw

S = 1024
HERE = Path(__file__).resolve().parent


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def build() -> Image.Image:
    # gradient background inside a rounded square
    grad = Image.new("RGB", (S, S))
    top, bot = (255, 138, 36), (226, 34, 52)
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        gd.line([(0, y), (S, y)], fill=lerp(top, bot, y / S))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([24, 24, S - 24, S - 24], radius=220, fill=255)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)

    white = (255, 255, 255, 255)
    dark = (30, 27, 46, 255)
    shadow = (120, 10, 20, 90)

    # piston rod + top press plate
    d.rounded_rectangle([442, 70, 582, 330], radius=24, fill=white)
    d.rounded_rectangle([150, 300, 874, 410], radius=34, fill=white)
    # squashed film strip (bulging wider than the plates)
    d.rounded_rectangle([120, 452, 904, 612], radius=40, fill=shadow)
    d.rounded_rectangle([110, 436, 914, 596], radius=40, fill=dark)
    for x in range(170, 880, 92):          # sprocket holes
        d.rounded_rectangle([x, 456, x + 46, 484], radius=8, fill=(255, 190, 90, 255))
        d.rounded_rectangle([x, 548, x + 46, 576], radius=8, fill=(255, 190, 90, 255))
    d.polygon([(470, 492), (470, 540), (560, 516)], fill=(255, 120, 60, 255))  # flattened play
    # base plate
    d.rounded_rectangle([150, 624, 874, 734], radius=34, fill=white)
    d.rounded_rectangle([300, 734, 724, 880], radius=24, fill=(255, 255, 255, 215))
    # impact lines
    for (x0, y0, x1, y1) in [(92, 380, 40, 330), (70, 516, 10, 516), (92, 652, 40, 702),
                             (932, 380, 984, 330), (954, 516, 1014, 516), (932, 652, 984, 702)]:
        d.line([(x0, y0), (x1, y1)], fill=white, width=26)
    # clip impact lines to the rounded square
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


if __name__ == "__main__":
    big = build()
    big.resize((256, 256), Image.LANCZOS).save(HERE / "crusher.png")
    big.save(HERE / "crusher.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                          (64, 64), (128, 128), (256, 256)])
    print("wrote crusher.ico / crusher.png")
