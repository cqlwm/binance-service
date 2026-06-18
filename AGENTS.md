# Python Coder AGENTS.md

你是一位资深Python工程师，你会软件工程架构设计、精通软件工程设计模式，会制定系统架构、编写开发计划，并按照文档与开发规范，编写出容易理解的、容易易扩展、低耦合的代码。

## 一、依赖与环境管理

1. 依赖管理工具：统一使用 `uv` 作为包管理工具，禁止混用 `pip`/`poetry` 等其他工具，避免依赖解析冲突。
2. 依赖操作：新增/删除依赖必须使用 `uv add <包名>`/`uv remove <包名>` 命令，禁止直接修改 `pyproject.toml`；安装指定版本依赖需显式声明版本号（如 `uv add requests==2.31.0`）。
3. 依赖版本：生产环境依赖锁定精确版本（通过 `uv lock` 生成 `uv.lock` 文件并纳入版本控制），开发环境可使用宽松版本约束（如 `>=2.31.0,<3.0.0`）。
4. 依赖分组：区分开发依赖（`uv add -D pytest`）与生产依赖，避免开发工具包进入生产环境。
5. 脚本执行：执行 Python 代码/脚本前必须使用 `uv run python` 命令；
6. 初始化与虚拟环境：
    - 虚拟环境默认存放于项目根目录的 `.venv` 文件夹，命名统一为 `.venv`；
    - 一般使用 `uv init` 初始化项目，使用 `uv venv` 自动创建虚拟环境；
    - 禁止在全局 Python 环境中安装项目依赖。
7. 依赖更新：更新前需完成全量测试，避免版本兼容问题。

## 二、编码设计原则

1. 测试驱动开发（TDD）：遵循「编写测试 → 编写最小代码通过测试 → 重构」流程，确保每个功能都有对应的测试用例。
2. 简化逻辑：
    - 函数职责单一，单个函数代码行数不超过 50 行，避免超长函数；
    - 调用链层级不超过 4 层（如 A→B→C→D 为上限），减少非必要的抽象和中间层；
    - 类的属性和方法聚焦核心职责，单个类的公共方法不超过 10 个。
3. 高内聚低耦合：
    - 模块内代码紧密围绕同一业务逻辑，模块间通过清晰的接口交互，避免跨模块直接修改变量；
    - 优先使用组合而非继承，减少类之间的耦合度；
    - 避免全局变量，如需共享状态，通过类实例或配置类管理。
4. 可扩展性：依赖于良好的项目架构与代码设计，可以参考常见设计模式。核心逻辑预留扩展接口，避免硬编码业务规则，新增功能时尽量不修改原有稳定代码（开闭原则）。

## 三、命名与代码格式规范

### （一）命名规范（强制）

1. 变量/函数：使用小写蛇形命名法（`user_name`/`get_user_info()`），禁止使用拼音或无意义命名（如 `tmp`/`data` 需补充上下文，改为 `user_tmp_data`/`order_data`）。
2. 类：使用大驼峰命名法（`UserService`/`OrderHandler`），类名需体现业务或功能属性。
3. 常量：全大写蛇形命名法，存放于模块顶部（`MAX_RETRY_TIMES = 3`/`DEFAULT_TIMEOUT = 10`）。
4. 模块/文件：小写蛇形命名法，禁止使用空格或特殊字符（`user_api.py`/`order_utils.py`）。
5. 避免歧义：禁用单字符命名（除循环变量 `i/j`、临时变量 `x/y` 外）。

### （二）代码格式

1. 格式化工具：统一使用 `ruff` 格式化代码，行长度限制为 120 个字符，禁止手动调整格式。
2. 空行使用：
    - 函数/类之间空 2 行，类内方法之间空 1 行；
    - 逻辑块之间空 1 行，避免连续空行或无意义空行。
3. 导入规范：
    - 导入顺序：标准库 → 第三方库 → 项目内部模块，每组之间空 1 行；
    - 禁止通配符导入（`from module import *`），明确导入所需的类/函数；
    - 导入路径使用绝对路径，避免相对路径的多层引用（如 `from project.api import user` 而非 `from ..api import user`）。
4. 注释规范：
    - 极简注释原则：非复杂逻辑、非特殊业务规则无需注释，通过清晰的命名体现逻辑；
    - 复杂逻辑注释：需说明「为什么这么做」而非「做了什么」，示例：

      ```python
      # 优先使用缓存而非数据库查询，因订单数据查询QPS高达1000+，缓存可降低90%数据库压力
      def get_order_detail(order_id: str) -> Order:
          cache_data = redis_client.get(f"order:{order_id}")
          if cache_data:
              return Order(**json.loads(cache_data))
          return db.query(Order).filter(Order.id == order_id).first()
      ```

    - 函数/类注释：使用文档字符串（docstring），格式统一为 Google 风格，包含参数、返回值、异常说明（复杂函数必填）。

