from __future__ import annotations

import logging
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from binance_service._config import AppConfig
from binance_service._playwright import connect_browser, get_or_create_page

logger = logging.getLogger("screenshot")

BASE_URL = "https://www.binance.com/zh-CN/futures"
SCREENSHOT_WINDOW_WIDTH = 500
SCREENSHOT_WINDOW_HEIGHT = 800
TARGET_SELECTOR = "div#chart"
GOTO_TIMEOUT_MS = 60000
SELECTOR_TIMEOUT_MS = 15000
TIMEFRAME_CHOICES = ("5m", "15m", "1h", "4h", "1d", "1w")
DEFAULT_TIMEFRAME = "1h"
# 切换 K 线周期后等待图表重绘的时间
TIMEFRAME_REDRAW_WAIT_MS = 5000
# 导航后等待图表初始加载的时间
CHART_INITIAL_WAIT_MS = 3000


def _resolve_output_path(symbol: str, timeframe: str, output: str | None) -> Path:
    path = (
        Path(output).expanduser()
        if output
        else Path.cwd() / f"{symbol}_{timeframe}_chart.png"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def take_futures_screenshot(
    symbol: str,
    timeframe: str = DEFAULT_TIMEFRAME,
    output: str | None = None,
    headless: bool = False,
    config: AppConfig | None = None,
) -> Path:
    if timeframe not in TIMEFRAME_CHOICES:
        raise ValueError(
            f"Invalid timeframe: {timeframe!r}. "
            f"Choose from {TIMEFRAME_CHOICES}."
        )

    output_path = _resolve_output_path(symbol, timeframe, output)
    url = f"{BASE_URL}/{symbol}"
    cfg = config or AppConfig.load()

    with connect_browser(
        cfg,
        headless=headless,
        window_width=SCREENSHOT_WINDOW_WIDTH,
        window_height=SCREENSHOT_WINDOW_HEIGHT,
    ) as browser:
        try:
            logger.warning("############# haha 123")
            page = get_or_create_page(browser, url, GOTO_TIMEOUT_MS)
            if headless:
                page.reload(timeout=GOTO_TIMEOUT_MS)

            page.wait_for_selector(TARGET_SELECTOR, state="visible", timeout=SELECTOR_TIMEOUT_MS)
            page.wait_for_timeout(CHART_INITIAL_WAIT_MS)

            timeframe_selector = f'div[id="{timeframe}"]'
            page.locator(timeframe_selector).click()
            page.wait_for_timeout(TIMEFRAME_REDRAW_WAIT_MS)

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(500)
            page.evaluate("""(()=>{
                const s=document.createElement('style');
                s.id='__pw_hide_sb';
                s.textContent='::-webkit-scrollbar{display:none!important}';
                document.head.appendChild(s);
            })()""")
            page.wait_for_timeout(500)

            page.locator(TARGET_SELECTOR).screenshot(path=str(output_path), scale="device")
            logger.info("Screenshot saved: %s", output_path)

        except PlaywrightTimeout as exc:
            raise RuntimeError(f"Selector {TARGET_SELECTOR} not visible after {SELECTOR_TIMEOUT_MS}ms") from exc
        finally:
            try:
                page.evaluate("(()=>{const s=document.getElementById('__pw_hide_sb');if(s)s.remove()})()")
            finally:
                page.close()

    return output_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            f"在 {SCREENSHOT_WINDOW_WIDTH}x{SCREENSHOT_WINDOW_HEIGHT} 窗口中截取 Binance 合约页"
            f" {TARGET_SELECTOR} 元素（复用登录态）"
        )
    )
    parser.add_argument(
        "--symbol", required=True, help="合约交易对，如 BTCUSDC、ETHUSDC"
    )
    parser.add_argument(
        "--timeframe",
        choices=TIMEFRAME_CHOICES,
        default=DEFAULT_TIMEFRAME,
        help="K 线时间周期（截图前切换），默认 1h",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="截图保存路径，默认 ./<symbol>_<timeframe>_chart.png",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="以无头模式启动 Chrome（无 GUI）",
    )
    args = parser.parse_args()
    take_futures_screenshot(args.symbol, args.timeframe, args.output, headless=args.headless)


if __name__ == "__main__":
    main()
