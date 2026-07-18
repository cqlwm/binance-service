from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from playwright.sync_api import Browser

from binance_service._config import AppConfig
from binance_service._playwright import connect_browser
from binance_service.poster import create_post
from binance_service.screenshot import symbol_screenshot

logger = logging.getLogger("service")


class BinanceService:
    """Binance 自动化操作的服务封装。

    管理浏览器生命周期，外部只需维持一个对象，多次调用 post / screenshot
    共用同一个浏览器实例，避免反复开关 Chrome。
    """

    def __init__(self, app_config: AppConfig) -> None:
        self._app_config = app_config
        self._browser: Browser | None = None
        self._cm: contextlib.AbstractContextManager[Browser] | None = None

    # ── 生命周期 ──────────────────────────────────────────────

    @property
    def _browser_instance(self) -> Browser:
        if self._browser is None:
            raise RuntimeError("Browser is not available. Use as context manager or call open() first.")
        return self._browser

    def open(self) -> None:
        """打开浏览器（如尚未打开）。"""
        if self._browser is not None:
            return
        cm = connect_browser(self._app_config)
        self._browser = cm.__enter__()
        self._cm = cm

    def close(self) -> None:
        """关闭浏览器。"""
        if self._browser is None:
            return
        if self._cm is not None:
            self._cm.__exit__(None, None, None)
        self._browser = None
        self._cm = None

    def __enter__(self) -> BinanceService:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ── 业务方法 ──────────────────────────────────────────────

    def create_post(
        self,
        base_asset: str,
        content: str,
        image_path: str | None = None,
        debug: bool = False,
    ) -> str | None:
        """发布 Binance Square 帖子。

        参数含义同 ``binance_service.poster.post``，但复用当前浏览器实例。
        """
        return create_post(
            browser=self._browser_instance,
            config=self._app_config.poster,
            base_asset=base_asset,
            content=content,
            image_path=image_path,
            debug=debug,
        )

    def create_postx(
        self,
        base_asset: str,
        content: str,
        quote: str = "USDT",
        timeframe: str | None = None,
        debug: bool = False,
    ) -> str | None:
        """截图 + 发帖组合操作。

        如果未提供 image_path，先截取 K 线图再发帖。
        quote 为报价币（如 USDT、USDC），用于拼接交易对 symbol。
        timeframe 默认取配置中的 default_timeframe。
        """
        shot_cfg = self._app_config.screenshot
        resolved_timeframe = shot_cfg.default_timeframe if timeframe is None else timeframe
        screenshot_path = self.symbol_screenshot(symbol=f"{base_asset}{quote}", timeframe=resolved_timeframe)
        image_path = screenshot_path.as_posix()

        return self.create_post(
            base_asset=base_asset,
            content=content,
            image_path=image_path,
            debug=debug,
        )

    def symbol_screenshot(
        self,
        symbol: str,
        timeframe: str | None = None,
        output: str | None = None,
    ) -> Path:
        """截取 Binance 合约 K 线图。

        参数含义同 ``binance_service.screenshot.symbol_screenshot``，
        但复用当前浏览器实例。timeframe 默认取配置中的 default_timeframe。
        """
        shot_cfg = self._app_config.screenshot
        resolved_timeframe = shot_cfg.default_timeframe if timeframe is None else timeframe
        if resolved_timeframe not in shot_cfg.timeframe_choices:
            raise ValueError(f"Invalid timeframe: {resolved_timeframe!r}. Choose from {shot_cfg.timeframe_choices}.")
        return symbol_screenshot(self._browser_instance, shot_cfg, symbol, resolved_timeframe, output)
