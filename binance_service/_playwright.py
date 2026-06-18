from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import Browser
from playwright.sync_api import Page
from playwright.sync_api import sync_playwright

from binance_service._chrome import ensure_debug_chrome_running
from binance_service._config import AppConfig

logger = logging.getLogger("playwright")


@contextmanager
def connect_browser(
    config: AppConfig,
    headless: bool = False,
    window_width: int | None = None,
    window_height: int | None = None,
) -> Iterator[Browser]:
    ensure_debug_chrome_running(
        config=config,
        headless=headless,
        window_width=window_width,
        window_height=window_height,
    )
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(config.chrome.debug_url)
        try:
            yield browser
        finally:
            browser.close()


def get_or_create_page(browser: Browser, target_url: str) -> Page:
    for context in browser.contexts:
        for page in context.pages:
            if page.url == target_url:
                logger.info("Reusing existing tab: %s", page.url)
                return page

    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()
    page.goto(target_url, wait_until="networkidle")
    logger.info("Opened new tab: %s", page.url)
    return page


def ensure_logged_in(page: Page, login_url_indicator: str = "/login") -> None:
    if login_url_indicator in page.url:
        raise RuntimeError(
            f"Not logged in (URL contains '{login_url_indicator}'). "
            "Please log in first in headed mode."
        )
