# Binance Service

通过 Chrome 自动化操作币安（Binance）的命令行工具集，复用本地 Chrome 登录态，**无需 API Key**。

## 功能

| 命令 | 说明 |
|------|------|
| `binance post` | 在币安广场（Binance Square）发布帖子，支持图文、行情卡片 |
| `binance screenshot` | 截取合约页（Futures）TradingView K 线图 |
| `binance postx` | 截图 + 发帖组合操作 |
| `binance save-storage` | 导出 Chrome 登录态，供 Headless 模式复用 |

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

### 1. 首次使用：导出登录态

```bash
# 确保 Chrome 已登录币安账号
# 导出登录态（cookies + localStorage）
uv run binance save-storage
```

登录态会保存到 `~/.debug_chrome/1/storage_state.json`，后续所有命令会自动加载。

> **注意**：登录态过期后需要重新导出。币安登录态通常有效期为数天到数周。

### 2. 发布帖子

```bash
# Headless 模式（默认，后台运行）
uv run binance post --base DOGE --content "UP UP UP" --image /path/to/image.jpg

# 有头模式（弹出 Chrome 窗口，调试用）
uv run binance post --base DOGE --content "UP UP UP" --headed
```

### 3. 截取 K 线图

```bash
# Headless 模式（默认）
uv run binance screenshot --symbol BTCUSDC

# 指定周期和输出路径
uv run binance screenshot --symbol ETHUSDC --timeframe 4h --output /tmp/eth_4h.png
```

### 4. 截图 + 发帖组合

```bash
uv run binance postx --base BTC --content "BTC looks bullish!"
```

## CLI 参考

### binance post — 发布帖子

```bash
uv run binance post --base <资产> --content "<正文>" [选项]
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
uv run binance post --base DOGE --content "DOGE to the moon!"

# 图文帖子
uv run binance post --base BTC --content "BTC 突破前高" --image /tmp/btc_chart.png

# 调试模式（排查问题时使用）
uv run binance post --base DOGE --content "test" --image test.png --debug
```

### binance screenshot — 合约页截图

截取合约页的 TradingView K 线图（合并 switch 区域和 chart 区域为一张完整图片）。

```bash
uv run binance screenshot --symbol <交易对> [选项]
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
uv run binance screenshot --symbol BTCUSDC

# 日线图
uv run binance screenshot --symbol BTCUSDC --timeframe 1d

# 指定输出路径
uv run binance screenshot --symbol ETHUSDC --timeframe 4h --output /tmp/eth_4h.png
```

### binance postx — 截图 + 发帖组合

先截取 K 线图，再附带截图发布帖子。

```bash
uv run binance postx --base <资产> --content "<正文>" [选项]
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--base` | 是 | 交易对基础资产，如 `DOGE`、`BTC` |
| `--content` | 是 | 帖子正文 |
| `--quote` | 否 | 报价币，默认 `USDT`（用于拼接交易对 symbol） |
| `--timeframe` | 否 | K 线周期，默认 `1h` |
| `--headed` | 否 | 以有头模式启动 Chrome（显示 GUI，调试用） |
| `--debug` | 否 | 启用调试模式 |

### binance save-storage — 导出登录态

通过 CDP 连接已有 Chrome，导出 cookies 和 localStorage，供自动化操作复用。

```bash
uv run binance save-storage [--url <页面URL>]
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--url` | 否 | 登录后导航到的页面，默认 `https://www.binance.com/zh-CN/square` |

登录态保存路径：`~/.debug_chrome/1/storage_state.json`

## 配置

配置文件位于 `~/.binance-service/.env`，可自定义 Chrome 路径和相关配置：

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
│   ├── __init__.py         # 公开 API
│   ├── _config.py          # 配置管理（从 ~/.binance-service/.env 加载）
│   ├── _chrome.py          # CDP Chrome 进程管理（仅 save-storage 使用）
│   ├── _playwright.py      # Playwright 浏览器生命周期管理
│   ├── storage_state.py    # 登录态序列化/反序列化（restore / save / CDP 导出）
│   ├── poster.py           # 发帖业务逻辑
│   ├── screenshot.py       # 截图业务逻辑
│   ├── cli.py              # CLI 入口
│   └── service.py          # BinanceService 封装
├── tests/
│   └── test_e2e.py         # 端到端集成测试
├── pyproject.toml          # 项目配置与依赖
├── uv.lock                 # 依赖锁定文件
└── README.md
```

## 常见问题

**Q: 截图模糊或只有黑色？**

截图前 Chrome 窗口被其他操作打断会导致渲染异常。脚本内置了图表加载等待（3s），若网络较慢可适当增加 `CHART_INITIAL_WAIT_MS` 和 `TIMEFRAME_REDRAW_WAIT_MS` 的值。

**Q: 帖子发送按钮一直灰色不可点击？**

- 确保帖子内容不为空
- 如果使用了 `--image`，确保图片已上传完成（检查 `~/.debug_chrome/screenshots/` 中的调试截图）
- 行情卡片（`$DOGE` 标签）需要正确匹配到交易对

**Q: 如何排查发帖失败问题？**

使用 `--debug` 模式，每一步都会截图保存到 `~/.debug_chrome/screenshots/`：

```bash
uv run binance post --base DOGE --content "test" --debug
```

**Q: 登录态过期了怎么办？**

重新运行 `binance save-storage` 导出最新登录态：

```bash
# 确保 Chrome 中已重新登录币安
uv run binance save-storage
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
uv run pyright binance_service/

# 运行测试
uv run pytest tests/
```
