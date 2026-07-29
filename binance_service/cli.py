from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace

from binance_service import BinanceService
from binance_service._config import AppConfig, load_config
from binance_service.storage_state import save_storage_state_from_cdp

logger = logging.getLogger("cli")

LOG_FORMAT = "%(asctime)s UTC %(levelname)s %(module)s.%(funcName)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)


def _add_global_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", required=True, help="config.yaml 配置文件路径")
    parser.add_argument("--headed", action="store_true", help="有头模式启动 Chrome（显示 GUI）")
    parser.add_argument("-v", "--verbose", action="store_true", help="输出 DEBUG 级别日志")


def _load_app_config(args: argparse.Namespace) -> AppConfig:
    app_config = load_config(args.config)
    if args.headed:
        app_config = replace(app_config, headless=False)
    return app_config


# ── post ─────────────────────────────────────────────────────


def cmd_post(args: argparse.Namespace) -> None:
    cfg = _load_app_config(args)
    with BinanceService(app_config=cfg) as svc:
        share_link = svc.create_post(
            base_asset=args.base,
            content=args.content,
            image_path=args.image,
            debug=args.debug,
        )
    if share_link:
        print(f"✅ 帖子发布成功: {share_link}")
    else:
        print("❌ 发帖失败，未获取到 shareLink", file=sys.stderr)
        sys.exit(1)


def register_post(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--base", required=True, help="交易对基础资产，如 DOGE")
    sub.add_argument("--content", required=True, help="帖子正文内容")
    sub.add_argument("--image", default=None, help="可选，本地图片路径")
    sub.add_argument("--debug", action="store_true", help="启用调试截图")
    sub.set_defaults(func=cmd_post)


# ── screenshot ───────────────────────────────────────────────


def cmd_screenshot(args: argparse.Namespace) -> None:
    cfg = _load_app_config(args)
    with BinanceService(app_config=cfg) as svc:
        result = svc.symbol_screenshot(
            symbol=args.symbol,
            timeframe=args.timeframe,
            output=args.output,
            debug=args.debug,
        )
    print(f"✅ 截图已保存: {result}")


def register_screenshot(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--symbol", required=True, help="合约交易对，如 BTCUSDC、ETHUSDC")
    sub.add_argument(
        "--timeframe",
        choices=("5m", "15m", "1h", "4h", "1d", "1w"),
        default=None,
        help="K 线时间周期，默认取配置中的 default_timeframe",
    )
    sub.add_argument("--output", default=None, help="截图保存路径")
    sub.add_argument("--debug", action="store_true", help="启用调试截图")
    sub.set_defaults(func=cmd_screenshot)


# ── postx ────────────────────────────────────────────────────


def cmd_postx(args: argparse.Namespace) -> None:
    cfg = _load_app_config(args)
    with BinanceService(app_config=cfg) as svc:
        share_link = svc.create_postx(
            base_asset=args.base,
            content=args.content,
            quote=args.quote,
            timeframe=args.timeframe,
            debug=args.debug,
        )
    if share_link:
        print(f"✅ 帖子发布成功: {share_link}")
    else:
        print("❌ 发帖失败，未获取到 shareLink", file=sys.stderr)
        sys.exit(1)


def register_postx(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--base", required=True, help="交易对基础资产，如 DOGE")
    sub.add_argument("--content", required=True, help="帖子正文内容")
    sub.add_argument("--quote", default="USDT", help="报价币，默认 USDT（用于拼接交易对 symbol）")
    sub.add_argument(
        "--timeframe",
        choices=("5m", "15m", "1h", "4h", "1d", "1w"),
        default=None,
        help="K 线时间周期，默认取配置中的 default_timeframe",
    )
    sub.add_argument("--debug", action="store_true", help="启用调试截图")
    sub.set_defaults(func=cmd_postx)


# ── save-storage ─────────────────────────────────────────────


def cmd_save_storage(args: argparse.Namespace) -> None:
    cfg = _load_app_config(args)
    save_storage_state_from_cdp(cfg, target_url=args.url)
    print(f"✅ 登录态已保存到 {cfg.chrome.storage_state_path}")


def register_save_storage(sub: argparse.ArgumentParser) -> None:
    sub.add_argument(
        "--url",
        default="https://www.binance.com/zh-CN/square",
        help="登录后要导航到的页面，默认 Binance Square",
    )
    sub.set_defaults(func=cmd_save_storage)


# ── entry ────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Binance 命令行工具集 - 截图合约 K 线、发布 Square 帖子",
    )
    _add_global_args(parser)

    sub = parser.add_subparsers(title="子命令", dest="command", required=True)

    register_post(sub.add_parser("post", help="发布 Binance Square 帖子"))
    register_screenshot(sub.add_parser("screenshot", help="截取合约 K 线图"))
    register_postx(sub.add_parser("postx", help="截图 + 发帖组合操作"))
    register_save_storage(sub.add_parser("save-storage", help="导出 Chrome 登录态供 headless 复用"))

    args = parser.parse_args()
    _setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
