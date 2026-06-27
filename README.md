# Binance Service

通过 Chrome 自动化操作币安（Binance）的命令行工具集，复用本地 Chrome 登录态，**无需 API Key**。

## 功能

| 命令 | 说明 |
|------|------|
| `binance-post` | 在币安广场（Binance Square）发布帖子，支持图文、行情卡片 |
| `binance-screenshot` | 截取合约页（Futures）TradingView K 线图 |
| `binance-save-storage` | 导出 Chrome 登录态，供 Headless 模式复用 |

## 工作原理

脚本通过 **Chrome DevTools Protocol（CDP）** 连接到 Chrome 浏览器，在现有窗口中执行页面操作。无需手动登录或管理 Cookie。

```
┌─────────────────────────────────────────────────────────────┐
│  CLI (binance-post / binance-screenshot)                    │
│    │                                                        │
│    ▼                                                        │
│  Playwright connect_over_cdp(127.0.0.1:18800)               │
│    │                                                        │
│    ▼                                                        │
│  Chrome (--remote-debugging-port=18800)                     │
│    │                                                        │
│    ▼                                                        │
│  Binance.com (复用本地登录态，无需 API Key)                    │
└─────────────────────────────────────────────────────────────┘
```

### 两种运行模式

- **Headless 模式**（默认）：Chrome 在后台运行，不弹出 GUI 窗口，适合定时任务、CI/CD 或服务器环境。**推荐生产环境使用**。
- **Headed 模式**（`--headed`）：连接本地已有的 Chrome 窗口，可见操作过程，适合调试和手动确认。

## 环境要求

- Python >= 3.13
- macOS，已安装 Google Chrome
- Chrome 中已登录币安账号

## 安装

```bash
# 创建虚拟环境并安装依赖
uv sync

# 安装 Playwright Chromium 浏览器引擎
uv run playwright install chromium
```

## 快速开始

### 1. 首次使用：导出登录态（Headless 模式需要）

如果使用 Headless 模式，需要先通过 Headed 模式导出登录态：

```bash
# 确保 Chrome 已登录币安账号
# 导出登录态（cookies + localStorage）
uv run binance-save-storage
```

登录态会保存到 `~/.debug_chrome/1/storage_state.json`，Headless 模式会自动加载。

> **注意**：登录态过期后需要重新导出。币安登录态通常有效期为数天到数周。

### 2. 发布帖子

```bash
# Headless 模式（默认，无需额外参数）
uv run binance-post --base DOGE --content "UP UP UP" --image /path/to/image.jpg

# 有头模式（弹出 Chrome 窗口，调试用）
uv run binance-post --base DOGE --content "UP UP UP" --image /path/to/image.jpg --headed
```

### 3. 截取 K 线图

```bash
# Headless 模式（默认，无需额外参数）
uv run binance-screenshot --symbol BTCUSDC

# 指定周期和输出路径
uv run binance-screenshot --symbol ETHUSDC --timeframe 4h --output /tmp/eth_4h.png
```

## CLI 参考

### binance-post — 发布帖子

```bash
uv run binance-post --base <资产> --content "<正文>" [选项]
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--base` | 是 | 交易对基础资产，如 `DOGE`、`BTC` |
| `--content` | 是 | 帖子正文 |
| `--image` | 否 | 本地图片路径，支持 PNG / JPEG / GIF / WebP |
| `--headed` | 否 | 以有头模式启动 Chrome（显示 GUI，调试用） |
| `--debug` | 否 | 启用调试模式，每一步截图保存到 `~/.debug_chrome/screenshots/` |

示例：

```bash
# 纯文字帖子
uv run binance-post --base DOGE --content "DOGE to the moon!"

# 图文帖子
uv run binance-post --base BTC --content "BTC 突破前高" --image /tmp/btc_chart.png

# 调试模式（排查问题时使用）
uv run binance-post --base DOGE --content "test" --image test.png --debug
```

### binance-screenshot — 合约页截图

截取合约页的 TradingView K 线图（合并 switch 区域和 chart 区域为一张完整图片）。

```bash
uv run binance-screenshot --symbol <交易对> [选项]
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--symbol` | 是 | 合约交易对，如 `BTCUSDC`、`ETHUSDC` |
| `--timeframe` | 否 | K 线周期：`5m`、`15m`、`1h`、`4h`、`1d`、`1w`，默认 `1h` |
| `--output` | 否 | 截图保存路径，默认 `./<symbol>_<timeframe>_chart.png` |
| `--headed` | 否 | 以有头模式启动 Chrome（显示 GUI，调试用） |

