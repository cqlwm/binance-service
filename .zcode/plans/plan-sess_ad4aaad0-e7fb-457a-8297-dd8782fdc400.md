## 目标

发帖前被动监控 Binance Square 页面加载时前端自动发起的 `userInfo` 请求，校验响应是否登录成功（`code == "000000"` 且 `success == true`）。失败时抛出 `LoginStateError` 中止发帖，避免后续 DOM 操作无谓失败。

## 设计原则

- 复用现有 `page.expect_response(...)` 模式（先例：`poster.py:_click_send_button` 拦截发帖 API）
- 配置驱动，URL 与超时入 `PosterConfig`（先例：`post_api_url` / `send_api_timeout_ms`）
- 复用 `get_or_create_page` 的导航入口，在 `page.goto` 外包裹 `expect_response`
- 自定义异常按业务模块分类（AGENTS.md § 七.3）

## 改动清单

### 1. 新增 `binance_service/login_state.py`

定义登录态校验异常 + 校验函数：

```python
class LoginStateError(Exception):
    """登录态失效或 userInfo 接口校验失败。"""

def verify_login_state(page: Page, user_info_api_url: str, timeout_ms: int) -> None:
    """页面加载期间被动监控 userInfo 请求并校验响应。

    用 page.expect_response 包裹 page.goto，捕获前端自动发起的
    userInfo 请求；校验 body['code']=='000000' 且 body['success'] is True。
    任一条件不满足或超时未捕获到请求，抛 LoginStateError。
    """
```

- 成功：记录 INFO 日志「登录态校验通过, userId=...」
- 失败：抛 `LoginStateError`，消息含具体原因（未捕获请求 / code 异常 / success=false / HTTP 状态码）
- 不吞异常（AGENTS.md § 七.2），日志 ERROR 级别记录后 raise

### 2. 修改 `binance_service/_config.py`

`PosterConfig` 新增两个字段（位置紧邻现有 `post_api_url`）：

```python
user_info_api_url: str
user_info_api_timeout_ms: int
```

`_parse_poster` 中追加两行解析（复用 `_require_str` / `_require_int`）。

### 3. 修改 `binance_service/_playwright.py`

`get_or_create_page` 增加可选参数 `user_info_api_url: str | None = None` 和 `user_info_api_timeout_ms: int | None = None`：

- 仅当 `user_info_api_url` 非空时，在新建 page 分支用 `page.expect_response(...)` 包裹 `page.goto`
- 复用现有 page 分支（URL 已匹配的 tab）跳过校验，保持原行为
- 复用 `_require`/`logger` 已有命名约定，保持函数行数 < 50

签名保持向后兼容（`screenshot.py` 调用不传新参数，行为不变）。

### 4. 修改 `binance_service/poster.py`

`create_post` 内调用 `get_or_create_page` 时传入 `config.user_info_api_url` 和 `config.user_info_api_timeout_ms`，让登录态校验在导航阶段执行。失败时 `LoginStateError` 自然向上抛出，调用方（CLI/service）收到明确异常。

### 5. 修改 `config.yaml` 与 `config.example.yaml`

`poster` 段新增：

```yaml
  # 用户信息接口端点（用于发帖前被动校验登录态）
  user_info_api_url: "https://www.binance.com/bapi/accounts/v1/private/account/user/userInfo"
  # userInfo 接口响应等待超时（毫秒）
  user_info_api_timeout_ms: 30000
```

### 6. 更新 `README.md`

- 「配置」章节的 `poster` 字段列表补充 `user_info_api_url`、`user_info_api_timeout_ms`
- 「常见问题 > 登录态过期」段落补充：发帖前会自动校验登录态，失败时给出明确 `LoginStateError` 提示，引导用户重新 `save-storage`

## 不改动

- CLI 层（`cli.py`）不改：`LoginStateError` 会从 `BinanceService.create_post` 自然冒泡，CLI 默认异常输出已足够清晰；如需更友好提示可在后续迭代再加
- `service.py` 不改：透传逻辑无需修改
- `screenshot.py` 不改：截图操作复用同一页面 tab，不触发登录态校验

## 校验逻辑细节

成功条件（全部满足）：
1. `expect_response` 在超时内捕获到 URL 含 `user_info_api_url` 的响应
2. `response.status == 200`
3. `body['code'] == '000000'`
4. `body['success'] is True`

失败场景与异常消息：
- 超时未捕获：`"userInfo 请求未在 {timeout_ms}ms 内出现，可能未登录或页面未发起该请求"`
- HTTP 非 200：`"userInfo 接口返回非 200 状态码: {status}"`
- code 异常：`"userInfo 接口 code 异常: {code}（预期 000000）"`
- success=false：`"userInfo 接口 success=false, message={message}"`

## 质量保障

- 类型注解完整（参数/返回值），无 `Any`（AGENTS.md § 四）
- 函数行数 ≤ 50（AGENTS.md § 二.2）
- 提交前跑 `uv run ruff format` + `uv run pyright binance_service` + `uv run pytest`
- 异常分类清晰，符合 AGENTS.md § 七（精准捕获、不静默吞异常、自定义异常按业务分类）

## 流程

```
create_post
  └─ get_or_create_page(target_url, user_info_api_url, timeout_ms)
       └─ if new tab:
            with page.expect_response(userInfoUrl, timeout):
                page.goto(target_url)
            └─ verify_login_state 校验 body
                  └─ 失败 → raise LoginStateError（中止）
  └─ _focus_input_box / ...（仅在登录态有效时执行）
```

## 影响面

- 新增 1 个模块（`login_state.py`）
- 修改 4 个文件（`_config.py` / `_playwright.py` / `poster.py` / 2 个 config + README）
- 对 screenshot 路径完全无影响（新参数默认 `None`）
- 对 CLI 调用方无破坏（异常向上冒泡，错误码由现有逻辑处理）