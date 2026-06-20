from __future__ import annotations

import argparse
import logging

from binance_service._config import AppConfig
from binance_service._playwright import save_storage_state


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s UTC %(levelname)s %(module)s.%(funcName)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="从 headed Chrome 导出登录态，供 headless 模式复用"
    )
    parser.add_argument(
        "--url",
        default="https://www.binance.com/zh-CN/square",
        help="登录后要导航到的页面（确保 cookies 已就绪），默认 Binance Square",
    )
    args = parser.parse_args()

    cfg = AppConfig.load()
    save_storage_state(cfg, target_url=args.url)


if __name__ == "__main__":
    main()
