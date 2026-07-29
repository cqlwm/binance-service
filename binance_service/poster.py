from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Browser
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from binance_service._config import PosterConfig
from binance_service._playwright import get_or_create_page
from binance_service.login_state import verify_login_state

logger = logging.getLogger("poster")


def _debug_screenshot(page: Page, debug_screenshot_dir: str, label: str) -> None:
    """Save a full-page screenshot for debugging, named by step label."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    output_dir = Path(debug_screenshot_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{ts}_{label}.png"
    page.screenshot(path=path.as_posix(), full_page=True)
    logger.info("Debug screenshot saved: %s", path)


def _focus_input_box(page: Page) -> None:
    editor = "div.json-article-editor"
    page.wait_for_selector(editor)
    page.click(editor)


def _input_symbol(page: Page, base_asset: str, dropdown_wait_seconds: int) -> None:
    page.keyboard.type(f"${base_asset}")
    icon_boxs_selector = ".tippy-box .tippy-content .bg-cardBg"
    try:
        page.wait_for_selector(icon_boxs_selector)
        time.sleep(dropdown_wait_seconds)
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


def _paste_image(page: Page, image_path: str, poll_count: int, poll_interval: float, img_timeout_ms: int) -> None:
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

    img = page.wait_for_selector(".short-editor-content img", timeout=img_timeout_ms)
    assert img is not None, "Image element not found in editor"

    for _ in range(poll_count):
        src = img.get_attribute("src") or ""
        if src.startswith("/bapi/fe/resource/image"):
            break
        page.wait_for_timeout(int(poll_interval * 1000))
    else:
        logger.warning("Image upload did not complete within poll limit")


def _input_trade_widget(page: Page, base_asset: str, default_timeout_ms: int) -> None:
    trade_widget_list_selector = ".bg-CardBg .text-PrimaryText"
    try:
        page.wait_for_selector(trade_widget_list_selector, timeout=default_timeout_ms)
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


def _click_send_button(page: Page, post_api_url: str, button_timeout_ms: int, api_timeout_ms: int) -> str | None:
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
            timeout=button_timeout_ms,
        )
        with page.expect_response(
            lambda resp: post_api_url in resp.url,
            timeout=api_timeout_ms,
        ) as response_info:
            send_button.click()
        response = response_info.value
        status = response.status
        body = response.json()
        logger.info("Post API responded with status=%d, body=%s", status, body)
        if body.get("success") and body.get("data", {}).get("shareLink"):
            return body["data"]["shareLink"]
        return None
    except PlaywrightTimeout:
        logger.warning("Send button remained inactive or API did not respond, skipping click")
        return None


def create_post(
    browser: Browser,
    config: PosterConfig,
    base_asset: str,
    content: str,
    image_path: str | None = None,
    debug: bool = False,
) -> str | None:
    page = get_or_create_page(browser, config.target_url, config.goto_timeout_ms)

    # 校验登录态：检查页面是否存在 .user-info .username 元素，
    # 失败时抛出 LoginStateError 中止发帖，避免后续 DOM 操作无谓失败
    verify_login_state(page, config.goto_timeout_ms)

    if debug:
        _debug_screenshot(page, config.debug_screenshot_dir, "01_after_login")

    _focus_input_box(page)
    if debug:
        _debug_screenshot(page, config.debug_screenshot_dir, "02_after_focus_input")

    _input_symbol(page, base_asset, config.symbol_dropdown_wait_seconds)
    if debug:
        _debug_screenshot(page, config.debug_screenshot_dir, "03_after_input_symbol")

    _input_content(page, content)
    if debug:
        _debug_screenshot(page, config.debug_screenshot_dir, "04_after_input_content")
    if image_path:
        img_file = Path(image_path)
        if not img_file.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        if img_file.suffix.lower() not in config.supported_image_extensions:
            raise ValueError(
                f"Unsupported image format: {img_file.suffix}. "
                f"Supported: {', '.join(sorted(config.supported_image_extensions))}"
            )
        _paste_image(
            page,
            image_path,
            config.image_upload_poll_count,
            config.image_upload_poll_interval,
            config.send_api_timeout_ms,
        )
        if debug:
            _debug_screenshot(page, config.debug_screenshot_dir, "05_after_paste_image")

    _input_trade_widget(page, base_asset, config.trade_widget_default_timeout_ms)
    if debug:
        _debug_screenshot(page, config.debug_screenshot_dir, "06_after_trade_widget")

    share_link = _click_send_button(
        page, config.post_api_url, config.send_button_timeout_ms, config.send_api_timeout_ms
    )
    if debug:
        _debug_screenshot(page, config.debug_screenshot_dir, "07_after_send")

    return share_link