示例：

```bash
# 默认 1h 周期
uv run binance-screenshot --symbol BTCUSDC

# 日线图
uv run binance-screenshot --symbol BTCUSDC --timeframe 1d

# 指定输出路径
uv run binance-screenshot --symbol ETHUSDC --timeframe 4h --output /tmp/eth_4h.png
```

### binance-save-storage — 导出登录态

从 Headed Chrome 导出 cookies 和 localStorage，供 Headless 模式复用。

```bash
uv run binance-save-storage [--url <页面URL>]
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--url` | 否 | 登录后导航到的页面，默认 `https://www.binance.com/zh-CN/square` |

登录态保存路径：`~/.debug_chrome/1/storage_state.json`

## 配置

配置文件位于 `~/.news-service/.env`，可自定义 Chrome 路径和调试端口：

```env
# Chrome 可执行文件路径
CHROME_BIN=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome

# 登录态存储路径（必需，用于恢复浏览器登录会话）
STORAGE_STATE_PATH=~/.debug_chrome/1/storage_state.json

# save-storage 命令使用的 Chrome 用户数据目录
USER_DATA_DIR=~/.debug_chrome/1/user-data

# save-storage 命令使用的 CDP 调试地址和端口
DEBUG_ADDRESS=127.0.0.1
DEBUG_PORT=18800
```

所有配置均有默认值，不配置 `.env` 也可直接使用。

## 项目结构

```
binance-service/
├── binance_service/
│   ├── __init__.py         # 公开 API（AppConfig, ChromeConfig, post, take_futures_screenshot）
│   ├── _config.py          # 配置管理（从 ~/.binance-service/.env 加载，dataclass 配置模型）
│   ├── _chrome.py          # Chrome 进程管理（CDP 检测/启动）
│   ├── _playwright.py      # Playwright 连接管理（CDP 连接 / Headless 启动 / 登录态恢复）
│   ├── poster.py           # 发帖业务逻辑（输入内容、图片粘贴、行情卡片、发送）
│   ├── screenshot.py       # 截图业务逻辑（导航、切换周期、合并截图）
│   └── save_storage.py     # 登录态导出 CLI
├── pyproject.toml          # 项目配置与依赖
├── uv.lock                 # 依赖锁定文件
└── README.md
```

## 常见问题

**Q: 截图模糊或只有黑色？**

截图前 Chrome 窗口被其他操作打断会导致渲染异常。脚本内置了图表加载等待（3s），若网络较慢可适当增加 `CHART_INITIAL_WAIT_MS` 和 `TIMEFRAME_REDRAW_WAIT_MS` 的值。

**Q: 报错 `CDP port not ready`？**

Chrome 调试端口未就绪。完全退出所有 Chrome 进程后重试：

```bash
pkill -f "Google Chrome"
uv run binance-screenshot --symbol BTCUSDC
```

**Q: Headless 模式提示用户数据目录被锁定？**

Headed 模式和 Headless 模式使用不同的用户数据目录（`user-data` vs `headless-user-data`），正常情况下不会冲突。如果仍有锁冲突，检查是否有残留 Chrome 进程：

```bash
lsof -ti :18800 | xargs kill
```

**Q: 帖子发送按钮一直灰色不可点击？**

- 确保帖子内容不为空
- 如果使用了 `--image`，确保图片已上传完成（检查 `~/.debug_chrome/screenshots/` 中的调试截图）
- 行情卡片（`$DOGE` 标签）需要正确匹配到交易对

**Q: 如何排查发帖失败问题？**

使用 `--debug` 模式，每一步都会截图保存到 `~/.debug_chrome/screenshots/`：

```bash
uv run binance-post --base DOGE --content "test" --debug
```

**Q: 登录态过期了怎么办？**

重新运行 `binance-save-storage` 导出最新登录态：

```bash
# 确保 Chrome 中已重新登录币安
uv run binance-save-storage
```

**Q: 支持 Windows / Linux 吗？**

目前仅测试了 macOS。Linux 和 Windows 理论上可用，需要调整 Chrome 路径配置。

## 开发

```bash
# 安装开发依赖
uv sync

# 代码格式化
uv run ruff format binance_service/

# 类型检查
uv run mypy binance_service/

# 运行测试
uv run pytest tests/
```
