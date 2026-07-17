# 将配置统一到 config.yaml 的重构计划

## 目标
移除 `.env` 环境变量与代码硬编码两条配置路径，统一为 `config.yaml` → `load_config(path)` → `AppConfig`（frozen dataclass 树）→ 业务模块。CSS 选择器保留为代码常量；调用方完全显式构造 `AppConfig`；CLI 通过必填 `--config` 指定配置文件。

## 架构

```
config.yaml ──load_config(path)──▶ AppConfig(frozen dataclass 树)
                                         │
        ┌────────────────────────────────┼───────────────────────────┐
        ▼                                ▼                           ▼
  BinanceService(app_config)     poster.create_post(        screenshot.symbol_screenshot(
                                   browser, poster_cfg, …)    browser, screenshot_cfg, …)
        │                                │                           │
        ▼                                ▼                           ▼
  connect_browser(app_config)     config 片段注入            config 片段注入
  (_chrome 用 cdp 片段)
```

## 数据结构设计（`_config.py`）

```python
@dataclass(frozen=True)
class ChromeConfig:           # 路径类
    bin_path: str
    user_data_dir: str
    storage_state_path: str
    debug_address: str
    debug_port: int
    # properties: debug_url, version_url（保留）

@dataclass(frozen=True)
class WindowConfig:
    width: int
    height: int

@dataclass(frozen=True)
class BrowserConfig:          # 浏览器启动行为
    device_scale_factor: float
    launch_args: tuple[str, ...]

@dataclass(frozen=True)
class PosterConfig:           # 发帖运营参数（选择器不入）
    target_url: str
    post_api_url: str
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
class ScreenshotConfig:       # 截图运营参数
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
    retry_count: int
    retry_interval: float

@dataclass(frozen=True)
class AppConfig:
    chrome: ChromeConfig
    window: WindowConfig
    headless: bool
    browser: BrowserConfig
    poster: PosterConfig
    screenshot: ScreenshotConfig
    cdp: CdpConfig

def load_config(path: str | Path) -> AppConfig: ...
```

**关键变更**：
- 删除 `ChromeConfig.default()` classmethod 与 `AppConfig` 字段的默认值（消除 mutable-default 反模式）。
- 删除 import 时的 `dotenv.load_dotenv()` 副作用。
- 所有字段无默认值，强制完整提供；`load_config` 严格读取，缺失字段报清晰错误。

## 执行步骤

### 1. 依赖变更
- `uv remove python-dotenv`
- `uv add pyyaml`
- 顺带删除死常量 `TRADE_WIDGET_SEARCH_TIMEOUT_MS`（poster.py 中已定义但从未引用）。

### 2. 重构 `binance_service/_config.py`
- 用 `yaml.safe_load` 实现 `load_config(path)`，按上述结构构造 `AppConfig`。
- 路径字段支持 `~` 展开（`os.path.expanduser`），修正当前 `.env` 中 `~` 不展开的隐患。
- 移除所有 `os.getenv` / `dotenv` / `CONFIG_DIR` / `_env_path` 逻辑。
- 保留 `debug_url`/`version_url` properties。
- `load_config` 缺字段时抛 `KeyError` 并提示完整路径。

### 3. 新增 `config.example.yaml`（仓库根）
完整模板，分组与 dataclass 对应，含中文注释说明每项用途。替换 `.env.example`。基于当前代码中的实际默认值填充，确保迁移零行为变更。

### 4. 重构 `binance_service/poster.py`
- 删除全部模块级常量（除 CSS 选择器相关字符串，后者保留为模块私有常量或函数内字面量）。
- `create_post(browser, config: PosterConfig, base_asset, content, image_path, debug)`：新增 `config` 参数。
- 各 `_xxx` 辅助函数改为接收所需 config 字段（或直接接收 `config`），不再引用模块全局。
- `DEBUG_SCREENSHOT_DIR` → `config.debug_screenshot_dir`。
- `_paste_image` 内硬编码的 `timeout=30000` 改用 `config.send_api_timeout_ms`（统一，消除重复魔法数）。
- 保留 CSS 选择器字面量（`div.json-article-editor`、`.tippy-box ...`、`.short-editor-inner button` 等）。

