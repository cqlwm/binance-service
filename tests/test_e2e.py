"""端到端集成测试：截图 BTC/USDT → 发帖看涨 BTC（附带截图图片）。

前置条件：
  1. 已通过 ``binance-save-storage`` 保存登录态
  2. Chrome 已安装且可被 Playwright 调用

运行方式：
  uv run python -m pytest tests/test_e2e.py -v --headed  # 有头模式（可观察）
  uv run python -m pytest tests/test_e2e.py -v            # 无头模式
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from binance_service import BinanceService

logger = logging.getLogger(__name__)

# ── 测试参数 ──────────────────────────────────────────────────

BTC_SYMBOL = "BTCUSDT"
USDT_SYMBOL = "ETHUSDT"  # USDT 本身不是合约交易对，用 ETHUSDT 作为第二个截图示例
POST_ASSET = "BTC"
POST_CONTENT = "BTC looks bullish! 🚀 Strong upward momentum on the daily chart."
TIMEFRAME = "1d"

# 截图输出目录
SCREENSHOT_DIR = Path.home() / ".binance-service" / "test_screenshots"


@pytest.fixture(scope="module")
def svc() -> BinanceService:
    """模块级 fixture：整个测试模块只打开一次浏览器。"""
    with BinanceService() as service:
        yield service


def test_screenshot_btc(svc: BinanceService) -> None:
    """截图 BTCUSDT 合约 K 线。"""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    btc_path = SCREENSHOT_DIR / f"{BTC_SYMBOL}_{TIMEFRAME}_chart.png"

    result = svc.symbol_screenshot(
        symbol=BTC_SYMBOL,
        timeframe=TIMEFRAME,
        output=str(btc_path),
    )

    assert result.exists(), f"BTC 截图未生成: {result}"
    assert result.stat().st_size > 1024, f"BTC 截图文件过小: {result.stat().st_size} bytes"
    logger.info("BTC 截图已保存: %s", result)


# def test_screenshot_usdt(svc: BinanceService) -> None:
#     """截图 ETHUSDT 合约 K 线（作为 USDT 交易对示例）。"""
#     usdt_path = SCREENSHOT_DIR / f"{USDT_SYMBOL}_{TIMEFRAME}_chart.png"
#
#     result = svc.take_futures_screenshot(
#         symbol=USDT_SYMBOL,
#         timeframe=TIMEFRAME,
#         output=str(usdt_path),
#     )
#
#     assert result.exists(), f"USDT 截图未生成: {result}"
#     assert result.stat().st_size > 1024, f"USDT 截图文件过小: {result.stat().st_size} bytes"
#     logger.info("USDT 截图已保存: %s", result)


def test_post_btc_with_image(svc: BinanceService) -> None:
    """发帖看涨 BTC，并附带 BTC 截图作为图片。"""
    btc_image = SCREENSHOT_DIR / f"{BTC_SYMBOL}_{TIMEFRAME}_chart.png"
    assert btc_image.exists(), (
        f"BTC 截图不存在，请先运行 test_screenshot_btc: {btc_image}"
    )

    share_link = svc.create_post(
        base_asset=POST_ASSET,
        content=POST_CONTENT,
        image_path=str(btc_image),
        debug=True,  # 开启调试截图，方便排查
    )

    assert share_link is not None, "发帖失败，未获取到 shareLink"
    assert share_link.startswith("https://"), f"shareLink 格式异常: {share_link}"
    logger.info("帖子发布成功: %s", share_link)
