from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from playwright.sync_api import Browser
from playwright.sync_api import BrowserContext
from playwright.sync_api import Page
from playwright.sync_api import sync_playwright

from binance_service._config import AppConfig

logger = logging.getLogger("storage_state")


def restore_storage_state(context: BrowserContext, storage_state_path: str) -> None:
    """Load previously saved cookies / localStorage into the context."""
    path = Path(storage_state_path)
    if not path.exists():
        logger.info("No storage state file found at %s, starting fresh", path)
        return

    try:
        context.set_storage_state(path)
        logger.info("Restored storage state from %s", path)
    except Exception:
        logger.exception("Failed to restore storage state from %s", path)


def save_storage_state(context: BrowserContext, storage_state_path: str) -> None:
    """Dump the current storage state (cookies + localStorage) to a JSON file.

    Creates a backup of the previous file before overwriting, so a bad
    session can be manually recovered from the ``.bak`` file.
    """
    path = Path(storage_state_path)
    try:
        state = context.storage_state()

        # 备份旧文件
        if path.exists():
            bak_path = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(str(path), str(bak_path))

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f)

        logger.info(
            "Saved storage state (%d cookies, %d origins) to %s",
            len(state.get("cookies", [])),
            len(state.get("origins", [])),
            path,
        )
    except Exception:
        logger.exception("Failed to save storage state to %s", path)
        raise


def is_cdp_ready(config: AppConfig) -> bool:
    from urllib.error import URLError
    from urllib.request import urlopen

    try:
        with urlopen(config.chrome.version_url, timeout=1):
            return True
    except (URLError, TimeoutError, OSError):
        return False


def save_storage_state_from_cdp(config: AppConfig, target_url: str) -> None:
    """Connect to headed Chrome via CDP, navigate to *target_url*, and dump storage state.

    Run this *after* logging in via headed mode so that headless mode can
    restore the login session from the saved file.
    """
    if is_cdp_ready(config):
        logger.info("CDP debug port ready: %s", config.chrome.version_url)
    else:
        raise ConnectionError(f"CDP debug port not ready: {config.chrome.version_url}")
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(config.chrome.debug_url)
        page = _get_or_create_page(browser, target_url)
        if target_url:
            page.goto(target_url, wait_until="load")
            logger.info("Navigated to %s for storage state capture", target_url)

        context = browser.contexts[0]
        save_storage_state(context, config.chrome.storage_state_path)


def _get_or_create_page(browser: Browser, target_url: str, timeout: int | None = None) -> Page:
    """Find an existing tab with the target URL, or open a new one."""
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
