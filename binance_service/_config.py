from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import dotenv


@dataclass(frozen=True)
class ChromeConfig:
    bin_path: str = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    user_data_dir: str = str(Path.home() / ".debug_chrome" / "1" / "user-data")
    debug_address: str = "127.0.0.1"
    debug_port: int = 18800

    @property
    def debug_url(self) -> str:
        return f"http://{self.debug_address}:{self.debug_port}"

    @property
    def version_url(self) -> str:
        return f"{self.debug_url}/json/version"


@dataclass(frozen=True)
class WindowConfig:
    width: int = 1920
    height: int = 1080


@dataclass(frozen=True)
class AppConfig:
    chrome: ChromeConfig = ChromeConfig()
    window: WindowConfig = WindowConfig()

    @classmethod
    def load(cls, env_path: str | Path | None = None) -> AppConfig:
        dotenv.load_dotenv(env_path)
        chrome = ChromeConfig(
            bin_path=os.getenv("CHROME_BIN", ChromeConfig.bin_path),
            user_data_dir=os.getenv("USER_DATA_DIR", ChromeConfig.user_data_dir),
            debug_address=os.getenv("DEBUG_ADDRESS", ChromeConfig.debug_address),
            debug_port=int(os.getenv("DEBUG_PORT", str(ChromeConfig.debug_port))),
        )
        return cls(chrome=chrome)
