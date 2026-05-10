from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .materials import MATERIALS


APP_DIR = Path.home() / "Documents" / "LockHeart_Bulksale"
CONFIG_PATH = APP_DIR / "settings.json"
BASE_WIDTH = 1920
BASE_HEIGHT = 1080


@dataclass
class Point:
    x: int
    y: int


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass
class ClickMap:
    bag_region: Rect = field(default_factory=lambda: Rect(1080, 340, 820, 720))
    listing_region: Rect = field(default_factory=lambda: Rect(70, 390, 1040, 680))
    price_text: Point = field(default_factory=lambda: Point(1128, 673))
    price_minus: Point = field(default_factory=lambda: Point(1038, 673))
    price_plus: Point = field(default_factory=lambda: Point(1217, 673))
    keypad_confirm: Point = field(default_factory=lambda: Point(1028, 638))
    keypad_backspace: Point = field(default_factory=lambda: Point(1028, 480))
    keypad_0: Point = field(default_factory=lambda: Point(849, 753))
    keypad_1: Point = field(default_factory=lambda: Point(758, 480))
    keypad_2: Point = field(default_factory=lambda: Point(849, 480))
    keypad_3: Point = field(default_factory=lambda: Point(939, 480))
    keypad_4: Point = field(default_factory=lambda: Point(758, 573))
    keypad_5: Point = field(default_factory=lambda: Point(849, 573))
    keypad_6: Point = field(default_factory=lambda: Point(939, 573))
    keypad_7: Point = field(default_factory=lambda: Point(758, 666))
    keypad_8: Point = field(default_factory=lambda: Point(849, 666))
    keypad_9: Point = field(default_factory=lambda: Point(939, 666))
    keypad_probe: Point = field(default_factory=lambda: Point(1094, 743))
    sell_button_probe: Point = field(default_factory=lambda: Point(1015, 944))
    sell_confirm: Point = field(default_factory=lambda: Point(1015, 944))
    remove_confirm: Point = field(default_factory=lambda: Point(1015, 944))
    close_dialog: Point = field(default_factory=lambda: Point(1190, 30))
    scroll_anchor: Point = field(default_factory=lambda: Point(1040, 850))
    listing_scroll_anchor: Point = field(default_factory=lambda: Point(1040, 850))
    bag_scroll_anchor: Point = field(default_factory=lambda: Point(1780, 850))


@dataclass
class AppSettings:
    window_title_keyword: str = "幻塔"
    match_threshold: float = 0.74
    action_interval: float = 0.25
    dry_run: bool = False
    selected_prices: dict[str, int] = field(
        default_factory=lambda: {item.slug: item.default_price for item in MATERIALS}
    )
    selected_enabled: dict[str, bool] = field(
        default_factory=lambda: {item.slug: True for item in MATERIALS}
    )
    click_map: ClickMap = field(default_factory=ClickMap)


def load_settings() -> AppSettings:
    if not CONFIG_PATH.exists():
        return AppSettings()
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    click_raw = raw.get("click_map", {}) if raw.get("automation_schema_version") == 2 else {}
    defaults_map = ClickMap()
    click_map = ClickMap(
        bag_region=Rect(**click_raw.get("bag_region", asdict(ClickMap().bag_region))),
        listing_region=Rect(**click_raw.get("listing_region", asdict(ClickMap().listing_region))),
        price_text=Point(**click_raw.get("price_text", asdict(ClickMap().price_text))),
        price_minus=Point(**click_raw.get("price_minus", asdict(ClickMap().price_minus))),
        price_plus=Point(**click_raw.get("price_plus", asdict(ClickMap().price_plus))),
        keypad_confirm=Point(**click_raw.get("keypad_confirm", asdict(ClickMap().keypad_confirm))),
        keypad_backspace=Point(**click_raw.get("keypad_backspace", asdict(ClickMap().keypad_backspace))),
        keypad_0=Point(**click_raw.get("keypad_0", asdict(ClickMap().keypad_0))),
        keypad_1=Point(**click_raw.get("keypad_1", asdict(ClickMap().keypad_1))),
        keypad_2=Point(**click_raw.get("keypad_2", asdict(ClickMap().keypad_2))),
        keypad_3=Point(**click_raw.get("keypad_3", asdict(ClickMap().keypad_3))),
        keypad_4=Point(**click_raw.get("keypad_4", asdict(ClickMap().keypad_4))),
        keypad_5=Point(**click_raw.get("keypad_5", asdict(ClickMap().keypad_5))),
        keypad_6=Point(**click_raw.get("keypad_6", asdict(ClickMap().keypad_6))),
        keypad_7=Point(**click_raw.get("keypad_7", asdict(ClickMap().keypad_7))),
        keypad_8=Point(**click_raw.get("keypad_8", asdict(ClickMap().keypad_8))),
        keypad_9=Point(**click_raw.get("keypad_9", asdict(ClickMap().keypad_9))),
        keypad_probe=Point(**click_raw.get("keypad_probe", asdict(ClickMap().keypad_probe))),
        sell_button_probe=Point(**click_raw.get("sell_button_probe", asdict(ClickMap().sell_button_probe))),
        sell_confirm=Point(**click_raw.get("sell_confirm", asdict(ClickMap().sell_confirm))),
        remove_confirm=Point(**click_raw.get("remove_confirm", asdict(ClickMap().remove_confirm))),
        close_dialog=Point(**click_raw.get("close_dialog", asdict(ClickMap().close_dialog))),
        scroll_anchor=Point(**click_raw.get("scroll_anchor", asdict(ClickMap().scroll_anchor))),
        listing_scroll_anchor=Point(**click_raw.get("listing_scroll_anchor", click_raw.get("scroll_anchor", asdict(ClickMap().listing_scroll_anchor)))),
        bag_scroll_anchor=Point(**click_raw.get("bag_scroll_anchor", asdict(ClickMap().bag_scroll_anchor))),
    )
    if asdict(click_map.bag_region) == {"x": 1120, "y": 430, "w": 760, "h": 630}:
        click_map.bag_region = defaults_map.bag_region
    if asdict(click_map.listing_region) == {"x": 80, "y": 440, "w": 1010, "h": 620}:
        click_map.listing_region = defaults_map.listing_region
    defaults = AppSettings()
    defaults.window_title_keyword = raw.get("window_title_keyword", defaults.window_title_keyword)
    defaults.match_threshold = float(raw.get("match_threshold", defaults.match_threshold))
    defaults.action_interval = float(raw.get("action_interval", defaults.action_interval))
    if raw.get("price_schema_version") == 2:
        defaults.dry_run = bool(raw.get("dry_run", defaults.dry_run))
    saved_prices = raw.get("selected_prices", {})
    if raw.get("price_schema_version") == 2:
        defaults.selected_prices.update(saved_prices)
    defaults.selected_enabled.update(raw.get("selected_enabled", {}))
    defaults.click_map = click_map
    return defaults


def save_settings(settings: AppSettings) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(
            {**asdict(settings), "price_schema_version": 2, "automation_schema_version": 2},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
