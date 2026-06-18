# Binance Service

通过 Chrome 自动化操作币安（Binance）的命令行工具集，复用本地 Chrome 登录态，无需 API Key。

提供两个 CLI：
- **binance-post** — 在币安广场发布帖子
- **binance-screenshot** — 截取合约页 K 线图

## 环境要求

- Python >= 3.13
- macOS，已安装 Google Chrome
- Chrome 用户数据目录中已登录币安账号

## 安装

```bash
uv sync
uv run playwright install chromium
```

## 工作原理

脚本通过 **Chrome DevTools Protocol（CDP）** 连接到以调试模式运行的 Chrome，在现有窗口中执行页面操作：

```
CLI  → Playwright connect_over_cdp(127.0.0.1:18800)
     → Chrome（--remote-debugging-port=18800, --user-data-dir=~/.debug_chrome/1/user-data）
```

首次运行时自动以调试模式启动 Chrome，复用用户数据目录中的登录态。无需手动登录或管理 Cookie。

**推荐使用 Headless 模式**（`--headless`）：Chrome 在后台运行，不弹出 GUI 窗口，适合定时任务、CI/CD 或服务器环境。Headless 模式下所有功能（发帖、截图）完全正常运作。

## CLI

### binance-post — 发布帖子

```bash
uv run binance-post --base <资产> --content "<正文>" [--image <图片路径>]
```

| 参数         | 必填 | 说明                            |
| ------------ | ---- | ------------------------------- |
| `--base`     | 是   | 交易对基础资产，如 `DOGE`、`BTC`   |
| `--content`  | 是   | 帖子正文                        |
| `--image`    | 否   | 本地图片路径，支持 PNG / JPEG    |
| `--headless` | 否   | 以无头模式启动 Chrome（推荐）      |

示例：

```bash
# 推荐：Headless 模式（无 GUI）
uv run binance-post --base DOGE --content "UP UP UP" --image /Users/li/Downloads/1.jpg --headless

# 有头模式（弹出 Chrome 窗口）
uv run binance-post --base DOGE --content "UP UP UP" --image /Users/li/Downloads/1.jpg
```

### binance-screenshot — 合约页截图

截取 `div#chart` 元素的内容（币安合约 TradingView K 线图）。

```bash
uv run binance-screenshot --symbol <交易对> [--timeframe <周期>] [--output <路径>]
```

| 参数          | 必填 | 说明                                                                                  |
| ------------- | ---- | ------------------------------------------------------------------------------------- |
| `--symbol`    | 是   | 合约交易对，如 `BTCUSDC`、`ETHUSDC`                                                    |
| `--timeframe` | 否   | K 线时间周期，可选 `5m`、`15m`、`1h`、`4h`、`1d`、`1w`，默认 `1h`，截图前自动切换          |
| `--output`    | 否   | 截图保存路径，默认 `./<symbol>_<timeframe>_chart.png`                                  |
| `--headless`  | 否   | 以无头模式启动 Chrome（推荐）                                                            |

示例：

```bash
# 推荐：Headless 模式（无 GUI）
uv run binance-screenshot --symbol BTCUSDC --headless
uv run binance-screenshot --symbol ETHUSDC --timeframe 4h --headless
uv run binance-screenshot --symbol BTCUSDC --timeframe 1d --output /tmp/btc_1d.png --headless

# 有头模式（弹出 Chrome 窗口）
uv run binance-screenshot --symbol BTCUSDC
```

## 配置

可在项目根目录的 `.env` 文件中指定 Chrome 可执行文件路径和用户数据目录：

```env
CHROME_BIN=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
USER_DATA_DIR=~/.debug_chrome/1/user-data
DEBUG_PORT=18800
```

所有配置均有默认值，不配置 `.env` 也可直接使用。

## 项目结构

```
binance_service/
├── __init__.py                # 公开 API
├── _config.py                 # 配置管理（从 .env 加载）
├── _chrome.py                 # Chrome 进程管理（启动/检测 CDP）
├── _playwright.py             # Playwright 连接管理（connect + page）
├── poster.py                  # 发帖业务逻辑
└── screenshot.py              # 截图业务逻辑
```

## 常见问题

**Q: 截图模糊/只有黑色？**

确保截图前 Chrome 窗口未被其他操作打断。脚本内置了图表加载等待（3s），若网络较慢可适当增加 `CHART_INITIAL_WAIT_MS`。

**Q: 报错 `CDP port not ready`？**

关闭所有 Chrome 进程后重试：

```bash
pkill -f "Google Chrome"
uv run binance-screenshot --symbol BTCUSDC
```
