from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "reference" / "IMG_6973.PNG"
OUT_ICO = ROOT / "assets" / "app_icon.ico"
OUT_PREVIEW = ROOT / "assets" / "app_icon_preview.png"


def main() -> None:
    OUT_ICO.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(SOURCE).convert("RGBA")
    # Crop around the character face and hair, then letterbox into a square icon.
    crop = image.crop((70, 0, 840, 770))
    crop = ImageOps.fit(crop, (1024, 1024), method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
    crop.save(OUT_PREVIEW)
    crop.save(OUT_ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
