from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Browser
from playwright.sync_api import Page, ViewportSize
from playwright.sync_api import sync_playwright

from binance_service._chrome import ensure_cdp_chrome_running
from binance_service._config import AppConfig

logger = logging.getLogger("playwright")


@contextmanager
def connect_browser(config: AppConfig) -> Iterator[Browser]:
    if config.headless:
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
    """Launch Chrome via Playwright's persistent context (headless mode).

    Uses a separate user data dir to avoid Singleton-lock conflicts with
    a headed Chrome instance that may be running on the same profile.
    Login state is restored from a previously saved storage-state file.
    On successful completion, the (potentially refreshed) storage state
    is written back so subsequent headless sessions use the latest session.
    """
    chrome_path = Path(config.chrome.bin_path)
    if not chrome_path.exists():
        raise FileNotFoundError(f"Chrome not found: {chrome_path}")

    w = config.window.width
    h = config.window.height
    vp: ViewportSize = {"width": w, "height": h}

    logger.info(
        "Launching headless Chrome (user_data_dir=%s, window=%dx%d)",
        config.chrome.headless_user_data_dir, w, h,
    )

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=config.chrome.headless_user_data_dir,
            headless=True,
            executable_path=config.chrome.bin_path,
            args=["--no-first-run", "--no-default-browser-check"],
            viewport=vp,
            device_scale_factor=2,
        )
        _restore_storage_state(context, config.chrome.storage_state_path)

        browser = context.browser
        assert browser is not None, "launch_persistent_context did not return a Browser"
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


def _restore_storage_state(context, storage_state_path: str) -> None:
    """Load previously saved cookies / localStorage into the context."""
    path = Path(storage_state_path)
    if not path.exists():
        logger.info("No storage state file found at %s, starting fresh", path)
        return

    try:
        with open(path) as f:
            state = json.load(f)

        # 恢复 cookies
        cookies = state.get("cookies", [])
        context.add_cookies(cookies)
        logger.info("Restored %d cookies from %s", len(cookies), path)

        # 恢复 localStorage（每个 origin 需开一个页面写入）
        origins = state.get("origins", [])
        for entry in origins:
            origin = entry["origin"]
            ls_items = entry.get("localStorage", [])
            if not ls_items:
                continue
            page = context.new_page()
            try:
                page.goto(origin, wait_until="domcontentloaded")
                for item in ls_items:
                    page.evaluate(
                        "({ name, value }) => localStorage.setItem(name, value)",
                        {"name": item["name"], "value": item["value"]},
                    )
                logger.debug(
                    "Restored %d localStorage items for %s", len(ls_items), origin,
                )
            except Exception:
                logger.warning("Failed to restore localStorage for %s", origin)
            finally:
                page.close()
        logger.info(
            "Restored localStorage for %d origins", len(origins),
        )
    except Exception:
        logger.exception("Failed to restore storage state from %s", path)


def _save_storage_state(context, storage_state_path: str) -> None:
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

        cookie_count = len(state.get("cookies", []))
        logger.info(
            "Saved storage state (%d cookies, %d origins) to %s",
            cookie_count, len(state.get("origins", [])), path,
        )
    except Exception:
        logger.exception("Failed to save storage state to %s", path)


def save_storage_state(config: AppConfig, target_url: str | None = None) -> None:
    """Connect to headed Chrome, navigate to *target_url*, and dump storage state.

    Run this *after* logging in via headed mode so that headless mode can
    restore the login session from the saved file.
    """
    with _connect_cdp_browser(config) as browser:
        context = browser.contexts[0]
        page = context.new_page()
        if target_url:
            page.goto(target_url, wait_until="load")
            logger.info("Navigated to %s for storage state capture", target_url)

        _save_storage_state(context, config.chrome.storage_state_path)
        page.close()


def get_or_create_page(browser: Browser, target_url: str, timeout: int) -> Page:
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


def ensure_logged_in(page: Page, login_url_indicator: str = "/login") -> None:
    if login_url_indicator in page.url:
        raise RuntimeError(
            f"Not logged in (URL contains '{login_url_indicator}'). "
            "Please log in first in headed mode."
        )