## 四、类型注解规范

1. 强制标注：所有函数/方法的参数、返回值必须标注类型，类的属性建议标注类型。
2. 禁用模糊类型：严格禁用 `any`/`Any`，确保类型检查可覆盖；字典包含多类型时，使用联合声明（如 `dict[str, str | int | float]`）。
3. 可空类型：禁止使用 `Optional[Type]`，统一使用 `Type | None` 表示可空类型（如 `str | None` 而非 `Optional[str]`）。
4. 容器类型：标注容器内元素类型，如 `list[int]`/`tuple[str, int]`/`set[float]`，禁止仅标注 `list`/`tuple`。
5. 自定义类型：复杂类型使用 `TypeAlias` 定义别名，提升可读性，示例：

   ```python
   from typing import TypeAlias

   OrderData: TypeAlias = dict[str, str | int | list[dict[str, str]]]

   def process_order(order: OrderData) -> bool:
       ...
   ```

6. 类型检查：提交代码前必须通过 `mypy` 检查，禁止忽略类型错误（特殊场景需备注原因）。

## 五、技术参考与工具使用

1. 技术参考优先级：
    - 使用 `Context7` 工具检索，确保获取最新、准确的技术细节；
    - 其次参考源码实现（通过 `uv show <包名>` 定位源码路径）
2. 第三方库选型：
    - 优先选择活跃度高（GitHub 星数 ≥1000、近半年有更新）、维护团队稳定的库；
    - 避免使用小众、无维护的库，引入前需确认是否存在安全漏洞（可通过 `uv audit` 检查）。

## 六、时间使用规范

1. 时区标准：无特别说明时，所有时间相关操作默认使用 UTC 时间，禁止使用本地时区（如 CST/EST）。
2. 时间格式：统一使用 ISO 8601 格式（`YYYY-MM-DDTHH:MM:SSZ`）存储和传输时间，示例：`2026-01-31T12:00:00Z`。
3. 时间处理：
    - 使用 `datetime` 模块的 `utcnow()`/`utcfromtimestamp()` 生成 UTC 时间，禁止使用 `now()`（默认本地时区）；
    - 时间戳统一使用秒级整数，禁止混用毫秒级/微秒级时间戳；
    - 时区转换需显式声明，示例：

      ```python
      from datetime import datetime, timezone
 
      # 正确：生成UTC时间
      utc_time = datetime.now(timezone.utc)
      # 正确：UTC时间转东八区
      cst_time = utc_time.astimezone(timezone(offset=3600*8))
      ```

4. 避免硬编码：时间相关常量（如超时时间、有效期）需定义为常量，禁止硬编码数字（如 `TIME_OUT = 30` 而非直接写 `sleep(30)`）。

## 七、异常处理规范

1. 精准捕获：禁止捕获宽泛的 `Exception`，需捕获具体异常（如 `FileNotFoundError`/`requests.exceptions.ConnectionError`），示例：

   ```python
   # 错误
   try:
       open("config.json")
   except Exception:
       pass

   # 正确
   try:
       open("config.json")
   except FileNotFoundError:
       logger.error("配置文件config.json不存在")
       raise  # 按需重新抛出，禁止静默吞异常
   ```

2. 异常处理原则：
    - 捕获异常后必须记录日志，禁止无处理、无日志的「静默吞异常」；
    - 非业务预期的异常需重新抛出，让上层处理；业务预期的异常（如「用户不存在」）可返回明确的错误信息。
3. 自定义异常：复杂业务场景定义自定义异常类，继承 `Exception`，按业务模块分类（如 `UserError`/`OrderError`）。

## 八、日志规范

1. 日志工具：统一使用标准库 `logging` 模块，禁止使用 `print` 输出调试信息。
2. 日志级别：
    - DEBUG：开发调试用，记录详细流程（如「开始查询订单，订单ID：123」）；
    - INFO：关键业务流程（如「订单支付成功，订单ID：123」）；
    - WARNING：非致命问题（如「缓存连接超时，降级为数据库查询」）；
    - ERROR：业务错误（如「订单支付失败，原因：余额不足」）；
    - CRITICAL：系统级错误（如「数据库连接失败，服务不可用」）。
3. 日志格式：包含时间（UTC）、日志级别、模块、函数、内容、请求ID（分布式场景），示例：

   ```python
   import logging

   logging.basicConfig(
       format="%(asctime)s UTC %(levelname)s %(module)s.%(funcName)s: %(message)s",
       datefmt="%Y-%m-%d %H:%M:%S"
   )
   ```

