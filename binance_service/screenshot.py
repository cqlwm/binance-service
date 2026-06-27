from __future__ import annotations

import logging
from pathlib import Path
from PIL import Image
from tempfile import NamedTemporaryFile, gettempdir as _gettempdir

from playwright.sync_api import Browser
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from binance_service._playwright import get_or_create_page

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
        else Path(_gettempdir()) / f"{symbol}_{timeframe}_chart.png"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def symbol_screenshot(browser: Browser, symbol: str, timeframe: str, output_path: str | None) -> Path:
    resolved_path = _resolve_output_path(symbol, timeframe, output_path)

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
            _image_merge(f1.name, f2.name, resolved_path.as_posix())

        logger.info("Screenshot saved: %s", resolved_path)
        return resolved_path

    except PlaywrightTimeout as exc:
        raise RuntimeError(
            f"Selector {CHART_UI_SELECTOR} not visible after {SELECTOR_TIMEOUT_MS}ms"
        ) from exc
    finally:
        try:
            page.evaluate("(()=>{const s=document.getElementById('__pw_hide_sb');if(s)s.remove()})()")
        finally:
            page.close()
