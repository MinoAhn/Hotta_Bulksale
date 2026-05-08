from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "reference" / "8_material.png"
BAG_SOURCE = ROOT / "assets" / "reference" / "img_2.png"
OUT = ROOT / "assets" / "materials"

CARD_SLOTS = [
    ("medicine_bone", (344, 47, 434, 137)),
    ("gold_ring", (844, 47, 934, 137)),
    ("scale", (344, 214, 434, 304)),
    ("fang", (844, 214, 934, 304)),
    ("fur", (344, 381, 434, 471)),
    ("oil", (844, 381, 934, 471)),
    ("stone", (344, 548, 434, 636)),
    ("marrow", (844, 548, 934, 636)),
]

BAG_SLOTS = [
    ("gold_ring", (1175, 475, 1265, 565)),
    ("scale", (1315, 475, 1405, 565)),
    ("fang", (1455, 475, 1545, 565)),
    ("fur", (1595, 475, 1685, 565)),
    ("oil", (1735, 475, 1825, 565)),
    ("stone", (1175, 635, 1265, 725)),
    ("marrow", (1315, 635, 1405, 725)),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    card_image = Image.open(SOURCE).convert("RGBA")
    for name, box in CARD_SLOTS:
        crop = card_image.crop(box)
        crop.save(OUT / f"{name}.png")
        crop.save(OUT / f"{name}_card.png")

    if BAG_SOURCE.exists():
        bag_image = Image.open(BAG_SOURCE).convert("RGBA")
        for name, box in BAG_SLOTS:
            crop = bag_image.crop(box)
            crop.save(OUT / f"{name}_bag.png")

    # The medicine bone is not visible in the provided bag screenshot. A tighter
    # card crop gives the matcher a usable fallback until a live screenshot exists.
    medicine_bone = card_image.crop((370, 62, 424, 126))
    medicine_bone.save(OUT / "medicine_bone_bag.png")


if __name__ == "__main__":
    main()