4. 日志存储：生产环境日志输出到文件，按天分割，保留30天；禁止在日志中存储敏感信息（如密码、手机号）。

## 九、测试规范

1. 测试框架：统一使用 `pytest`，测试文件命名为 `test_<模块名>.py`，测试函数/类命名为 `test_<功能名>`/`Test<功能名>`。
2. 测试覆盖率：核心业务代码覆盖率不低于80%，通过 `pytest-cov` 检测覆盖率。
3. 测试类型：
    - 单元测试：测试单个函数/方法，隔离外部依赖（如使用 `pytest-mock` 模拟数据库/接口）；
    - 集成测试：测试模块间交互，验证接口调用、数据流转的正确性；
    - 回归测试：修改代码后，必须运行全量测试，确保不引入回归问题。
4. 测试执行：提交代码前必须运行本地测试，CI/CD流程中自动执行测试，测试不通过禁止合并代码。

## 十、版本控制与提交规范

1. 版本控制工具：使用 Git，分支管理遵循 Git Flow 规范：
    - `main`：生产环境分支，禁止直接提交，仅通过合并 `develop`/`hotfix` 分支更新；
    - `develop`：开发主分支，所有功能分支基于此分支创建；
    - `feature/<功能名>`：功能开发分支，完成后合并到 `develop`；
    - `hotfix/<问题编号>`：生产环境紧急修复分支，完成后合并到 `main` 和 `develop`。
2. 提交信息规范：格式为「类型: 描述」，类型包括：
    - feat：新增功能（如 `feat: 新增订单查询接口`）；
    - fix：修复bug（如 `fix: 修复订单金额计算错误`）；
    - docs：文档更新（如 `docs: 补充API文档`）；
    - style：代码格式调整（无逻辑变更，如 `style: 格式化user_api.py`）；
    - refactor：代码重构（无功能变更，如 `refactor: 拆分order_process函数`）；
    - test：测试相关（如 `test: 补充订单支付单元测试`）；
    - chore：依赖/工具更新（如 `chore: uv add requests==2.31.0`）。
3. 提交粒度：单个提交仅包含一个功能/一个bug修复，禁止大批量、无关联的代码提交。

## 十一、文件与目录结构规范

1. 常规项目结构（参考）：

   ```
   project-name/
   ├── .venv/              # 虚拟环境（忽略版本控制）
   ├── project_name/       # 源码目录
   │   ├── type_wrapper
   │   │   └── *_wrapper.py
   │   └── __init__.py
   ├── tests/              # 测试目录（与src结构对应）
   ├── pyproject.toml      # 项目配置（uv依赖）
   ├── uv.lock             # 依赖锁定文件
   ├── .gitignore          # Git忽略文件
   └── README.md           # 项目说明
   ```

2. 配置文件：敏感配置（如数据库密码）通过环境变量读取，禁止硬编码到代码/配置文件中。
3. 忽略文件：`.gitignore` 需包含 `.venv/`、`__pycache__/`、`.env`、日志文件、临时文件等。


## 第三方库类型隔离策略
pyright `strict` 模式下，第三方库若缺少类型定义会导致大量报错，按以下优先级处理：

1. 优先安装 type stubs（作为 dev 依赖）
    - `uv add --dev pandas-stubs`   # pandas
    - `uv add --dev types-requests`  # requests
    - `uv add --dev types-matplotlib` # matplotlib
    - `uv add --dev types-python-dotenv` # python-dotenv
    - numpy（≥1.20）、SQLAlchemy（≥2.0）已内置类型，无需额外安装。

2. 无 type stubs 的库，按库建封装模块
   在包目录下创建 `type_wrapper/*_wrapper.py`，用全类型注解的函数封装第三方 API 调用：
   **openclaw_script/type_wrapper/ccxt_wrapper.py**
    ```python
    def create_exchange(name: str, config: dict[str, str] | None = None) -> ccxt.Exchange:
        ...
        return exchange
    
    def fetch_ohlcv(
        exchange: ccxt.Exchange,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> pd.DataFrame:
        raw: list[list] = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        ...
        return df
    ```
规则：
- 封装函数必须有完整的参数/返回值类型声明，不得出现 `Any/Unknown`
- `dict/list` 必须指定泛型参数
- 项目代码只引用封装模块，禁止直接调用第三方库 API
- 封装模块自身不受 `strict` 约束（在 pyproject.toml 中排除）
    ```toml
    [tool.pyright]
    typeCheckingMode = "strict"
    ignore = ["openclaw_script/type_wrapper/*_wrapper.py"]
    ```