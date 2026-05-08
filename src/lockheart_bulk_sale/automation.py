from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

import keyboard
import pyautogui
import pygetwindow as gw

from .config import AppSettings, Point
from .materials import MATERIAL_BY_SLUG, MATERIALS
from .vision import Match, VisionEngine, pil_to_bgr


LogFn = Callable[[str], None]


@dataclass(frozen=True)
class JobItem:
    slug: str
    price: int


class StopRequested(RuntimeError):
    pass


class GameAutomation:
    def __init__(self, settings: AppSettings, log: LogFn) -> None:
        self.settings = settings
        self.log = log
        self.stop_event = threading.Event()
        self.vision = VisionEngine(MATERIALS, threshold=settings.match_threshold)

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
                self.log(f"找到背包物品: {material.name}，置信度 {match.confidence:.2f}，坐标 {match.center}")
                self._click(match.center, f"选择 {material.name}")
                self._wait_for_sell_page()
                self._set_price(job.price)
                self._wait_for_sell_page()
                self._click_point(self.settings.click_map.sell_confirm, f"点击上架 {material.name} / {job.price}")
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
            self.log(f"找到待下架商品: {material.name}，置信度 {found.confidence:.2f}，坐标 {found.center}")
            self._click(found.center, f"打开 {material.name} 下架弹窗")
            self._sleep(0.45)
            self._click_point(self.settings.click_map.remove_confirm, f"下架 {material.name}")
            self._sleep(1.0)
            removed_total += 1
            self.log(f"完成一次下架: {material.name}，累计 {removed_total}。")
        self.log(f"下架任务结束，累计下架 {removed_total} 次。")

    def scan(self) -> tuple[list[Match], list[Match]]:
        screenshot = pil_to_bgr(pyautogui.screenshot())
        bag = self.vision.find_materials(screenshot, self.settings.click_map.bag_region)
        listing = self.vision.find_materials(screenshot, self.settings.click_map.listing_region)
        return bag, listing

    def _find_in_bag(self, slug: str) -> Match | None:
        screenshot = pil_to_bgr(pyautogui.screenshot())
        return self.vision.find_best(screenshot, self.settings.click_map.bag_region, MATERIAL_BY_SLUG[slug])

    def _find_in_listing(self, slug: str) -> Match | None:
        screenshot = pil_to_bgr(pyautogui.screenshot())
        return self.vision.find_best(screenshot, self.settings.click_map.listing_region, MATERIAL_BY_SLUG[slug])

    def _set_price(self, price: int) -> None:
        base_price = 20
        delta = price - base_price
        if delta == 0:
            self.log("目标价格为 20，无需调整价格。")
            return
        button = self.settings.click_map.price_plus if delta > 0 else self.settings.click_map.price_minus
        label = "加号" if delta > 0 else "减号"
        steps = abs(delta)
        self.log(f"价格调整：从默认 {base_price} 调整到 {price}，点击{label} {steps} 次。")
        for index in range(steps):
            self._click_point(button, f"价格{label}调整 {index + 1}/{steps}")
            self._sleep(0.08)
        self._sleep(0.35)

    def _wait_for_keypad(self, timeout: float = 2.0) -> None:
        self._wait_for_blue_probe(self.settings.click_map.keypad_probe, "价格数字键盘", timeout)

    def _wait_for_sell_page(self, timeout: float = 2.0) -> None:
        self._wait_for_blue_probe(self.settings.click_map.sell_button_probe, "上架按钮", timeout)

    def _wait_for_blue_probe(self, point: Point, label: str, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._guard()
            if self._is_blue_at(point):
                self.log(f"已识别到{label}。")
                return
            time.sleep(0.08)
        self.log(f"未明确识别到{label}，继续按默认流程执行。")

    @staticmethod
    def _is_blue_pixel(rgb: tuple[int, int, int]) -> bool:
        red, green, blue = rgb
        return blue > 145 and green > 85 and red < 100

    def _is_blue_at(self, point: Point) -> bool:
        image = pyautogui.screenshot(region=(point.x - 12, point.y - 12, 24, 24))
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
        self._click((point.x, point.y), label)

    def _click(self, xy: tuple[int, int], label: str) -> None:
        self._guard()
        if self.settings.dry_run:
            self.log(f"[Dry-run] {label}: click {xy[0]}, {xy[1]}")
            return
        pyautogui.click(*xy)

    def _scroll_bag(self, clicks: int) -> None:
        self._scroll(clicks * 8, "滚动背包列表", self.settings.click_map.bag_scroll_anchor)
        self._drag(self.settings.click_map.bag_scroll_anchor, 0, -520, "拖动背包列表")

    def _scroll_listing(self, clicks: int) -> None:
        self._scroll(clicks * 4, "滚动上架列表", self.settings.click_map.listing_scroll_anchor)
        self._drag(self.settings.click_map.listing_scroll_anchor, 0, -180, "慢速拖动上架列表", duration=0.75)
        self._sleep(0.55)

    def _scroll(self, clicks: int, label: str, point: Point) -> None:
        self._guard()
        if self.settings.dry_run:
            self.log(f"[Dry-run] {label}: scroll {clicks} @ {point.x}, {point.y}")
            return
        pyautogui.moveTo(point.x, point.y)
        pyautogui.scroll(clicks)

    def _drag(self, point: Point, dx: int, dy: int, label: str, duration: float = 0.35) -> None:
        self._guard()
        if self.settings.dry_run:
            self.log(f"[Dry-run] {label}: drag {dx}, {dy} @ {point.x}, {point.y}")
            return
        pyautogui.moveTo(point.x, point.y)
        pyautogui.dragRel(dx, dy, duration=duration, button="left")

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
