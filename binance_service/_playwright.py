from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager

from cloakbrowser import launch
from playwright.sync_api import Browser, Page, ViewportSize

from binance_service._config import AppConfig
from binance_service.storage_state import restore_storage_state, save_storage_state

logger = logging.getLogger(__name__)


@contextmanager
def connect_browser(config: AppConfig) -> Generator[Browser, None, None]:
    """Launch stealth Chromium via cloakbrowser and create a context with restored login state.

    Uses cloakbrowser's patched Chromium binary for anti-detection.
    Login state is restored from a previously saved storage-state file.
    On successful completion, the (potentially refreshed) storage state
    is written back so subsequent sessions use the latest session.
    """
    w = config.window.width
    h = config.window.height
    vp: ViewportSize = {"width": w, "height": h}

    logger.info(
        "Launching Chrome (headless=%s, window=%dx%d)",
        config.headless,
        w,
        h,
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=config.headless,
            args=list(config.browser.launch_args),
        )
        context = browser.new_context(
            viewport=vp,
            device_scale_factor=config.browser.device_scale_factor,
        )
        context.set_default_timeout(30000)
        context.set_default_navigation_timeout(60000)
        restore_storage_state(context, config.chrome.storage_state_path)

        error_occurred = False
        try:
            yield browser
        except BaseException:
            error_occurred = True
            raise
        finally:
            if not error_occurred:
                save_storage_state(context, config.chrome.storage_state_path)
            context.close()
            browser.close()
            logger.info("Closed Chrome !")


def get_or_create_page(browser: Browser, target_url: str, timeout: int | None = None) -> Page:
    """Find an existing tab with the target URL, or open a new one."""
    for context in browser.contexts:
        for page in context.pages:
            if page.url == target_url:
                logger.info("Reusing existing tab: %s", page.url)
                return page

# else 分支是防御性死代码--永远不会走到
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()
    page.goto(target_url, wait_until="domcontentloaded", timeout=timeout)
    logger.info("Opened new tab: %s", page.url)
    return page
