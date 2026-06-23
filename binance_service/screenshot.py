from __future__ import annotations

import logging
from pathlib import Path
from PIL import Image
from tempfile import NamedTemporaryFile

from playwright.sync_api import Browser
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from binance_service._config import AppConfig, WindowConfig
from binance_service._playwright import connect_browser, get_or_create_page

logger = logging.getLogger("screenshot")

BASE_URL = "https://www.binance.com/zh-CN/futures"
SCREENSHOT_WINDOW_WIDTH = 430
SCREENSHOT_WINDOW_HEIGHT = 932
SWITCH_UI_SELECTOR = 'div[style="grid-area: switch;"]'
CHART_UI_SELECTOR = 'div[style="grid-area: charts;"]'
GOTO_TIMEOUT_MS = 60000
SELECTOR_TIMEOUT_MS = 15000
TIMEFRAME_CHOICES = ("5m", "15m", "1h", "4h", "1d", "1w")
DEFAULT_TIMEFRAME = "1h"
# 切换 K 线周期后等待图表重绘的时间
TIMEFRAME_REDRAW_WAIT_MS = 5000
# 导航后等待图表初始加载的时间
CHART_INITIAL_WAIT_MS = 3000

def _image_merge(image1: str, image2: str, output: str):

    # 1. 读取两张图片
    img1 = Image.open(image1)
    img2 = Image.open(image2)

    # 校验宽度相等（题目要求等宽）
    assert img1.width == img2.width, "两张图片宽度不一致"

    # 新建画布：宽=原图宽度，高=两张高度相加
    new_width = img1.width
    new_height = img1.height + img2.height
    combined = Image.new("RGB", (new_width, new_height))

    # 依次粘贴图片
    combined.paste(img1, (0, 0))          # 第一张贴顶部
    combined.paste(img2, (0, img1.height))# 第二张贴第一张下方

    # 保存
    combined.save(output)

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
    app_config: AppConfig = AppConfig(window=WindowConfig(SCREENSHOT_WINDOW_WIDTH, SCREENSHOT_WINDOW_HEIGHT)),
    browser: Browser | None = None,
) -> Path:
    if timeframe not in TIMEFRAME_CHOICES:
        raise ValueError(
            f"Invalid timeframe: {timeframe!r}. "
            f"Choose from {TIMEFRAME_CHOICES}."
        )

    output_path = _resolve_output_path(symbol, timeframe, output)

    if browser is not None:
        _do_screenshot(browser, symbol, timeframe, output_path)
    else:
        with connect_browser(app_config) as b:
            _do_screenshot(b, symbol, timeframe, output_path)

    return output_path




def _do_screenshot(
    browser: Browser,
    symbol: str,
    timeframe: str,
    output_path: Path,
) -> None:
    url = f"{BASE_URL}/{symbol}"

    page = get_or_create_page(browser, url, GOTO_TIMEOUT_MS)
    page.set_viewport_size({"width": SCREENSHOT_WINDOW_WIDTH, "height": SCREENSHOT_WINDOW_HEIGHT})

    try:
        page.wait_for_selector(CHART_UI_SELECTOR, state="visible", timeout=SELECTOR_TIMEOUT_MS)
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

        with NamedTemporaryFile(suffix=".png") as f1, NamedTemporaryFile(suffix=".png") as f2:
            page.locator(SWITCH_UI_SELECTOR).screenshot(path=str(f1.name), scale="device")
            page.locator(CHART_UI_SELECTOR).screenshot(path=str(f2.name), scale="device")
            _image_merge(f1.name, f2.name, output_path.as_posix())

        logger.info("Screenshot saved: %s", output_path)

    except PlaywrightTimeout as exc:
        raise RuntimeError(
            f"Selector {CHART_UI_SELECTOR} not visible after {SELECTOR_TIMEOUT_MS}ms"
        ) from exc
    finally:
        try:
            page.evaluate("(()=>{const s=document.getElementById('__pw_hide_sb');if(s)s.remove()})()")
        finally:
            page.close()


def main() -> None:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s UTC %(levelname)s %(module)s.%(funcName)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description=(
            f"在 {SCREENSHOT_WINDOW_WIDTH}x{SCREENSHOT_WINDOW_HEIGHT} 窗口中截取 Binance 合约页"
            f" {CHART_UI_SELECTOR} 元素（复用登录态）"
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
        "--headed",
        action="store_true",
        help="以有头模式启动 Chrome（显示 GUI）",
    )
    args = parser.parse_args()

    cfg = AppConfig(headless=not args.headed, window=WindowConfig(SCREENSHOT_WINDOW_WIDTH, SCREENSHOT_WINDOW_HEIGHT))
    take_futures_screenshot(
        symbol=args.symbol,
        timeframe=args.timeframe,
        output=args.output,
        app_config=cfg,
    )


if __name__ == "__main__":
    main()
