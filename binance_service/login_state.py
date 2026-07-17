from __future__ import annotations

import logging
from typing import NoReturn, cast

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

logger = logging.getLogger("login_state")

# 登录态校验通过的预期 code 值
_OK_CODE = "000000"


class LoginStateError(Exception):
    """登录态失效或 userInfo 接口校验失败。"""


def verify_login_state(page: Page, user_info_api_url: str, timeout_ms: int) -> None:
    """被动监控页面发起的 userInfo 请求并校验登录态。

    用 ``page.expect_response`` 包裹 ``page.reload``，捕获前端在页面
    重新加载时自动发起的 userInfo 请求，校验 ``body['code']=='000000'``
    且 ``body['success'] is True``。任一条件不满足或超时未捕获到请求，
    抛出 :class:`LoginStateError`。

    Args:
        page: 已导航到 Binance Square 的页面。
        user_info_api_url: userInfo 接口端点 URL（用于匹配响应）。
        timeout_ms: 等待 userInfo 响应的超时（毫秒）。

    Raises:
        LoginStateError: 登录态校验失败。
    """
    try:
        with page.expect_response(
            lambda resp: user_info_api_url in resp.url,
            timeout=timeout_ms,
        ) as response_info:
            page.reload(wait_until="load")
        response = response_info.value
    except PlaywrightTimeout:
        _fail(f"userInfo 请求未在 {timeout_ms}ms 内出现，可能未登录或页面未发起该请求")

    status = response.status
    if status != 200:
        _fail(f"userInfo 接口返回非 200 状态码: {status}")

    body = cast(dict[str, object], response.json())
    code = body.get("code")
    if code != _OK_CODE:
        _fail(f"userInfo 接口 code 异常: {code!r}（预期 {_OK_CODE!r}）")

    success = body.get("success")
    if not success:
        message = body.get("message")
        _fail(f"userInfo 接口 success=false, message={message!r}")

    data = cast(dict[str, object], body.get("data") or {})
    user_id = data.get("userId")
    logger.info("登录态校验通过, userId=%s", user_id)


def _fail(message: str) -> NoReturn:
    """记录 ERROR 日志并抛出 LoginStateError。"""
    logger.error(message)
    raise LoginStateError(message)
