import logging
import time
from pathlib import Path
from typing import Callable

import dotenv
from playwright.sync_api import Page
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError

from binance_service._chrome import DEBUG_URL
from binance_service._chrome import ensure_debug_chrome_running
from binance_service._chrome import is_cdp_ready

logger = logging.getLogger("chrome")

dotenv.load_dotenv()

TARGET_URL = "https://www.binance.com/zh-CN/square"


def open_page(target_url: str, run: Callable[[Page], None], headless: bool = False) -> None:
    if not is_cdp_ready():
        if headless:
            logger.info("CDP not ready, launching Chrome in headless mode...")
            ensure_debug_chrome_running(headless=True)
        else:
            logger.error("cdp not ready!")
            return

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(DEBUG_URL)
        context = browser.contexts[0] if browser.contexts else browser.new_context()

        target_page: Page | None = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if pg.url == target_url:
                    target_page = pg
                    break
            if target_page:
                break

        if target_page:
            page = target_page
            logger.info(f"Use the opened tabs: {page.url}")
        else:
            page = context.new_page()
            page.goto(target_url, wait_until="networkidle")
            logger.info(f"Open a new tab: {page.url}")

        if "/login" in page.url:
            raise RuntimeError(
                "Binance Square 未登录，请先在 headed 模式下完成登录，"
                "或检查 user-data-dir 中的 session cookies。"
            )

        run(page)


def _post(base_asset: str, content: str, page: Page, image_path: str | None = None) -> None:
    def _focus_input_box() -> None:
        page.click("div.json-article-editor")

    def _input_symbol() -> None:
        page.keyboard.type(f"${base_asset}")
        selector = ".tippy-box .tippy-content .bg-cardBg"
        try:
            page.wait_for_selector(selector, timeout=30000)
            time.sleep(3)
            container = page.locator(selector)
            children = container.locator(".text-PrimaryText").all()
            for child in children:
                if child.text_content() == base_asset:
                    logger.debug(child.text_content())
                    child.click()
                    break
        except TimeoutError:
            logger.warning(f"{base_asset}现货标签没找到")
        finally:
            page.keyboard.type(" ")

    def _input_content(text: str) -> None:
        page.keyboard.type(text)

    def _input_trade_widget(is_search: bool = False) -> None:
        trade_widget_list_selector = ".bg-CardBg .text-PrimaryText"
        try:
            timeout = 0 if is_search else 3000
            page.wait_for_selector(trade_widget_list_selector, timeout=timeout)
        except TimeoutError:
            logger.warning(f"wait_for_selector {trade_widget_list_selector} TimeoutError")
        except Exception as e:
            logger.error(e)

        if page.locator(trade_widget_list_selector).count() == 0:
            page.click(".trade-widget-icon.icon-box")
            symbol_name_input_selector = ".bg-CardBg .bn-textField-input"
            page.wait_for_selector(symbol_name_input_selector)
            page.fill(symbol_name_input_selector, base_asset)
            time.sleep(1)

        target = f"{base_asset}USDT"
        elements = page.locator(trade_widget_list_selector).all()
        for el in elements:
            logger.debug(el.text_content())
            if el.text_content() == target:
                el.click()
                break

    def _click_send_button() -> None:
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
                timeout=10000,
            )
            send_button.click()
        except TimeoutError:
            logger.warning("发送按钮仍处于 inactive 状态")

    def _paste_image(_image_path: str) -> None:
        import base64

        img_path = Path(_image_path)
        if not img_path.exists():
            logger.error(f"Image file not found: {_image_path}")
            return

        mime_type = "image/png" if _image_path.endswith(".png") else "image/jpeg"
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

        for _ in range(30):
            src = img.get_attribute("src") or ""
            if src and src.startswith("/bapi/fe/resource/image"):
                break
            page.wait_for_timeout(1000)
        else:
            logger.warning("图片上传等待超时")

    _focus_input_box()
    _input_symbol()
    _input_content(content)
    if image_path:
        _paste_image(image_path)
    _input_trade_widget()
    _click_send_button()


def create_post(base_asset: str, content: str, image_path: str | None = None, headless: bool = False) -> None:
    open_page(
        target_url=TARGET_URL,
        run=lambda page: _post(base_asset, content, page, image_path),
        headless=headless,
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="发布 Binance Square 帖子")
    parser.add_argument("--base", required=True, help="交易对基础资产，如 DOGE")
    parser.add_argument("--content", required=True, help="帖子正文内容")
    parser.add_argument("--image", default=None, help="可选，本地图片路径")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="以无头模式启动 Chrome（无 GUI），Chrome 未运行时自动启动",
    )
    args = parser.parse_args()
    create_post(args.base, args.content, args.image, headless=args.headless)


if __name__ == "__main__":
    main()
