from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from binance_service._config import AppConfig
from binance_service._playwright import connect_browser
from binance_service._playwright import ensure_logged_in
from binance_service._playwright import get_or_create_page

logger = logging.getLogger("poster")

TARGET_URL = "https://www.binance.com/zh-CN/square"
GOTO_TIMEOUT_MS = 60000

# 输入资产标签后等待下拉列表渲染的时间
SYMBOL_DROPDOWN_WAIT_SECONDS = 3
# 交易 widget 搜索模式下等待列表出现的时间
TRADE_WIDGET_SEARCH_TIMEOUT_MS = 3000
# 交易 widget 非搜索模式下的等待时间
TRADE_WIDGET_DEFAULT_TIMEOUT_MS = 3000
# 发送按钮 active 状态等待超时
SEND_BUTTON_TIMEOUT_MS = 30000
# 发送 API 响应等待超时
SEND_API_TIMEOUT_MS = 30000
# 图片上传后轮询等待上传完成的最大次数
IMAGE_UPLOAD_POLL_COUNT = 30
# 图片上传轮询间隔
IMAGE_UPLOAD_POLL_INTERVAL = 1.0

SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}

# 调试截图输出目录
DEBUG_SCREENSHOT_DIR = Path.home() / ".debug_chrome" / "screenshots"

# 发帖 API 路径
POST_API_URL = "https://www.binance.com/bapi/composite/v5/private/pgc/content/add"


