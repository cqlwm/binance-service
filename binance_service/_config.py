from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

logger = logging.getLogger("_config")


@dataclass(frozen=True)
class ChromeConfig:
    """Chrome CDP 调试与登录态存储相关配置。"""

    storage_state_path: str
    debug_address: str
    debug_port: int

    @property
    def debug_url(self) -> str:
        return f"http://{self.debug_address}:{self.debug_port}"

    @property
    def version_url(self) -> str:
        return f"{self.debug_url}/json/version"


@dataclass(frozen=True)
class WindowConfig:
    """浏览器窗口尺寸。"""

    width: int
    height: int


@dataclass(frozen=True)
class BrowserConfig:
    """Playwright 浏览器启动行为参数。"""

    device_scale_factor: float
    launch_args: tuple[str, ...]


@dataclass(frozen=True)
class PosterConfig:
    """Binance Square 发帖运营参数（CSS 选择器不入配置，与 DOM 强耦合）。"""

    target_url: str
    post_api_url: str
    user_info_api_url: str
    user_info_api_timeout_ms: int
    goto_timeout_ms: int
    symbol_dropdown_wait_seconds: int
    trade_widget_default_timeout_ms: int
    send_button_timeout_ms: int
    send_api_timeout_ms: int
    image_upload_poll_count: int
    image_upload_poll_interval: float
    supported_image_extensions: tuple[str, ...]
    debug_screenshot_dir: str


@dataclass(frozen=True)
class ScreenshotConfig:
    """合约 K 线截图运营参数。"""

    base_url: str
    window_width: int
    window_height: int
    goto_timeout_ms: int
    selector_timeout_ms: int
    timeframe_choices: tuple[str, ...]
    default_timeframe: str
    timeframe_redraw_wait_ms: int
    chart_initial_wait_ms: int


@dataclass(frozen=True)
class CdpConfig:
    """CDP 就绪探测的轮询参数。"""

    retry_count: int
    retry_interval: float


@dataclass(frozen=True)
class AppConfig:
    """顶层应用配置，聚合各子模块的配置片段。"""

    chrome: ChromeConfig
    window: WindowConfig
    headless: bool
    browser: BrowserConfig
    poster: PosterConfig
    screenshot: ScreenshotConfig
    cdp: CdpConfig


def _require(data: dict[str, object], key: str, path: str) -> object:
    """从 data 取 key，缺失时抛出带配置路径提示的 KeyError。"""
    if key not in data:
        raise KeyError(f"Missing config field '{path}.{key}'")
    return data[key]


def _require_dict(data: dict[str, object], key: str, path: str) -> dict[str, object]:
    value = _require(data, key, path)
    if not isinstance(value, dict):
        raise TypeError(f"Config field '{path}.{key}' must be a mapping, got {type(value).__name__}")
    return cast(dict[str, object], value)


def _require_str(data: dict[str, object], key: str, path: str) -> str:
    value = _require(data, key, path)
    if not isinstance(value, str):
        raise TypeError(f"Config field '{path}.{key}' must be a string, got {type(value).__name__}")
    return value


def _require_int(data: dict[str, object], key: str, path: str) -> int:
    value = _require(data, key, path)
    # YAML 中整数已是 int，但兼容 bool（bool 是 int 子类，需排除）
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Config field '{path}.{key}' must be an integer, got {type(value).__name__}")
    return value


def _require_float(data: dict[str, object], key: str, path: str) -> float:
    value = _require(data, key, path)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"Config field '{path}.{key}' must be a number, got {type(value).__name__}")
    return float(value)


def _require_bool(data: dict[str, object], key: str, path: str) -> bool:
    value = _require(data, key, path)
    if not isinstance(value, bool):
        raise TypeError(f"Config field '{path}.{key}' must be a boolean, got {type(value).__name__}")
    return value


def _require_str_list(data: dict[str, object], key: str, path: str) -> tuple[str, ...]:
    value = _require(data, key, path)
    if not isinstance(value, list):
        raise TypeError(f"Config field '{path}.{key}' must be a list, got {type(value).__name__}")
    items = cast(list[object], value)
    result: list[str] = []
    for i, item in enumerate(items):
        if not isinstance(item, str):
            raise TypeError(f"Config field '{path}.{key}[{i}]' must be a string, got {type(item).__name__}")
        result.append(item)
    return tuple(result)


