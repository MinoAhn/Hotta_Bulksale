from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


def resource_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled)
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = resource_root()
ASSET_DIR = PROJECT_ROOT / "assets" / "materials"


@dataclass(frozen=True)
class Material:
    slug: str
    name: str
    default_price: int
    icon_file: str

    @property
    def icon_path(self) -> Path:
        return ASSET_DIR / self.icon_file


MATERIALS: tuple[Material, ...] = (
    Material("medicine_bone", "药用兽骨", 20, "medicine_bone.png"),
    Material("gold_ring", "无主金戒指", 20, "gold_ring.png"),
    Material("scale", "溢彩鳞片", 20, "scale.png"),
    Material("fang", "完整的兽牙", 20, "fang.png"),
    Material("fur", "整块皮毛", 20, "fur.png"),
    Material("oil", "异香油脂", 20, "oil.png"),
    Material("stone", "小块结石", 20, "stone.png"),
    Material("marrow", "新鲜兽髓", 20, "marrow.png"),
)


MATERIAL_BY_SLUG = {item.slug: item for item in MATERIALS}