def _debug_screenshot(page: Page, label: str) -> None:
    """Save a full-page screenshot for debugging, named by step label."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    output_dir = DEBUG_SCREENSHOT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{ts}_{label}.png"
    page.screenshot(path=str(path), full_page=True)
    logger.info("Debug screenshot saved: %s", path)


def _focus_input_box(page: Page) -> None:
    editor = "div.json-article-editor"
    page.wait_for_selector(editor)
    page.click(editor)


def _input_symbol(page: Page, base_asset: str) -> None:
    page.keyboard.type(f"${base_asset}")
    icon_boxs_selector = ".tippy-box .tippy-content .bg-cardBg"
    try:
        page.wait_for_selector(icon_boxs_selector)
        time.sleep(SYMBOL_DROPDOWN_WAIT_SECONDS)
        container = page.locator(icon_boxs_selector)
        children = container.locator(".text-PrimaryText").all()
        for child in children:
            if child.text_content() == base_asset:
                logger.debug("Matched symbol: %s", child.text_content())
                child.click()
                break
    except PlaywrightTimeout:
        logger.warning("Symbol dropdown for %s not found within timeout", base_asset)
    finally:
        page.keyboard.type(" ")


def _input_content(page: Page, text: str) -> None:
    page.keyboard.type(text)


def _paste_image(page: Page, image_path: str) -> None:
    img_path = Path(image_path)
    if not img_path.exists():
        logger.error("Image file not found: %s", image_path)
        return

    mime_type = "image/png" if image_path.endswith(".png") else "image/jpeg"
    with open(img_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    page.evaluate(
        """
        ({ base64Data, mimeType, fileName }) => {
            const byteCharacters = atob(base64Data);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: mimeType });
            const file = new File([blob], fileName, { type: mimeType });

            const editor = document.querySelector('div.ProseMirror');
            if (!editor) {
                console.error('ProseMirror editor not found');
                return;
            }

            editor.focus();

            const dt = new DataTransfer();
            dt.items.add(file);

            const pasteEvent = new ClipboardEvent('paste', {
                bubbles: true,
                cancelable: true,
                clipboardData: dt
            });

            editor.dispatchEvent(pasteEvent);
        }
        """,
        {"base64Data": image_data, "mimeType": mime_type, "fileName": "image.jpg"},
    )

    img = page.wait_for_selector(".short-editor-content img", timeout=30000)

    for _ in range(IMAGE_UPLOAD_POLL_COUNT):
        src = img.get_attribute("src") or ""
        if src.startswith("/bapi/fe/resource/image"):
            break
        page.wait_for_timeout(int(IMAGE_UPLOAD_POLL_INTERVAL * 1000))
    else:
        logger.warning("Image upload did not complete within poll limit")


def _input_trade_widget(page: Page, base_asset: str) -> None:
    trade_widget_list_selector = ".bg-CardBg .text-PrimaryText"
    try:
        page.wait_for_selector(trade_widget_list_selector, timeout=TRADE_WIDGET_DEFAULT_TIMEOUT_MS)
    except PlaywrightTimeout:
        logger.warning("Trade widget list not found, attempting search mode")

    if page.locator(trade_widget_list_selector).count() == 0:
        page.click(".trade-widget-icon.icon-box")
        symbol_name_input_selector = ".bg-CardBg .bn-textField-input"
        page.wait_for_selector(symbol_name_input_selector)
        page.fill(symbol_name_input_selector, base_asset)
        time.sleep(1)

    target = f"{base_asset}USDT"
    elements = page.locator(trade_widget_list_selector).all()
    for el in elements:
        logger.debug("Trade widget option: %s", el.text_content())
        if el.text_content() == target:
            el.click()
            break


def _click_send_button(page: Page) -> None:
    selector = ".short-editor-inner button"
    send_button = page.locator(selector, has_text="发文")
    try:
        page.wait_for_function(
            """
            (selector) => {
                const btn = document.querySelector(selector);
                if (!btn) return false;
                return !btn.classList.contains('inactive');
            }
            """,
            arg=selector,
            timeout=SEND_BUTTON_TIMEOUT_MS
        )
        with page.expect_response(
            lambda resp: POST_API_URL in resp.url,
            timeout=SEND_API_TIMEOUT_MS,
        ) as response_info:
            send_button.click()
        response = response_info.value
        status = response.status
        body = response.json()
        logger.info("Post API responded with status=%d, body=%s", status, body)
    except PlaywrightTimeout:
        logger.warning("Send button remained inactive or API did not respond, skipping click")


def post(
    base_asset: str,
    content: str,
    image_path: str | None = None,
    headless: bool = False,
    debug: bool = False,
) -> None:
    cfg = AppConfig.load()

    with connect_browser(cfg, headless=headless) as browser:
        page = get_or_create_page(browser, TARGET_URL, GOTO_TIMEOUT_MS)
        ensure_logged_in(page)

        if debug:
            _debug_screenshot(page, "01_after_login")

        _focus_input_box(page)
        if debug:
            _debug_screenshot(page, "02_after_focus_input")

        _input_symbol(page, base_asset)
        if debug:
            _debug_screenshot(page, "03_after_input_symbol")

        _input_content(page, content)
        if debug:
            _debug_screenshot(page, "04_after_input_content")

        if image_path:
            img_file = Path(image_path)
            if not img_file.exists():
                raise FileNotFoundError(f'Image file not found: {image_path}')
            if img_file.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
                raise ValueError(
                    f'Unsupported image format: {img_file.suffix}. '
                    f'Supported: {', '.join(sorted(SUPPORTED_IMAGE_EXTENSIONS))}'
                )
            _paste_image(page, image_path)
            if debug:
                _debug_screenshot(page, "05_after_paste_image")

        _input_trade_widget(page, base_asset)
        if debug:
            _debug_screenshot(page, "06_after_trade_widget")

        _click_send_button(page)
        if debug:
            _debug_screenshot(page, "07_after_send")


def main() -> None:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s UTC %(levelname)s %(module)s.%(funcName)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="发布 Binance Square 帖子")
    parser.add_argument("--base", required=True, help="交易对基础资产，如 DOGE")
    parser.add_argument("--content", required=True, help="帖子正文内容")
    parser.add_argument("--image", default=None, help="可选，本地图片路径")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="以无头模式启动 Chrome（无 GUI），Chrome 未运行时自动启动",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式，每一步都截图保存到 ~/.debug_chrome/screenshots/",
    )
    args = parser.parse_args()
    post(args.base, args.content, args.image, headless=args.headless, debug=args.debug)


if __name__ == "__main__":
    main()
