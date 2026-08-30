from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "presentation" / "resources" / "smshks.ico"


def build_icon():
    size = 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Rounded blue app tile.
    draw.rounded_rectangle((4, 4, 252, 252), radius=44, fill=(24, 126, 232, 255))

    # Phone body and screen.
    draw.rounded_rectangle((63, 27, 178, 230), radius=20, fill=(248, 250, 252, 255))
    draw.rounded_rectangle((72, 49, 169, 204), radius=12, fill=(5, 74, 178, 255))
    draw.rounded_rectangle((105, 37, 137, 42), radius=3, fill=(6, 57, 128, 255))
    draw.rounded_rectangle((112, 212, 137, 222), radius=5, fill=(5, 74, 178, 255))

    # Message bubble.
    draw.ellipse((157, 52, 233, 128), fill=(250, 250, 250, 255))
    draw.polygon([(174, 118), (166, 142), (190, 126)], fill=(250, 250, 250, 255))
    for x in (180, 198, 216):
        draw.ellipse((x - 5, 86, x + 5, 96), fill=(18, 105, 210, 255))

    # HKS lettering. Use a bold system font when available; fall back safely.
    font = None
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            font = ImageFont.truetype(str(candidate), 55)
            break
    if font is None:
        font = ImageFont.load_default()

    text = "HKS"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    draw.text(((121 - text_w / 2), (135 - text_h / 2)), text, font=font, fill=(255, 255, 255, 255))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        OUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Built {OUT}")


if __name__ == "__main__":
    build_icon()