def _expand(path: str) -> str:
    """展开路径中的 ~ 为用户家目录。"""
    return os.path.expanduser(path)


def _parse_chrome(data: dict[str, object]) -> ChromeConfig:
    p = "chrome"
    section = _require_dict(data, p, p)
    return ChromeConfig(
        storage_state_path=_expand(_require_str(section, "storage_state_path", p)),
        debug_address=_require_str(section, "debug_address", p),
        debug_port=_require_int(section, "debug_port", p),
    )


def _parse_window(data: dict[str, object]) -> WindowConfig:
    p = "window"
    section = _require_dict(data, p, p)
    return WindowConfig(
        width=_require_int(section, "width", p),
        height=_require_int(section, "height", p),
    )


def _parse_browser(data: dict[str, object]) -> BrowserConfig:
    p = "browser"
    section = _require_dict(data, p, p)
    return BrowserConfig(
        device_scale_factor=_require_float(section, "device_scale_factor", p),
        launch_args=_require_str_list(section, "launch_args", p),
    )


def _parse_poster(data: dict[str, object]) -> PosterConfig:
    p = "poster"
    section = _require_dict(data, p, p)
    return PosterConfig(
        target_url=_require_str(section, "target_url", p),
        post_api_url=_require_str(section, "post_api_url", p),
        user_info_api_url=_require_str(section, "user_info_api_url", p),
        user_info_api_timeout_ms=_require_int(section, "user_info_api_timeout_ms", p),
        goto_timeout_ms=_require_int(section, "goto_timeout_ms", p),
        symbol_dropdown_wait_seconds=_require_int(section, "symbol_dropdown_wait_seconds", p),
        trade_widget_default_timeout_ms=_require_int(section, "trade_widget_default_timeout_ms", p),
        send_button_timeout_ms=_require_int(section, "send_button_timeout_ms", p),
        send_api_timeout_ms=_require_int(section, "send_api_timeout_ms", p),
        image_upload_poll_count=_require_int(section, "image_upload_poll_count", p),
        image_upload_poll_interval=_require_float(section, "image_upload_poll_interval", p),
        supported_image_extensions=_require_str_list(section, "supported_image_extensions", p),
        debug_screenshot_dir=_expand(_require_str(section, "debug_screenshot_dir", p)),
    )


def _parse_screenshot(data: dict[str, object]) -> ScreenshotConfig:
    p = "screenshot"
    section = _require_dict(data, p, p)
    return ScreenshotConfig(
        base_url=_require_str(section, "base_url", p),
        window_width=_require_int(section, "window_width", p),
        window_height=_require_int(section, "window_height", p),
        goto_timeout_ms=_require_int(section, "goto_timeout_ms", p),
        selector_timeout_ms=_require_int(section, "selector_timeout_ms", p),
        timeframe_choices=_require_str_list(section, "timeframe_choices", p),
        default_timeframe=_require_str(section, "default_timeframe", p),
        timeframe_redraw_wait_ms=_require_int(section, "timeframe_redraw_wait_ms", p),
        chart_initial_wait_ms=_require_int(section, "chart_initial_wait_ms", p),
    )


def _parse_cdp(data: dict[str, object]) -> CdpConfig:
    p = "cdp"
    section = _require_dict(data, p, p)
    return CdpConfig(
        retry_count=_require_int(section, "retry_count", p),
        retry_interval=_require_float(section, "retry_interval", p),
    )


def load_config(path: str | Path) -> AppConfig:
    """从 YAML 配置文件加载 AppConfig。

    Args:
        path: YAML 配置文件路径。

    Returns:
        解析后的 AppConfig 实例。

    Raises:
        FileNotFoundError: 配置文件不存在。
        KeyError: 缺少必填字段（错误信息含字段路径）。
        TypeError: 字段类型不匹配。
    """
    config_path = Path(path).expanduser()
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise TypeError(f"Config root must be a mapping, got {type(raw).__name__}")

    data = cast(dict[str, object], raw)

    return AppConfig(
        chrome=_parse_chrome(data),
        window=_parse_window(data),
        headless=_require_bool(data, "headless", "root"),
        browser=_parse_browser(data),
        poster=_parse_poster(data),
        screenshot=_parse_screenshot(data),
        cdp=_parse_cdp(data),
    )
