from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import dotenv
import logging
logger = logging.getLogger("_config.py")

# 配置根目录
CONFIG_DIR = Path.home() / ".binance-service"

_env_path = CONFIG_DIR / ".env"
if not dotenv.load_dotenv(_env_path):
    logger.warning("Failed to load environment variables from %s", _env_path)


@dataclass(frozen=True)
class ChromeConfig:
    storage_state_path: str
    debug_address: str
    debug_port: int

    @property
    def debug_url(self) -> str:
        return f"http://{self.debug_address}:{self.debug_port}"

    @property
    def version_url(self) -> str:
        return f"{self.debug_url}/json/version"

    @classmethod
    def default(cls) -> ChromeConfig:
        if not os.getenv("STORAGE_STATE_PATH"):
            logger.warning(
                "STORAGE_STATE_PATH environment variable is not configured"
            )

        return ChromeConfig(
            storage_state_path=os.getenv("STORAGE_STATE_PATH", (CONFIG_DIR / "storage_state.json").as_posix()),
            debug_address=os.getenv("DEBUG_ADDRESS", "127.0.0.1"),
            debug_port=int(os.getenv("DEBUG_PORT", "18800")),
        )


@dataclass(frozen=True)
class WindowConfig:
    width: int = 1920
    height: int = 1080


@dataclass(frozen=True)
class AppConfig:
    chrome: ChromeConfig = ChromeConfig.default()
    window: WindowConfig = WindowConfig()
    headless: bool = True
