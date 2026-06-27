from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from binance_service._config import AppConfig

logger = logging.getLogger("chrome")

CDP_RETRY_COUNT = 20
CDP_RETRY_INTERVAL = 0.5


def is_cdp_ready(config: AppConfig) -> bool:
    try:
        with urlopen(config.chrome.version_url, timeout=1):
            return True
    except (URLError, TimeoutError, OSError):
        return False


def ensure_cdp_chrome_running(config: AppConfig) -> None:
    """Ensure a Chrome instance with CDP debug port is running (headed mode)."""
    chrome_path = Path(config.chrome.bin_path)
    if not chrome_path.exists():
        raise FileNotFoundError(f"Chrome not found: {chrome_path}")

    if is_cdp_ready(config):
        logger.info("CDP debug port ready: %s", config.chrome.version_url)
        return

    w = config.window.width
    h = config.window.height

    args = [
        config.chrome.bin_path,
        f"--remote-debugging-port={config.chrome.debug_port}",
        f"--remote-debugging-address={config.chrome.debug_address}",
        f"--user-data-dir={config.chrome.user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        f"--window-size={w},{h}",
    ]

    logger.info("Launching Chrome (window=%dx%d)", w, h)

    subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    for _ in range(CDP_RETRY_COUNT):
        if is_cdp_ready(config):
            return
        time.sleep(CDP_RETRY_INTERVAL)

    raise RuntimeError(
        f"CDP port {config.chrome.debug_url} not ready after "
        f"{CDP_RETRY_COUNT * CDP_RETRY_INTERVAL}s. "
        "Please fully exit all Chrome processes and try again."
    )
