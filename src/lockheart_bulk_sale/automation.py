from __future__ import annotations

import ctypes
import ctypes.wintypes
import threading
import time
from dataclasses import dataclass
from typing import Callable

import cv2
import keyboard
import numpy as np
import pyautogui
import pygetwindow as gw
from PIL import Image

from .config import BASE_HEIGHT, BASE_WIDTH, AppSettings, Point, Rect
from .materials import MATERIAL_BY_SLUG, MATERIALS
from .vision import Match, VisionEngine, pil_to_bgr


LogFn = Callable[[str], None]


@dataclass(frozen=True)
class JobItem:
    slug: str
    price: int


class StopRequested(RuntimeError):
    pass


@dataclass(frozen=True)
class WindowContext:
    left: int
    top: int
    width: int
    height: int

    @property
    def scale(self) -> float:
        return min(self.width / BASE_WIDTH, self.height / BASE_HEIGHT)

    @property
    def content_width(self) -> int:
        return round(BASE_WIDTH * self.scale)

    @property
    def content_height(self) -> int:
        return round(BASE_HEIGHT * self.scale)

    @property
    def content_left(self) -> int:
        return self.left + (self.width - self.content_width) // 2

    @property
    def content_top(self) -> int:
        return self.top + (self.height - self.content_height) // 2

    @property
    def content_offset_x(self) -> int:
        return self.content_left - self.left

    @property
    def content_offset_y(self) -> int:
        return self.content_top - self.top

    def point(self, point: Point) -> tuple[int, int]:
        return (self.content_left + round(point.x * self.scale), self.content_top + round(point.y * self.scale))

    def rect(self, rect: Rect) -> Rect:
        return Rect(
            x=self.content_offset_x + round(rect.x * self.scale),
            y=self.content_offset_y + round(rect.y * self.scale),
            w=max(1, round(rect.w * self.scale)),
            h=max(1, round(rect.h * self.scale)),
        )

    def delta(self, dx: int, dy: int) -> tuple[int, int]:
        return (round(dx * self.scale), round(dy * self.scale))


