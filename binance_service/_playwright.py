from __future__ import annotations

import logging
import os
import signal
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Browser
from playwright.sync_api import Page, ViewportSize
from playwright.sync_api import sync_playwright

from binance_service._config import AppConfig

logger = logging.getLogger("playwright")


@contextmanager
def connect_browser(
    config: AppConfig,
    headless: bool = False,
    window_width: int | None = None,
    window_height: int | None = None,
) -> Iterator[Browser]:
    if headless:
        with _launch_headless_browser(config, window_width, window_height) as browser:
            yield browser
    else:
        with _connect_cdp_browser(config, window_width, window_height) as browser:
            yield browser


@contextmanager
def _connect_cdp_browser(
    config: AppConfig,
    window_width: int | None = None,
    window_height: int | None = None,
) -> Iterator[Browser]:
    """Connect to an existing Chrome instance via CDP (headed mode)."""
    from binance_service._chrome import ensure_debug_chrome_running

    ensure_debug_chrome_running(
        config=config,
        headless=False,
        window_width=window_width,
        window_height=window_height,
    )
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(config.chrome.debug_url)
        try:
            yield browser
        finally:
            browser.close()


@contextmanager
def _launch_headless_browser(
    config: AppConfig,
    window_width: int | None = None,
    window_height: int | None = None,
) -> Iterator[Browser]:
    """Launch Chrome via Playwright's persistent context (headless mode)."""
    chrome_path = Path(config.chrome.bin_path)
    if not chrome_path.exists():
        raise FileNotFoundError(f"Chrome not found: {chrome_path}")

    win_w = window_width or 1280
    win_h = window_height or 720

    # If headed Chrome is already running on the CDP port, kill it first
    # to avoid user data dir lock conflict
    _stop_existing_chrome(config)

    logger.info("Launching headless Chrome via persistent context (window=%dx%d)", win_w, win_h)

    with sync_playwright() as pw:
        vp: ViewportSize = {"width": win_w, "height": win_h}
        context = pw.chromium.launch_persistent_context(
            user_data_dir=config.chrome.user_data_dir,
            headless=True,
            executable_path=config.chrome.bin_path,
            args=["--no-first-run", "--no-default-browser-check"],
            viewport=vp,
            device_scale_factor=2,
        )
        browser = context.browser
        assert browser is not None, "launch_persistent_context did not return a Browser"
        try:
            yield browser
        finally:
            context.close()


def _stop_existing_chrome(config: AppConfig) -> None:
    """Kill any Chrome process holding the user data dir lock."""
    from binance_service._chrome import is_cdp_ready

    if not is_cdp_ready(config):
        return  # No Chrome running on the CDP port, nothing to stop

    logger.warning(
        "Headed Chrome is running on %s, stopping it to avoid user data dir lock conflict",
        config.chrome.debug_url,
    )
    try:
        # Find the Chrome process using the CDP port
        result = subprocess.run(
            ["lsof", "-ti", f"-iTCP:{config.chrome.debug_port}", "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=5,
        )
        pids = [int(pid) for pid in result.stdout.strip().split() if pid]
        for pid in pids:
            os.kill(pid, signal.SIGTERM)
        if pids:
            logger.info("Sent SIGTERM to Chrome PID(s): %s", pids)
    except (subprocess.TimeoutExpired, OSError, ValueError):
        logger.warning("Failed to stop existing Chrome, proceeding anyway")


def get_or_create_page(browser: Browser, target_url: str, timeout: int) -> Page:
    for context in browser.contexts:
        for page in context.pages:
            if page.url == target_url:
                logger.info("Reusing existing tab: %s", page.url)
                return page

    vp: ViewportSize = {"width": 430, "height": 932}
    context = browser.contexts[0] if browser.contexts else browser.new_context(
        viewport=vp,
        device_scale_factor=2,
    )
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
