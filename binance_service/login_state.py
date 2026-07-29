from __future__ import annotations

import logging
from typing import NoReturn

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

logger = logging.getLogger("login_state")


class LoginStateError(Exception):
    """登录态失效或 DOM 元素校验失败。"""


def verify_login_state(page: Page, timeout_ms: int) -> None:
    """通过 DOM 元素 ``.user-info .username`` 校验登录态。

    等待页面上出现 ``.user-info .username`` 元素，若超时未找到则判定
    为未登录，抛出 :class:`LoginStateError`。

    Args:
        page: 已导航到 Binance Square 的页面。
        timeout_ms: 等待元素出现的超时时间（毫秒）。

    Raises:
        LoginStateError: 登录态校验失败。
    """
    selector = ".user-info .username"
    try:
        page.locator(selector).wait_for(timeout=timeout_ms)
    except PlaywrightTimeout:
        _fail(f"登录态校验失败: 未找到元素 {selector!r}（超时 {timeout_ms}ms）")

    logger.info("登录态校验通过（元素 %s 存在）", selector)


def _fail(message: str) -> NoReturn:
    """记录 ERROR 日志并抛出 LoginStateError。"""
    logger.error(message)
    raise LoginStateError(message)
