from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Browser
from playwright.sync_api import BrowserContext
from playwright.sync_api import Page, ViewportSize
from playwright.sync_api import sync_playwright

from binance_service._chrome import ensure_cdp_chrome_running
from binance_service._config import AppConfig

logger = logging.getLogger("playwright")


@contextmanager
def connect_browser(config: AppConfig) -> Generator[Browser, None, None]:
    """Launch Chrome via Playwright and create a context with restored login state.

    Both headless and headed modes use the same path:
    ``pw.chromium.launch()`` → ``browser.new_context()``.
    Login state is restored from a previously saved storage-state file.
    On successful completion, the (potentially refreshed) storage state
    is written back so subsequent sessions use the latest session.
    """
    chrome_path = Path(config.chrome.bin_path)
    if not chrome_path.exists():
        raise FileNotFoundError(f"Chrome not found: {chrome_path}")

    w = config.window.width
    h = config.window.height
    vp: ViewportSize = {"width": w, "height": h}

    logger.info(
        "Launching Chrome (headless=%s, window=%dx%d)",
        config.headless, w, h,
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=config.headless,
            executable_path=config.chrome.bin_path,
            args=["--no-first-run", "--no-default-browser-check"],
        )
        context = browser.new_context(
            viewport=vp,
            device_scale_factor=2,
        )
        _restore_storage_state(context, config.chrome.storage_state_path)

        error_occurred = False
        try:
            yield browser
        except BaseException:
            error_occurred = True
            raise
        finally:
            if not error_occurred:
                _save_storage_state(context, config.chrome.storage_state_path)
            context.close()


def _restore_storage_state(context: BrowserContext, storage_state_path: str) -> None:
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


def _save_storage_state(context: BrowserContext, storage_state_path: str) -> None:
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


def save_storage_state(config: AppConfig, target_url: str) -> None:
    """Connect to headed Chrome via CDP, navigate to *target_url*, and dump storage state.

    Run this *after* logging in via headed mode so that headless mode can
    restore the login session from the saved file.
    """
    ensure_cdp_chrome_running(config=config)
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(config.chrome.debug_url)
        page = get_or_create_page(browser, target_url)
        if target_url:
            page.goto(target_url, wait_until="load")
            logger.info("Navigated to %s for storage state capture", target_url)

        context = browser.contexts[0]
        _save_storage_state(context, config.chrome.storage_state_path)


def get_or_create_page(browser: Browser, target_url: str, timeout: int | None = None) -> Page:
    for context in browser.contexts:
        for page in context.pages:
            if page.url == target_url:
                logger.info("Reusing existing tab: %s", page.url)
                return page

    # else 分支是防御性死代码——永远不会走到
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()
    page.goto(target_url, wait_until="load", timeout=timeout)
    logger.info("Opened new tab: %s", page.url)
    return page