def _enable_dpi_awareness() -> None:
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class GameAutomation:
    def __init__(self, settings: AppSettings, log: LogFn) -> None:
        _enable_dpi_awareness()
        self.settings = settings
        self.log = log
        self.stop_event = threading.Event()
        self.vision = VisionEngine(MATERIALS, threshold=settings.match_threshold)
        self.window = None
        self.window_context: WindowContext | None = None
        self.last_sell_button: tuple[int, int] | None = None

    def request_stop(self) -> None:
        self.stop_event.set()

    def run_list(self, jobs: list[JobItem]) -> None:
        self.stop_event.clear()
        self._install_hotkey()
        self._activate_game()
        self._check_templates()
        self.log("开始执行上架任务。每次上架后都会重新截图判断，按 Ctrl+Alt+S 可随时停止。")
        for job in jobs:
            material = MATERIAL_BY_SLUG[job.slug]
            sold_count = 0
            self.log(f"开始处理上架材料: {material.name}，目标价格 {job.price}")
            while sold_count < 80:
                self._guard()
                match = self._find_in_bag(material.slug)
                if not match:
                    self.log(f"当前背包页未找到 {material.name}，停止处理该材料。")
                    break
                self.log(f"找到背包物品: {material.name}，置信度 {match.confidence:.2f}，缩放 {match.scale:.2f}，坐标 {match.center}")
                self._click(match.center, f"选择 {material.name}")
                self._wait_for_sell_page(required=True)
                self._set_price(job.price)
                self._wait_for_sell_page(required=True)
                self._click_sell_button(f"点击上架 {material.name} / {job.price}")
                self._sleep(1.05)
                sold_count += 1
                self.log(f"完成一次上架: {material.name} -> {job.price}，累计 {sold_count}。")
            if sold_count == 0:
                self.log(f"{material.name} 未完成上架：背包中未找到或已售罄。")
            else:
                self.log(f"{material.name} 上架循环结束，累计上架 {sold_count} 次。")
        self.log("上架任务结束。")

    def run_remove_selected(self, slugs: list[str]) -> None:
        self.stop_event.clear()
        self._install_hotkey()
        self._activate_game()
        self._check_templates()
        wanted = set(slugs)
        removed_total = 0
        empty_scrolls = 0
        self.log("开始执行下架任务。每次下架后都会重新截图判断。")
        while wanted and removed_total < 120 and empty_scrolls < 8:
            self._guard()
            found_slug = None
            found = None
            for slug in list(wanted):
                candidate = self._find_in_listing(slug)
                if candidate:
                    found_slug = slug
                    found = candidate
                    break
            if not found or not found_slug:
                empty_scrolls += 1
                self.log(f"当前上架页未找到目标商品，滚动上架列表继续查找 ({empty_scrolls}/8)。")
                self._scroll_listing(-5)
                self._sleep(0.5)
                continue
            empty_scrolls = 0
            material = MATERIAL_BY_SLUG[found_slug]
            self.log(f"找到待下架商品: {material.name}，置信度 {found.confidence:.2f}，缩放 {found.scale:.2f}，坐标 {found.center}")
            self._click(found.center, f"打开 {material.name} 下架弹窗")
            self._sleep(0.45)
            self._wait_for_sell_page(required=True)
            self._click_sell_button(f"下架 {material.name}")
            self._sleep(1.0)
            removed_total += 1
            self.log(f"完成一次下架: {material.name}，累计 {removed_total}。")
        self.log(f"下架任务结束，累计下架 {removed_total} 次。")

    def scan(self) -> tuple[list[Match], list[Match]]:
        self._activate_game()
        ctx = self._context()
        screenshot = self._screenshot_game(ctx)
        bag = self._to_screen_matches(self.vision.find_materials(screenshot, ctx.rect(self.settings.click_map.bag_region)), ctx)
        listing = self._to_screen_matches(self.vision.find_materials(screenshot, ctx.rect(self.settings.click_map.listing_region)), ctx)
        return bag, listing

    def _find_in_bag(self, slug: str) -> Match | None:
        ctx = self._context()
        screenshot = self._screenshot_game(ctx)
        match = self.vision.find_best(screenshot, ctx.rect(self.settings.click_map.bag_region), MATERIAL_BY_SLUG[slug])
        return match.offset(ctx.left, ctx.top) if match else None

    def _find_in_listing(self, slug: str) -> Match | None:
        ctx = self._context()
        screenshot = self._screenshot_game(ctx)
        match = self.vision.find_best(screenshot, ctx.rect(self.settings.click_map.listing_region), MATERIAL_BY_SLUG[slug])
        return match.offset(ctx.left, ctx.top) if match else None

    def _set_price(self, price: int) -> None:
        base_price = 20
        delta = price - base_price
        if delta == 0:
            self.log("目标价格为 20，无需调整价格。")
            return
        minus_button, plus_button = self._find_price_step_buttons()
        fallback = self._screen_point(self.settings.click_map.price_plus if delta > 0 else self.settings.click_map.price_minus)
        button = (plus_button if delta > 0 else minus_button) or fallback
        label = "加号" if delta > 0 else "减号"
        steps = abs(delta)
        if plus_button and minus_button:
            self.log(f"价格按钮定位：减号 {minus_button}，加号 {plus_button}。")
        else:
            self.log(f"价格按钮自动定位不完整，使用备用{label}坐标 {button}。")
        self.log(f"价格调整：从默认 {base_price} 调整到 {price}，点击{label} {steps} 次。")
        for index in range(steps):
            self._click(button, f"价格{label}调整 {index + 1}/{steps}")
            self._sleep(0.08)
        self._sleep(0.35)

    def _wait_for_keypad(self, timeout: float = 2.0, required: bool = False) -> bool:
        return self._wait_for_blue_probe(self.settings.click_map.keypad_probe, "价格数字键盘", timeout, required)

    def _wait_for_sell_page(self, timeout: float = 2.0, required: bool = False) -> bool:
        return self._wait_for_blue_probe(self.settings.click_map.sell_button_probe, "上架按钮", timeout, required)

    def _wait_for_blue_probe(self, point: Point, label: str, timeout: float, required: bool) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._guard()
            blue_button = self._find_blue_button()
            if blue_button:
                self.last_sell_button = blue_button
                self.log(f"已识别到{label}: {blue_button}。")
                return True
            if self._is_blue_at(point):
                self.last_sell_button = self._screen_point(point)
                self.log(f"已识别到{label}。")
                return True
            time.sleep(0.08)
        message = f"未明确识别到{label}。"
        if required:
            raise RuntimeError(message + "为防止误点，已停止当前任务。")
        self.log(message)
        return False

    @staticmethod
    def _is_blue_pixel(rgb: tuple[int, int, int]) -> bool:
        red, green, blue = rgb
        return blue > 145 and green > 85 and red < 100

    def _is_blue_at(self, point: Point) -> bool:
        x, y = self._screen_point(point)
        image = pyautogui.screenshot(region=(x - 12, y - 12, 24, 24))
        pixels = image.convert("RGB").getdata()
        blue_count = sum(1 for pixel in pixels if self._is_blue_pixel(pixel))
        return blue_count > 40

    def _clear_game_keypad(self) -> None:
        for _ in range(4):
            self._click_point(self.settings.click_map.keypad_backspace, "清除旧价格")
            self._sleep(0.05)

    def _enter_game_keypad(self, text: str) -> None:
        digits = {
            "0": self.settings.click_map.keypad_0,
            "1": self.settings.click_map.keypad_1,
            "2": self.settings.click_map.keypad_2,
            "3": self.settings.click_map.keypad_3,
            "4": self.settings.click_map.keypad_4,
            "5": self.settings.click_map.keypad_5,
            "6": self.settings.click_map.keypad_6,
            "7": self.settings.click_map.keypad_7,
            "8": self.settings.click_map.keypad_8,
            "9": self.settings.click_map.keypad_9,
        }
        for char in text:
            point = digits.get(char)
            if not point:
                raise RuntimeError(f"价格只能包含数字，收到: {text}")
            self._click_point(point, f"输入价格数字 {char}")
            self._sleep(0.07)

    def _activate_game(self) -> None:
        keyword = self.settings.window_title_keyword.strip()
        windows = [win for win in gw.getAllWindows() if keyword and keyword in win.title]
        if not windows:
            raise RuntimeError(f"找不到标题包含「{keyword}」的游戏窗口。请先打开游戏商店界面。")
        window = windows[0]
        self.log(f"切换到游戏窗口: {window.title}")
        if not self.settings.dry_run:
            window.activate()
        self._sleep(0.6)
        self.window = window
        self.window_context = self._read_window_context(window)
        ctx = self.window_context
        self.log(
            f"游戏客户区: {ctx.left},{ctx.top} {ctx.width}x{ctx.height}；"
            f"16:9内容区 {ctx.content_left},{ctx.content_top} {ctx.content_width}x{ctx.content_height}；"
            f"坐标缩放 x{ctx.scale:.3f}"
        )
        base_ratio = BASE_WIDTH / BASE_HEIGHT
        current_ratio = ctx.width / ctx.height
        if abs(current_ratio - base_ratio) > 0.04:
            self.log("提示：当前游戏窗口比例与基准 16:9 差异较大，建议使用全屏或无边框窗口。")

    def _check_templates(self) -> None:
        missing = self.vision.missing_templates(MATERIALS)
        if missing:
            raise RuntimeError("缺少材料模板: " + "、".join(missing))

    def _install_hotkey(self) -> None:
        try:
            keyboard.add_hotkey("ctrl+alt+s", self.request_stop, suppress=False)
        except Exception as exc:
            self.log(f"全局停止热键注册失败，仍可用 GUI 停止: {exc}")

    def _guard(self) -> None:
        if self.stop_event.is_set():
            raise StopRequested("用户停止任务。")

    def _sleep(self, seconds: float) -> None:
        end = time.monotonic() + max(seconds, self.settings.action_interval)
        while time.monotonic() < end:
            self._guard()
            time.sleep(0.05)

    def _click_point(self, point: Point, label: str) -> None:
        self._click(self._screen_point(point), label)

    def _click(self, xy: tuple[int, int], label: str) -> None:
        self._guard()
        if self.settings.dry_run:
            self.log(f"[Dry-run] {label}: click {xy[0]}, {xy[1]}")
            return
        pyautogui.click(*xy)

    def _click_sell_button(self, label: str) -> None:
        button = self._find_blue_button() or self.last_sell_button or self._screen_point(self.settings.click_map.sell_confirm)
        self._click(button, label)

    def _scroll_bag(self, clicks: int) -> None:
        self._scroll(clicks * 8, "滚动背包列表", self.settings.click_map.bag_scroll_anchor)
        self._drag(self.settings.click_map.bag_scroll_anchor, 0, -520, "拖动背包列表")

    def _scroll_listing(self, clicks: int) -> None:
        self._scroll(clicks * 4, "滚动上架列表", self.settings.click_map.listing_scroll_anchor)
        self._drag(self.settings.click_map.listing_scroll_anchor, 0, -180, "慢速拖动上架列表", duration=0.75)
        self._sleep(0.55)

    def _scroll(self, clicks: int, label: str, point: Point) -> None:
        self._guard()
        x, y = self._screen_point(point)
        if self.settings.dry_run:
            self.log(f"[Dry-run] {label}: scroll {clicks} @ {x}, {y}")
            return
        pyautogui.moveTo(x, y)
        pyautogui.scroll(clicks)

    def _drag(self, point: Point, dx: int, dy: int, label: str, duration: float = 0.35) -> None:
        self._guard()
        x, y = self._screen_point(point)
        scaled_dx, scaled_dy = self._context().delta(dx, dy)
        if self.settings.dry_run:
            self.log(f"[Dry-run] {label}: drag {scaled_dx}, {scaled_dy} @ {x}, {y}")
            return
        pyautogui.moveTo(x, y)
        pyautogui.dragRel(scaled_dx, scaled_dy, duration=duration, button="left")

    def _hotkey(self, *keys: str) -> None:
        self._guard()
        if self.settings.dry_run:
            self.log("[Dry-run] hotkey " + "+".join(keys))
            return
        pyautogui.hotkey(*keys)

    def _write(self, text: str) -> None:
        self._guard()
        if self.settings.dry_run:
            self.log(f"[Dry-run] write {text}")
            return
        pyautogui.write(text, interval=0.02)

    def _context(self) -> WindowContext:
        if self.window_context is None:
            self._activate_game()
        if self.window is not None:
            self.window_context = self._read_window_context(self.window)
        if self.window_context is None:
            raise RuntimeError("无法获取游戏窗口坐标。")
        return self.window_context

    def _screen_point(self, point: Point) -> tuple[int, int]:
        return self._context().point(point)

    def _screenshot_game(self, ctx: WindowContext):
        return pil_to_bgr(pyautogui.screenshot(region=(ctx.left, ctx.top, ctx.width, ctx.height)))

    def _find_blue_button(self) -> tuple[int, int] | None:
        ctx = self._context()
        image = pyautogui.screenshot(region=(ctx.left, ctx.top, ctx.width, ctx.height)).convert("RGB")
        rect = ctx.rect(Rect(760, 740, 560, 260))
        roi = np.array(image.crop((rect.x, rect.y, rect.x + rect.w, rect.y + rect.h)))
        red = roi[:, :, 0]
        green = roi[:, :, 1]
        blue = roi[:, :, 2]
        mask = (blue > 145) & (green > 85) & (red < 110) & ((blue.astype(int) - red.astype(int)) > 70)
        ys, xs = np.where(mask)
        if len(xs) < 250:
            return None
        row_counts = mask.sum(axis=1)
        dense_rows = np.where(row_counts > max(20, row_counts.max() * 0.45))[0]
        if len(dense_rows) < 12:
            return None
        y1, y2 = int(dense_rows.min()), int(dense_rows.max())
        dense_band = mask[y1 : y2 + 1, :]
        col_counts = dense_band.sum(axis=0)
        dense_cols = np.where(col_counts > max(15, col_counts.max() * 0.35))[0]
        if len(dense_cols) < 80:
            return None
        x1, x2 = int(dense_cols.min()), int(dense_cols.max())
        if x2 - x1 < 80 or y2 - y1 < 20:
            return None
        return (ctx.left + rect.x + (x1 + x2) // 2, ctx.top + rect.y + (y1 + y2) // 2)

    def _find_price_step_buttons(self) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
        ctx = self._context()
        image = pyautogui.screenshot(region=(ctx.left, ctx.top, ctx.width, ctx.height)).convert("RGB")
        return self._locate_price_step_buttons(image, ctx)

    @staticmethod
    def _locate_price_step_buttons(image: Image.Image, ctx: WindowContext) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
        rect = ctx.rect(Rect(930, 500, 380, 220))
        roi = np.array(image.crop((rect.x, rect.y, rect.x + rect.w, rect.y + rect.h)))
        red = roi[:, :, 0]
        green = roi[:, :, 1]
        blue = roi[:, :, 2]
        gray = (np.abs(red.astype(int) - green.astype(int)) < 18) & (np.abs(green.astype(int) - blue.astype(int)) < 18)
        dark_button = gray & (red > 80) & (red < 170) & (green > 80) & (green < 170) & (blue > 80) & (blue < 170)
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(dark_button.astype("uint8"), 8)
        centers: list[tuple[int, int]] = []
        for index in range(1, count):
            x, y, w, h, area = stats[index]
            if area < 250 or w < 18 or h < 18 or w > 55 or h > 55:
                continue
            ratio = w / h
            if ratio < 0.65 or ratio > 1.45:
                continue
            cx, cy = centroids[index]
            centers.append((ctx.left + rect.x + round(cx), ctx.top + rect.y + round(cy)))
        if len(centers) < 2:
            return None, None
        centers = sorted(centers, key=lambda point: point[0])
        return centers[0], centers[-1]

    @staticmethod
    def _to_screen_matches(matches: list[Match], ctx: WindowContext) -> list[Match]:
        return [match.offset(ctx.left, ctx.top) for match in matches]

    @staticmethod
    def _read_window_context(window) -> WindowContext:
        hwnd = getattr(window, "_hWnd", None)
        if hwnd:
            rect = ctypes.wintypes.RECT()
            point = ctypes.wintypes.POINT(0, 0)
            if ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect)) and ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(point)):
                width = max(1, rect.right - rect.left)
                height = max(1, rect.bottom - rect.top)
                return WindowContext(point.x, point.y, width, height)
        return WindowContext(window.left, window.top, max(1, window.width), max(1, window.height))
