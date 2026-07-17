# Binance Service

通过 Chrome 自动化操作币安（Binance）的命令行工具集，复用本地 Chrome 登录态，**无需 API Key**。

## 功能

| 命令 | 说明 |
|------|------|
| `binance post` | 在币安广场（Binance Square）发布帖子，支持图文、行情卡片 |
| `binance screenshot` | 截取合约页（Futures）TradingView K 线图 |
| `binance postx` | 截图 + 发帖组合操作 |
| `binance save-storage` | 导出 Chrome 登录态，供 Headless 模式复用 |

> 所有命令均需通过 `--config <path>` 指定 `config.yaml` 配置文件（见[配置](#配置)章节）。

## 工作原理

脚本通过 **Playwright** 启动 Chrome 实例，自动恢复之前保存的登录态。登录态管理分为两步：

```
┌──────────────────────────────────────────────────────────────────┐
│  步骤一：导出登录态（save-storage，仅首次/登录态过期时需要）       │
│                                                                    │
│  CLI (binance save-storage)                                        │
│    │                                                               │
│    ▼                                                               │
│  CDP 连接已有 Chrome ← 用户已手动登录 Binance                      │
│    │                                                               │
│    ▼                                                               │
│  导出 cookies + localStorage → storage_state.json                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  步骤二：自动化操作（post / screenshot / postx）                  │
│                                                                    │
│  CLI (binance post / screenshot / postx)                           │
│    │                                                               │
│    ▼                                                               │
│  Playwright launch Chrome (headless/headed)                        │
│    │                                                               │
│    ▼                                                               │
│  new_context(storage_state=storage_state.json) ← 恢复登录态        │
│    │                                                               │
│    ▼                                                               │
│  执行操作 → 写回 storage_state.json（更新 session）                │
└──────────────────────────────────────────────────────────────────┘
```

### 关键设计

- **`save-storage` 是唯一需要用户手动登录的命令**：通过 CDP 连接用户已有的 Chrome，用户需事先在 Chrome 中登录币安
- **其他命令完全由 Playwright 管理**：Playwright 自动启动/关闭 Chrome，无需依赖外部 Chrome 进程，无需固定的 CDP 端口
- **登录态自动持久化**：每次操作结束时自动写回 `storage_state.json`（含 `.bak` 备份），session 刷新后不会丢失

## 环境要求

- Python >= 3.13
- macOS，已安装 Google Chrome
- Chrome 中已登录币安账号（仅首次导出登录态时需要）

## 安装

```bash
# 创建虚拟环境并安装依赖
uv sync

# 安装 Playwright Chromium 浏览器引擎
uv run playwright install chromium
```

## 快速开始

### 0. 准备配置文件

```bash
# 复制配置模板，按本机环境修改路径字段
cp config.example.yaml config.yaml
```

`config.yaml` 中需根据实际情况调整 `chrome.bin_path`、`chrome.storage_state_path` 等路径字段。路径支持 `~` 展开为用户家目录。详见[配置](#配置)章节。

### 1. 首次使用：导出登录态

```bash
# 确保 Chrome 已登录币安账号
# 导出登录态（cookies + localStorage）
uv run binance --config config.yaml save-storage
```

登录态会保存到配置文件中 `chrome.storage_state_path` 指定的路径（默认 `~/.debug_chrome/1/storage_state.json`），后续所有命令会自动加载。

> **注意**：登录态过期后需要重新导出。币安登录态通常有效期为数天到数周。

### 2. 发布帖子

```bash
# Headless 模式（默认，后台运行）
uv run binance --config config.yaml post --base DOGE --content "UP UP UP" --image /path/to/image.jpg

# 有头模式（弹出 Chrome 窗口，调试用）
uv run binance --config config.yaml post --base DOGE --content "UP UP UP" --headed
```

### 3. 截取 K 线图

```bash
# Headless 模式（默认）
uv run binance --config config.yaml screenshot --symbol BTCUSDC

# 指定周期和输出路径
uv run binance --config config.yaml screenshot --symbol ETHUSDC --timeframe 4h --output /tmp/eth_4h.png
```

### 4. 截图 + 发帖组合

```bash
uv run binance --config config.yaml postx --base BTC --content "BTC looks bullish!"
```

## 库函数使用

除了命令行工具，本项目也提供 Python 库接口供其他代码直接调用。核心封装类为 `BinanceService`，支持自动管理浏览器生命周期。

### 快速示例

```python
from binance_service import BinanceService

# 使用 with 语句自动管理浏览器生命周期（推荐）
with BinanceService() as service:
    # 1. 截图 + 发帖组合操作（PostX，最常用）
    # 自动截取 K 线图，然后附带图片发布帖子
    service.create_postx(
        base_asset="BTC",
        content="BTC 突破关键阻力位，看涨！",
        quote="USDT",      # 可选，默认 USDT
        timeframe="1h",    # 可选，默认 1h
    )

    # 2. 单独发布帖子
    service.create_post(
        base_asset="DOGE",
        content="To the moon! 🚀",
        image_path="/path/to/image.jpg",  # 可选
    )

    # 3. 单独截取 K 线图
    screenshot_path = service.symbol_screenshot(
        symbol="ETHUSDT",
        timeframe="4h",
        output="/tmp/eth_4h.png",  # 可选
    )
```

### 手动管理浏览器

如需多次调用不同方法，可手动打开/关闭浏览器，避免反复启动 Chrome：

```python
service = BinanceService()
service.open()

try:
    # 多次操作共用一个浏览器实例
    service.create_postx(base_asset="BTC", content="First post")
    service.create_postx(base_asset="ETH", content="Second post")
finally:
    service.close()
```

### API 参考

#### `BinanceService` 类

| 方法 | 说明 |
|------|------|
| `create_postx(base_asset, content, quote="USDT", timeframe="1h", debug=False)` | **截图 + 发帖组合**，自动截取 K 线图并发布带图片的帖子 |
| `create_post(base_asset, content, image_path=None, debug=False)` | 发布 Binance Square 帖子 |
| `symbol_screenshot(symbol, timeframe="1h", output=None)` | 截取 Binance 合约 K 线图，返回截图路径 |

**`create_postx` 参数说明：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `base_asset` | `str` | 是 | 基础资产，如 `BTC`、`DOGE`、`ETH` |
| `content` | `str` | 是 | 帖子正文内容 |
| `quote` | `str` | 否 | 报价币，默认 `USDT`，用于拼接交易对 symbol |
| `timeframe` | `str` | 否 | K 线周期，默认 `1h`，可选值：`1m` / `5m` / `15m` / `30m` / `1h` / `2h` / `4h` / `1d` |
| `debug` | `bool` | 否 | 启用调试模式，默认 `False` |

> **注意**：使用库函数前，需先通过 `binance save-storage` 命令导出登录态。

## CLI 参考

所有子命令共享以下全局参数：

| 参数 | 必填 | 说明 |
|------|------|------|
| `--config` | 是 | `config.yaml` 配置文件路径 |
| `--headed` | 否 | 以有头模式启动 Chrome（显示 GUI，调试用） |
| `-v` / `--verbose` | 否 | 输出 DEBUG 级别日志 |

全局参数需写在子命令之前，例如：`binance --config config.yaml post ...`。

### binance post - 发布帖子

```bash
uv run binance --config config.yaml post --base <资产> --content "<正文>" [选项]
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--base` | 是 | 交易对基础资产，如 `DOGE`、`BTC` |
| `--content` | 是 | 帖子正文 |
| `--image` | 否 | 本地图片路径，支持 PNG / JPEG / GIF / WebP |
| `--debug` | 否 | 启用调试模式，每一步截图保存到配置中的 `poster.debug_screenshot_dir` |

示例：

```bash
# 纯文字帖子
uv run binance --config config.yaml post --base DOGE --content "DOGE to the moon!"

# 图文帖子
uv run binance --config config.yaml post --base BTC --content "BTC 突破前高" --image /tmp/btc_chart.png

# 调试模式（排查问题时使用）
uv run binance --config config.yaml post --base DOGE --content "test" --image test.png --debug
```

### binance screenshot — 合约页截图

截取合约页的 TradingView K 线图（合并 switch 区域和 chart 区域为一张完整图片）。

```bash
uv run binance --config config.yaml screenshot --symbol <交易对> [选项]
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--symbol` | 是 | 合约交易对，如 `BTCUSDC`、`ETHUSDC` |
| `--timeframe` | 否 | K 线周期：`5m`、`15m`、`1h`、`4h`、`1d`、`1w`，默认取配置中的 `screenshot.default_timeframe` |
| `--output` | 否 | 截图保存路径，默认 `./<symbol>_<timeframe>_chart.png` |

示例：

```bash
# 默认周期（取配置中的 default_timeframe）
uv run binance --config config.yaml screenshot --symbol BTCUSDC

# 日线图
uv run binance --config config.yaml screenshot --symbol BTCUSDC --timeframe 1d

# 指定输出路径
uv run binance --config config.yaml screenshot --symbol ETHUSDC --timeframe 4h --output /tmp/eth_4h.png
```

### binance postx — 截图 + 发帖组合

先截取 K 线图，再附带截图发布帖子。

```bash
uv run binance --config config.yaml postx --base <资产> --content "<正文>" [选项]
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--base` | 是 | 交易对基础资产，如 `DOGE`、`BTC` |
| `--content` | 是 | 帖子正文 |
| `--quote` | 否 | 报价币，默认 `USDT`（用于拼接交易对 symbol） |
| `--timeframe` | 否 | K 线周期，默认取配置中的 `screenshot.default_timeframe` |
| `--debug` | 否 | 启用调试模式 |

### binance save-storage - 导出登录态

通过 CDP 连接已有 Chrome，导出 cookies 和 localStorage，供自动化操作复用。

```bash
uv run binance --config config.yaml save-storage [--url <页面URL>]
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--url` | 否 | 登录后导航到的页面，默认 `https://www.binance.com/zh-CN/square` |

登录态保存路径：配置文件中 `chrome.storage_state_path` 指定的路径（默认 `~/.debug_chrome/1/storage_state.json`）

## 配置

项目通过单一 `config.yaml` 文件统一管理所有配置，不再使用环境变量或硬编码。仓库提供 `config.example.yaml` 模板，复制为 `config.yaml` 后按本机环境修改即可：

```bash
cp config.example.yaml config.yaml
```

配置文件结构如下（完整字段与注释见 `config.example.yaml`）：

| 分组 | 说明 | 关键字段 |
|------|------|---------|
| `chrome` | Chrome 路径与 CDP/登录态配置 | `bin_path`、`storage_state_path`、`user_data_dir`、`debug_address`、`debug_port` |
| `window` | 浏览器窗口尺寸 | `width`、`height` |
| `headless` | 是否无头模式运行 Chrome | `true` / `false` |
| `browser` | Playwright 启动行为 | `device_scale_factor`、`launch_args` |
| `poster` | 发帖运营参数 | `target_url`、`post_api_url`、`user_info_api_url`、`user_info_api_timeout_ms`、各类超时、`supported_image_extensions` |
| `screenshot` | 截图运营参数 | `base_url`、视口尺寸、`timeframe_choices`、`default_timeframe` |
| `cdp` | CDP 就绪探测轮询 | `retry_count`、`retry_interval` |

路径字段支持 `~` 展开为用户家目录。所有字段均为必填，缺失字段会在加载时报错并提示具体路径。

### 作为库使用

本项目也可被其他项目以函数调用方式使用：

```python
from binance_service import BinanceService, load_config

# 从 config.yaml 加载配置
app_config = load_config("config.yaml")

# 复用同一浏览器实例执行多次操作
with BinanceService(app_config=app_config) as svc:
    # 截图
    svc.symbol_screenshot(symbol="BTCUSDT", timeframe="1d")
    # 发帖
    svc.create_post(base_asset="BTC", content="BTC looks bullish!")
```

如需在运行时覆盖个别字段（如切换为有头模式），可用 `dataclasses.replace`：

```python
from dataclasses import replace
from binance_service import load_config

app_config = load_config("config.yaml")
app_config = replace(app_config, headless=False)
```

## 项目结构

```
binance-service/
├── binance_service/
│   ├── __init__.py         # 公开 API
│   ├── _config.py          # 配置管理（从 config.yaml 加载）
│   ├── _chrome.py          # CDP Chrome 进程管理（仅 save-storage 使用）
│   ├── _playwright.py      # Playwright 浏览器生命周期管理
│   ├── storage_state.py    # 登录态序列化/反序列化（restore / save / CDP 导出）
│   ├── poster.py           # 发帖业务逻辑
│   ├── screenshot.py       # 截图业务逻辑
│   ├── cli.py              # CLI 入口
│   └── service.py          # BinanceService 封装
├── tests/
│   └── test_e2e.py         # 端到端集成测试
├── config.example.yaml     # 配置文件模板
├── pyproject.toml          # 项目配置与依赖
├── uv.lock                 # 依赖锁定文件
└── README.md
```

## 常见问题

**Q: 截图模糊或只有黑色？**

截图前 Chrome 窗口被其他操作打断会导致渲染异常。脚本内置了图表加载等待，若网络较慢可在 `config.yaml` 中适当增加 `screenshot.chart_initial_wait_ms` 和 `screenshot.timeframe_redraw_wait_ms` 的值。

**Q: 帖子发送按钮一直灰色不可点击？**

- 确保帖子内容不为空
- 如果使用了 `--image`，确保图片已上传完成（检查 `~/.debug_chrome/screenshots/` 中的调试截图）
- 行情卡片（`$DOGE` 标签）需要正确匹配到交易对

**Q: 如何排查发帖失败问题？**

使用 `--debug` 模式，每一步都会截图保存到配置文件中 `poster.debug_screenshot_dir` 指定的目录：

```bash
uv run binance --config config.yaml post --base DOGE --content "test" --debug
```

**Q: 登录态过期了怎么办？**

发帖前会自动被动校验登录态：打开 Binance Square 页面时拦截前端发起的 `userInfo` 请求，校验 `code=="000000"` 且 `success==true`。校验失败会抛出 `LoginStateError` 并中止发帖，日志会给出具体原因（如 `code 异常`、`success=false`、`非 200 状态码`、`请求未出现`）。

此时需要重新运行 `binance save-storage` 导出最新登录态：

```bash
# 确保 Chrome 中已重新登录币安
uv run binance --config config.yaml save-storage
```

**Q: 支持 Windows / Linux 吗？**

目前仅测试了 macOS。Linux 和 Windows 理论上可用，需要在 `config.yaml` 中调整 `chrome.bin_path` 为对应平台的 Chrome 路径。

## 开发

```bash
# 安装开发依赖
uv sync

# 代码格式化
uv run ruff format binance_service/

# 类型检查
uv run pyright binance_service/

# 运行测试
uv run pytest tests/
```
