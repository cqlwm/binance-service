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

### 截图流程

截图 CLI 会在截图前临时缩放 Chrome 窗口至目标尺寸（500×800），确保 TradingView 图表以精确分辨率渲染：

```
获取原始窗口大小 → 缩至 500×800
  → 打开新标签 → 导航到合约页
  → 等待图表加载（3s）
  → 滚动到底部 → 隐藏滚动条
  → 截图 → 恢复窗口大小 → 关闭标签
```

## CLI

### binance-post — 发布帖子

```bash
uv run binance-post --base <资产> --content "<正文>" [--image <图片路径>]
```

| 参数       | 必填 | 说明                          |
| ---------- | ---- | ----------------------------- |
| `--base`   | 是   | 交易对基础资产，如 `DOGE`、`BTC` |
| `--content` | 是  | 帖子正文                      |
| `--image`  | 否   | 本地图片路径，支持 PNG / JPEG  |

示例：

```bash
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

示例：

```bash
uv run binance-screenshot --symbol BTCUSDC
uv run binance-screenshot --symbol ETHUSDC --timeframe 4h
uv run binance-screenshot --symbol BTCUSDC --timeframe 1d --output /tmp/btc_1d.png
```

### 配置

可在 `.env` 文件中指定 Chrome 可执行文件路径和用户数据目录：

```env
CHROME_BIN=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
USER_DATA_DIR=~/.debug_chrome/1/user-data
DEBUG_PORT=18800
```

## 项目结构

```
binance_service/
├── binance_service/
│   ├── __init__.py
│   ├── _chrome.py                     # Chrome 调试启动 & CDP 连接管理
│   ├── binance_poster.py              # 发帖 CLI
│   └── binance_futures_screenshot.py  # 合约页截图 CLI
├── pyproject.toml
└── README.md
```

## 常见问题

**Q: 截图模糊/只有黑色？**

确保截图前 Chrome 窗口未被其他操作打断。脚本内置了图表加载等待（3s），若网络较慢可适当增加 `SELECTOR_TIMEOUT_MS`。

**Q: 报错 `CDP port not ready`？**

关闭所有 Chrome 进程后重试：

```bash
pkill -f "Google Chrome"
uv run binance-screenshot --symbol BTCUSDC
```
