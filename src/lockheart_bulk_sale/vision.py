from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image

from .config import Rect
from .materials import Material


@dataclass(frozen=True)
class Match:
    slug: str
    name: str
    confidence: float
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


def pil_to_bgr(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def read_bgr(path: Path) -> np.ndarray:
    raw = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"无法读取图片: {path}")
    return img


def crop(image: np.ndarray, rect: Rect) -> np.ndarray:
    return image[rect.y : rect.y + rect.h, rect.x : rect.x + rect.w]


class VisionEngine:
    def __init__(self, materials: Iterable[Material], threshold: float = 0.74) -> None:
        self.threshold = threshold
        self.templates: dict[str, tuple[Material, list[np.ndarray]]] = {}
        for material in materials:
            paths = sorted(material.icon_path.parent.glob(f"{material.slug}*.png"))
            loaded = [read_bgr(path) for path in paths if path.exists()]
            if loaded:
                self.templates[material.slug] = (material, loaded)

    def missing_templates(self, materials: Iterable[Material]) -> list[str]:
        return [item.name for item in materials if item.slug not in self.templates]

    def find_materials(
        self,
        screenshot_bgr: np.ndarray,
        region: Rect,
        slugs: Iterable[str] | None = None,
    ) -> list[Match]:
        roi = crop(screenshot_bgr, region)
        wanted = set(slugs or self.templates.keys())
        matches: list[Match] = []
        for slug, (material, templates) in self.templates.items():
            if slug not in wanted:
                continue
            for template in templates:
                found = self._match_template(roi, template, region, material)
                if found:
                    matches.extend(found)
        return self._dedupe(sorted(matches, key=lambda item: item.confidence, reverse=True))

    def find_best(
        self,
        screenshot_bgr: np.ndarray,
        region: Rect,
        material: Material,
    ) -> Match | None:
        matches = self.find_materials(screenshot_bgr, region, [material.slug])
        return matches[0] if matches else None

    def _match_template(
        self,
        roi: np.ndarray,
        template: np.ndarray,
        region: Rect,
        material: Material,
    ) -> list[Match]:
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(roi_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        points = np.where(result >= self.threshold)
        height, width = template_gray.shape[:2]
        raw = [
            Match(
                slug=material.slug,
                name=material.name,
                confidence=float(result[y, x]),
                x=int(x + region.x),
                y=int(y + region.y),
                width=width,
                height=height,
            )
            for y, x in zip(*points)
        ]
        return self._dedupe(raw)

    @staticmethod
    def _dedupe(matches: list[Match]) -> list[Match]:
        accepted: list[Match] = []
        for match in sorted(matches, key=lambda item: item.confidence, reverse=True):
            mx, my = match.center
            if any(abs(mx - ax) < match.width // 2 and abs(my - ay) < match.height // 2 for ax, ay in (a.center for a in accepted)):
                continue
            accepted.append(match)
        return accepted
