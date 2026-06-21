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
    bin_path: str
    user_data_dir: str
    headless_user_data_dir: str
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
        chrome_data_dir = Path.home() / ".debug_chrome" / "1"
        if not os.getenv("USER_DATA_DIR"):
            logger.warning("USER_DATA_DIR/HEADLESS_USER_DATA_DIR/STORAGE_STATE_PATH environment variables are not configured")

        return ChromeConfig(
            bin_path=os.getenv("CHROME_BIN", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            user_data_dir=os.getenv("USER_DATA_DIR", (chrome_data_dir / "user-data").as_posix()),
            headless_user_data_dir=os.getenv("HEADLESS_USER_DATA_DIR", (chrome_data_dir / "headless-user-data").as_posix()),
            storage_state_path=os.getenv("STORAGE_STATE_PATH", (chrome_data_dir / "storage_state.json").as_posix()),
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
