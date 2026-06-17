from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import dotenv

logger = logging.getLogger("chrome")

dotenv.load_dotenv()

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
USER_DATA_DIR = "/Users/li/.debug_chrome/1/user-data"
DEBUG_ADDRESS = "127.0.0.1"
DEBUG_PORT = 18800
DEBUG_URL = f"http://{DEBUG_ADDRESS}:{DEBUG_PORT}"
VERSION_URL = f"{DEBUG_URL}/json/version"


def is_cdp_ready() -> bool:
    try:
        with urlopen(VERSION_URL, timeout=1):
            return True
    except URLError:
        return False


def ensure_debug_chrome_running(headless: bool = False, window_size: str | None = None) -> None:
    chrome_path = Path(CHROME_BIN)
    if not chrome_path.exists():
        raise FileNotFoundError(f"Local ChromeBrowser not found: {chrome_path}")

    if is_cdp_ready():
        logger.info(f"Debug port ready: {VERSION_URL}.")
        return

    args = [
        CHROME_BIN,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--remote-debugging-address={DEBUG_ADDRESS}",
        f"--user-data-dir={USER_DATA_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if headless:
        args.append("--headless=new")
        if not window_size:
            args.append("--window-size=1920,1080")
    if window_size:
        args.append(f"--window-size={window_size}")

    subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    for _ in range(20):
        if is_cdp_ready():
            return
        time.sleep(0.5)

    raise RuntimeError(
        f"CDP port not ready: {VERSION_URL}."
        " Please fully exit all Chrome processes and try again, "
        "or manually launch a standalone instance with --user-data-dir."
    )
