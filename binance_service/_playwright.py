from __future__ import annotations

import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import TypeAlias

from cloakbrowser import launch
from playwright.sync_api import Browser, Page, ViewportSize

from binance_service._config import AppConfig
from binance_service.storage_state import restore_storage_state, save_storage_state

logger = logging.getLogger(__name__)

# 导航动作：由 get_or_create_page 注入 page.goto，调用方在 callback 内部触发，
# 以便用 expect_response 在 goto 之前挂上响应监听器
NavigateFn: TypeAlias = Callable[[], None]

# cloakbrowser 返回的 Browser 对象已 patch close() 会同步停止 playwright，
# 故无需再用 sync_playwright() 上下文管理器包裹。
DEFAULT_CONTEXT_TIMEOUT_MS = 30000
DEFAULT_NAVIGATION_TIMEOUT_MS = 60000


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
        "Launching cloakbrowser (headless=%s, window=%dx%d)",
        config.headless,
        w,
        h,
    )

    browser = launch(
        headless=config.headless,
        args=list(config.browser.launch_args),
    )
    context = browser.new_context(
        viewport=vp,
        device_scale_factor=config.browser.device_scale_factor,
    )
    context.set_default_timeout(DEFAULT_CONTEXT_TIMEOUT_MS)
    context.set_default_navigation_timeout(DEFAULT_NAVIGATION_TIMEOUT_MS)
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
        logger.info("Closed cloakbrowser !")


def get_or_create_page(
    browser: Browser,
    target_url: str,
    timeout: int | None = None,
    callback: Callable[[Page, NavigateFn], None] | None = None,
) -> Page:
    """Find an existing tab with the target URL, or open a new one.

    复用已存在的 tab 时跳过 callback（tab 已稳定，页面接口早已响应完毕）；
    仅在新开 tab 时调用 callback。调用方负责在 callback 内部用
    expect_response 等待特定接口返回 200 后再触发 navigate() 完成 goto--
    expect_response 谓词只看 with 块启动后的响应，故 goto 必须在块内执行。
    """
    for context in browser.contexts:
        for page in context.pages:
            if page.url == target_url:
                logger.info("Reusing existing tab: %s", page.url)
                return page

    # else 分支是防御性死代码--永远不会走到
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()

    def navigate() -> None:
        page.goto(target_url, wait_until="domcontentloaded", timeout=timeout)

    if callback is None:
        navigate()
    else:
        callback(page, navigate)

    logger.info("Opened new tab: %s", page.url)
    return page
