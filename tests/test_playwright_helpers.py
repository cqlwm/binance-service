"""binance_service._playwright 的 get_or_create_page 单元测试。

不依赖真实 Chrome/Playwright，用 MagicMock 模拟 Browser/Page，
仅验证 callback 调用语义（何时调用、是否控制导航时序）。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from binance_service._playwright import get_or_create_page

if TYPE_CHECKING:
    from playwright.sync_api import Page


def _make_browser_with_existing_tab(target_url: str) -> MagicMock:
    """构造一个已存在匹配 URL tab 的 mock Browser。"""
    existing_page = MagicMock()
    existing_page.url = target_url
    context = MagicMock()
    context.pages = [existing_page]
    browser = MagicMock()
    browser.contexts = [context]
    return browser


def _make_browser_without_tabs() -> MagicMock:
    """构造一个无 tab 的 mock Browser，new_page 返回可追踪的 mock page。"""
    new_page = MagicMock()
    new_page.url = "about:blank"
    context = MagicMock()
    context.pages = []
    context.new_page.return_value = new_page
    browser = MagicMock()
    browser.contexts = [context]
    return browser


def test_get_or_create_page_reuses_existing_tab_skips_callback() -> None:
    """复用已存在 tab 时应跳过 callback（tab 已稳定，无需再等接口）。"""
    target_url = "https://www.binance.com/zh-CN/futures/SOXSUSDT"
    browser = _make_browser_with_existing_tab(target_url)

    def _explode(page: Page, navigate: Callable[[], None]) -> None:
        raise AssertionError("复用 tab 时不应调用 callback")

    # 不抛异常即通过：callback 未被调用
    page = get_or_create_page(browser, target_url, callback=_explode)
    assert page is not None


def test_get_or_create_page_new_tab_calls_callback_with_navigate() -> None:
    """新开 tab 时应调用 callback，且 navigate 在 callback 内触发 goto。"""
    target_url = "https://www.binance.com/zh-CN/futures/SOXSUSDT"
    browser = _make_browser_without_tabs()

    received: list[tuple[object, Callable[[], None]]] = []

    def _capture(page: Page, navigate: Callable[[], None]) -> None:
        received.append((page, navigate))
        # 调用 navigate，应触发 page.goto
        navigate()

    page = get_or_create_page(browser, target_url, timeout=5000, callback=_capture)

    # callback 被调用一次，收到 page 与 navigate
    assert len(received) == 1
    received_page, received_navigate = received[0]
    assert received_page is page
    # navigate 触发了 goto，且超时透传
    received_page.goto.assert_called_once_with(target_url, wait_until="domcontentloaded", timeout=5000)


def test_get_or_create_page_new_tab_without_callback_navigates() -> None:
    """不传 callback 时应直接 goto，保持向后兼容。"""
    target_url = "https://www.binance.com/zh-CN/futures/SOXSUSDT"
    browser = _make_browser_without_tabs()

    page = get_or_create_page(browser, target_url, timeout=3000)

    page.goto.assert_called_once_with(target_url, wait_until="domcontentloaded", timeout=3000)
