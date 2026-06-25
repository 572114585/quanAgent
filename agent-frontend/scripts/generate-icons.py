"""
Generate placeholder Tauri 2 icons (PNG + ICO + ICNS stub).
Replace icons/icon.png with your real artwork, then re-run this script.
"""
from PIL import Image, ImageDraw
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src-tauri" / "icons"
OUT.mkdir(parents=True, exist_ok=True)

SIZE = 1024


def draw_icon() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Rounded square background with a subtle gradient feel (two layers)
    radius = 220
    d.rounded_rectangle((0, 0, SIZE, SIZE), radius=radius, fill=(59, 130, 246, 255))
    d.rounded_rectangle(
        (40, 40, SIZE - 40, SIZE - 40),
        radius=radius - 40,
        fill=(96, 165, 250, 255),
    )
    # Letter "A"
    d.text((SIZE * 0.32, SIZE * 0.22), "A", fill=(255, 255, 255, 255))
    return img


def main() -> None:
    base = draw_icon()
    png_files = {
        "32x32.png": 32,
        "128x128.png": 128,
        "128x128@2x.png": 256,
        "icon.png": SIZE,
    }
    for name, size in png_files.items():
        base.resize((size, size), Image.LANCZOS).save(OUT / name, "PNG")
    # Windows .ico
    base.resize((256, 256), Image.LANCZOS).save(OUT / "icon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    # macOS .icns (best-effort; Tauri can fall back to PNGs)
    try:
        base.resize((512, 512), Image.LANCZOS).save(OUT / "icon.icns", format="ICNS")
    except Exception:
        # Pillow may not have ICNS support on all builds — copy PNG as fallback
        base.resize((512, 512), Image.LANCZOS).save(OUT / "icon.icns", "PNG")
    print("Generated icons in", OUT)


if __name__ == "__main__":
    main()
