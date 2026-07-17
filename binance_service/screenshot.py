from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile, gettempdir as _gettempdir

from PIL import Image
from playwright.sync_api import Browser, Page
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from binance_service._playwright import get_or_create_page

logger = logging.getLogger("screenshot")

BASE_URL = "https://www.binance.com/zh-CN/futures"
SCREENSHOT_WINDOW_WIDTH = 430
SCREENSHOT_WINDOW_HEIGHT = 932
SWITCH_UI_SELECTOR = 'div[style="grid-area: switch;"]'
CHART_UI_SELECTOR = 'div[style="grid-area: charts;"]'
GOTO_TIMEOUT_MS = 60000
SELECTOR_TIMEOUT_MS = 30000
TIMEFRAME_CHOICES = ("5m", "15m", "1h", "4h", "1d", "1w")
DEFAULT_TIMEFRAME = "1h"
# 切换 K 线周期后等待图表重绘的时间
TIMEFRAME_REDRAW_WAIT_MS = 5000
# 导航后等待图表初始加载的时间
CHART_INITIAL_WAIT_MS = 3000
# 调试快照存放目录（仅在选择器超时等失败时写入）
DEBUG_SNAPSHOT_DIR = Path(_gettempdir()) / "binance_service_debug"
# 快照抓取的单步超时：页面已处于异常态，不能用默认 30s，否则快照本身也会超时
DEBUG_SNAPSHOT_TIMEOUT_MS = 5000


def _dump_debug_snapshot(page: Page, tag: str) -> None:
    """选择器超时等失败时，把当前页面截图 + HTML 落盘，便于离线排查 headless 渲染问题。

    币安在 headless 下可能被风控拦截、跳转登录页、或卡在资源加载阶段，
    仅凭选择器超时无法定位根因，所以失败时保留现场。
    分步抓取并各自保护，保证至少 HTML 一定能拿到（content 不依赖资源加载）。
    """
    try:
        DEBUG_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("Failed to create debug snapshot dir: %s", exc)
        return

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # 1. HTML 优先：page.content() 读当前 DOM，不等待资源，几乎不会卡
    html_path = DEBUG_SNAPSHOT_DIR / f"{tag}_{ts}.html"
    try:
        html_path.write_text(page.content(), encoding="utf-8")
        logger.error(
            "Debug HTML saved: %s (url=%s, title=%s)",
            html_path, page.url, page.title(),
        )
    except PlaywrightError as exc:
        logger.error("Failed to dump debug HTML: %s", exc)

    # 2. 视口截图：full_page=True 在卡死页面上要等所有资源，容易超时，故只截视口并加短超时
    png_path = DEBUG_SNAPSHOT_DIR / f"{tag}_{ts}.png"
    try:
        page.screenshot(
            path=str(png_path),
            full_page=False,
            timeout=DEBUG_SNAPSHOT_TIMEOUT_MS,
        )
        logger.error("Debug PNG saved: %s", png_path)
    except PlaywrightError as exc:
        logger.error("Failed to dump debug PNG (page likely stuck on resource load): %s", exc)


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

        skeleton = page.locator('div[class="futures-skeleton-root"]')
        if skeleton.count() > 0:
            skeleton.evaluate_all("els => els.forEach(el => el.remove())")
            page.wait_for_timeout(500)

        with NamedTemporaryFile(suffix=".png") as f1, NamedTemporaryFile(suffix=".png") as f2:
            page.locator(SWITCH_UI_SELECTOR).screenshot(path=str(f1.name), scale="device")
            page.locator(CHART_UI_SELECTOR).screenshot(path=str(f2.name), scale="device")
            _image_merge(f1.name, f2.name, resolved_path.as_posix())

        logger.info("Screenshot saved: %s", resolved_path)
        return resolved_path

    except PlaywrightTimeout as exc:
        _dump_debug_snapshot(page, f"chart_timeout_{symbol}_{timeframe}")
        raise RuntimeError(
            f"Selector {CHART_UI_SELECTOR} not visible after {SELECTOR_TIMEOUT_MS}ms"
        ) from exc
    finally:
        try:
            page.evaluate("(()=>{const s=document.getElementById('__pw_hide_sb');if(s)s.remove()})()")
        finally:
            page.close()
