from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Browser
from playwright.sync_api import Page, ViewportSize
from playwright.sync_api import sync_playwright

from binance_service._chrome import check_user_data_dir_available
from binance_service._chrome import ensure_cdp_chrome_running
from binance_service._config import AppConfig

logger = logging.getLogger("playwright")


@contextmanager
def connect_browser(config: AppConfig, headless: bool = False) -> Iterator[Browser]:
    if headless:
        with _launch_headless_browser(config) as browser:
            yield browser
    else:
        with _connect_cdp_browser(config) as browser:
            yield browser


@contextmanager
def _connect_cdp_browser(config: AppConfig) -> Iterator[Browser]:
    """Connect to an existing Chrome instance via CDP (headed mode)."""
    ensure_cdp_chrome_running(config=config)
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(config.chrome.debug_url)
        try:
            yield browser
        finally:
            browser.close()


@contextmanager
def _launch_headless_browser(config: AppConfig) -> Iterator[Browser]:
    """Launch Chrome via Playwright's persistent context (headless mode)."""
    chrome_path = Path(config.chrome.bin_path)
    if not chrome_path.exists():
        raise FileNotFoundError(f"Chrome not found: {chrome_path}")

    # Ensure no headed Chrome is holding the user data dir lock
    check_user_data_dir_available(config)

    w = config.window.width
    h = config.window.height
    vp: ViewportSize = {"width": w, "height": h}
    logger.info("Launching headless Chrome via persistent context (window=%dx%d)", w, h)

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=config.chrome.user_data_dir,
            headless=True,
            executable_path=config.chrome.bin_path,
            args=["--no-first-run", "--no-default-browser-check"],
            record_video_size=vp,
            device_scale_factor=2,
        )
        browser = context.browser
        assert browser is not None, "launch_persistent_context did not return a Browser"
        try:
            yield browser
        finally:
            context.close()


def get_or_create_page(browser: Browser, target_url: str, timeout: int) -> Page:
    for context in browser.contexts:
        for page in context.pages:
            if page.url == target_url:
                logger.info("Reusing existing tab: %s", page.url)
                return page

    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()
    page.goto(target_url, wait_until="load", timeout=timeout)
    logger.info("Opened new tab: %s", page.url)
    return page


def ensure_logged_in(page: Page, login_url_indicator: str = "/login") -> None:
    if login_url_indicator in page.url:
        raise RuntimeError(
            f"Not logged in (URL contains '{login_url_indicator}'). "
            "Please log in first in headed mode."
        )