### 5. 重构 `binance_service/screenshot.py`
- 删除模块级运营常量；保留 `SWITCH_UI_SELECTOR`/`CHART_UI_SELECTOR` 选择器常量。
- `symbol_screenshot(browser, config: ScreenshotConfig, symbol, timeframe, output_path)`：新增 `config`。
- `TIMEFRAME_CHOICES`/`DEFAULT_TIMEFRAME` 移入 `ScreenshotConfig`；`service.py` 改为从 `app_config.screenshot` 读取。
- 保留 `wait_for_timeout(500)` 这类 DOM 交互短等待为代码字面量（不入配置）。

### 6. 重构 `binance_service/_chrome.py`
- 删除 `CDP_RETRY_COUNT`/`CDP_RETRY_INTERVAL` 模块常量。
- `ensure_cdp_chrome_running(config)` 内部改用 `config.cdp.retry_count` / `config.cdp.retry_interval`。
- `is_cdp_ready` 内 `urlopen(timeout=1)` 保留为代码常量（网络级健康检查超时，非运营参数）。

### 7. 重构 `binance_service/_playwright.py`
- `connect_browser(config)` 内 `device_scale_factor=2` → `config.browser.device_scale_factor`。
- `args=["--no-first-run", "--no-default-browser-check"]` → `list(config.browser.launch_args)`。
- `get_or_create_page` 逻辑不变。

### 8. 重构 `binance_service/service.py`
- `BinanceService.__init__(self, app_config: AppConfig, browser: Browser | None = None)`：移除 `app_config` 默认值（完全显式）。
- `create_post` 调用 `poster.create_post(browser, self._app_config.poster, …)`。
- `symbol_screenshot` 调用 `screenshot.symbol_screenshot(browser, self._app_config.screenshot, …)`，timeframe 校验用 `self._app_config.screenshot.timeframe_choices`，默认值用 `self._app_config.screenshot.default_timeframe`。
- `create_postx` 的 `quote="USDT"`/`timeframe="1h"` 默认值：timeframe 默认改读 config；quote 保留参数默认（CLI 覆盖）。

### 9. 重构 `binance_service/cli.py`
- 顶层 `--config <path>` 必填参数（`required=True`）；加载：`app_config = load_config(args.config)`。
- `--headed` 仍覆盖：`app_config = replace(app_config, headless=not args.headed)`（用 `dataclasses.replace`）。
- 删除 `_build_app_config`，改为 `load_config` + `replace`。
- `cmd_save_storage` 用加载的 `app_config`。
- 保留 `LOG_FORMAT`/`LOG_DATE_FORMAT` 为代码常量（日志格式非业务运营参数）。

### 10. 更新 `binance_service/__init__.py`
- 导出 `load_config`；移除 `ChromeConfig`（不再有 `.default()`，作为内部细节；若外部需要仍可从 `_config` 导入）。最终 `__all__ = ["AppConfig", "BinanceService", "connect_browser", "load_config"]`。

### 11. 更新 `tests/test_e2e.py`
- 通过 `load_config(Path(__file__).parent.parent / "config.example.yaml")` 加载配置（同时验证 load_config），再用 `replace` 调整 storage_state_path 指向本机真实文件。
- `BinanceService(app_config)` 显式传参。

### 12. 更新 `README.md`
- 配置章节：移除 `.env` 说明，改为 `config.yaml` 使用说明（复制 `config.example.yaml` → 编辑路径 → CLI 传 `--config`）。
- 库用法示例：`app_config = load_config("config.yaml")` → `with BinanceService(app_config) as svc:`。
- 更新所有 CLI 命令示例加上 `--config config.yaml`。

### 13. 清理
- 删除 `.env.example`（仓库根）。
- `.gitignore` 中 `.env` 行可保留（无害）或移除。
- 用户家目录 `~/.binance-service/.env` 不动（属用户环境）。

## 验证
1. `uv run ruff format && uv run ruff check` —— 格式与 lint。
2. `uv run pyright binance_service` —— strict 类型检查通过（AGENTS.md 要求）。
3. `uv run pytest`（e2e 需真实登录态与 Chrome，可能跳过/失败，确认非配置问题即可）。
4. 手动 `uv run python -c "from binance_service import load_config; load_config('config.example.yaml')"` 验证加载。

## 不在本次范围
- `build/`、`egg-info/` 陈旧构建产物（gitignored，不处理）。
- `storage_state.py` 的 `_get_or_create_page` 与 `_playwright.py` 的 `get_or_create_page` 重复（独立重构项）。
- `typings/cloakbrowser`（与本流程无关）。