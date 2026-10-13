# 开发者指南

> 面向要**读源码、改代码、加功能**的人。
> 只想用的话看 [`README.md`](README.md)。

| | |
|---|---|
| **语言** | Python ≥ 3.10 |
| **包管理** | [`uv`](https://docs.astral.sh/uv/)（推荐）或 pip |
| **规模** | 270 个源文件 / **59,216 行**；204 个测试文件 / **62,269 行** |
| **许可** | MIT |

> 测试代码**比源码还多 3 千行** —— 这不是副产品，是刻意的。下面「设计原则」第 1 条会解释为什么。

---

## 环境准备

```bash
git clone https://github.com/LEPZHANG/arbiter.git
cd arbiter

uv sync --extra cli --extra web --extra i18n    # 装依赖
cp .env.example .env                            # 配 OPENAI_* 三个变量

uv run arbiter                                  # 跑起来
uv run python -m pytest tests/                   # 跑测试（3651 个）
```

**extras 说明**（核心依赖很轻，重的都是可选的）：

| extra | 内容 | 什么时候要 |
|---|---|---|
| `cli` | rich / prompt-toolkit / readchar / pygments | 要用交互式 CLI |
| `web` | beautifulsoup4 | 要用网页抓取工具 |
| `i18n` | jieba | 中文分词（记忆关键词召回） |
| `tokenizer` | tiktoken | 精确 token 计数 |
| `dev` | pytest / mypy / build / twine | 开发 |

---

## 架构总览

### 一个回合里发生了什么

```
Arbiter.chat() / Arbiter.arun()
  └─ ChatLoopRunner.run()                     runtime/chat_loop/_runner.py
       loop (max_iterations):
         ├─ run_llm_call(messages, tools)     runtime/llm_call.py
         ├─ if tool_calls:
         │    └─ ToolRunner.run()             runtime/tool_runner.py
         │         plan → execute → format → sanitize
         │           └─ 门禁：PermissionEngine + confirmation_callback
         └─ else: 返回助手文本
```

- `chat()` 是同步外壳，`arun()` 是异步真身
- **AsyncTool** 在 `runtime_loop` 上派发，所以 LLM 驱动的一轮里**取消是可以穿透到工具内部的**

### 两条负载承重的边界

```
┌──────────────────────────────────────────┐
│  宿主（Host）                             │
│  · 提供 working_directory / llm_client    │
│  · 订阅事件（arbiter.host）               │
│  · 决定确认回调                           │
└────────────────┬─────────────────────────┘
                 │  【公开宿主契约】稳定边界
┌────────────────┴─────────────────────────┐
│  运行时（Runtime）—— 内部实现可自由重构     │
└──────────────────────────────────────────┘
```

1. **`arbiter.host` 是公开契约，`arbiter` 其余部分是内部实现。**
   宿主只该依赖 `host/` 导出的东西。这个边界是**承重**的 —— 破坏它等于破坏所有嵌入方。
2. **执行归 Agent，审批归宿主。**
   注意 Arbiter 的 ACP 实现里**没有 `fs/*` 和 `terminal/*`** —— 文件与终端操作由 Agent 自己的工具做，
   宿主只负责**批准和展示**。这是刻意的职责划分，不是漏做。

---

## 代码结构

| 路径 | 职责 |
|---|---|
| `agent.py` | `Arbiter` 门面 —— 同步 `chat()` / 异步 `arun()`；构造时装配 LLM、工具、技能、插件、权限、回放 |
| `runtime/` | 每回合机制：`ChatLoopRunner` / `ToolRunner`（四阶段管线）/ 参数修复 / 截断安全 / doom-loop |
| `host/` | **公开宿主契约**：`HostEvent`、`ToolLifecycleEvent`、`SubagentLifecycleEvent`、`PermissionDecisionEvent`、`EventStream` |
| `harness/` | `host` 的**废弃别名**（0.4.2 改名），0.5.0 移除 |
| `permissions.py` + `permissions_hardline/` | `PermissionEngine` + shell 语义地板扫描器（位置上下文 / heredoc / 解码） |
| `security/` | `path_policy` / `url_policy`(SSRF) / `secret_scan`（共享凭据模式，日志·回放·记忆守卫都用它） |
| `sandbox/` | 沙箱 profile（macOS `sandbox-exec` 等） |
| `memory/` | SQLite 存储 / 倒排召回 / 结晶 / 守卫 |
| `context_manager.py` | token 锚点估算 / 两级压缩 / 溢出恢复 |
| `embedding/` | **宿主侧构造**：`build_from_environment()`、`permission_loader`、`sessions`、`plugins/`（加载器） |
| `plugins/` | 插件**运行路径**（模型、钩子、校验器）—— 加载器在 `embedding/plugins/` |
| `tooling/` | 工具注册（`registry.py::register_builtin_tools`）+ Agent/MCP 工具接线 |
| `tools/` | 工具实现（`base.py` 定义 `Tool` / `AsyncToolBase`） |
| `cli/` | 交互式 CLI **包**（0.4.x 前是单文件 `cli.py`）：`app.py` / `entrypoints.py` / `run.py` / `commands/` |
| `acp/` · `acp_client/` | ACP **服务端** / **客户端**（两端都实现了） |
| `mcp/` | MCP 客户端（stdio / Streamable HTTP / SSE） |
| `agents/` | 子 Agent 委派与结果回收 |
| `skills/` · `prompts/` · `plan/` · `capabilities/` · `replay/` · `transport/` | 技能发现 / 提示装配 / 计划模式 / 能力声明 / 回放 / 传输 |

---

## 设计原则

这五条不是口号 —— 每一条都对应一组具体实现和测试。

### 1. Fail-closed，且"不可逆"与"昂贵"要分层

判定不了就**拒绝**，不做乐观假设。

但并非所有危险操作都该被库拦下 —— 分两层：

| 层 | 覆盖 | 谁决定 |
|---|---|---|
| **地板**（库内不变量） | **不可逆**操作：`rm -rf /`、`mkfs`、`dd of=/dev/rdisk`、fork bomb | 库自己，**任何模式下都不放行** |
| **策略**（宿主决定） | **昂贵但可恢复**：`git reset --hard`、`pip install`、`curl \| sh` | 宿主 / 权限规则 |

**为什么重要**：把 `pip install` 做成硬地板会很烦人；把 `rm -rf /` 交给策略则迟早出事。

### 2. 顺序契约

- **权限决策事件先于执行事件发出** —— 宿主才能做出正确的 UI 反应
- **开始 / 结束事件严格配对** —— **被拒的调用也要发**，否则审计和回放会有洞

### 3. "看到的文本"与"执行的含义"必须显式分离

**凡是二者可能不一致的地方，都要归一化并写测试。**

这条催生了最多代码，也是最容易出漏洞的地方：

- Shell：引号归一化、`$'...'`、命令替换下钻、`sh -c` 嵌套、heredoc 掩码
- 网络：DNS 解析后校验**真实 IP**（防 Rebinding）、IPv6 内嵌 IPv4、NAT64、重定向逐跳
- 路径：解析**符号链接链**后再判是否逃逸

> **一个具体后果**：`finish_reason=length` 时**拒绝执行**该回合的工具调用 ——
> 被砍断的参数可能语法合法但语义危险（`rm -rf /path` 截成 `rm -rf /`）。

### 4. 人留在回路里

记忆与技能的自我进化**必须过人工审核队列**，不能让 Agent 静默改写自己的长期状态：

- 记忆**写入**对 LLM 开放，**检索 / 删除仅限人工 CLI**
- 经验结晶进**审核队列**，批准后才落库
- 自生成技能要过**四道 NO-OP 门控**（重复 / 无法展开 / 通用常识 / 仅单次有效）

### 5. 测试要比源码多

**对抗性系统里，没测过的分支等于不存在。** 所以测试行数刻意超过源码。

---

## 如何扩展

### 加一个内置工具

1. 继承 `arbiter/tools/base.py` 的 `Tool`（同步）或 `AsyncToolBase`（异步）
2. **注册在 `arbiter/tooling/registry.py::register_builtin_tools()`** —— ⚠️ 不是 `agent.py`
3. 需要用户确认就设 `requires_confirmation=True`，权限引擎会自动接管
4. 加测试

> `arbiter/tools/goal.py` 是特例：**默认不注册**，由 CLI 在 `/goal` 激活时用 `add_tool` 注入。

### 加一个技能

在 `skills/<name>/` 下放 `SKILL.md`（YAML frontmatter 要有 `name:` / `description:`），
可选 `references/*.md`（激活时加载）。跨进程有 `filelock` 保护，并发安装/更新安全。

激活：`activate_skill` 工具，或 `/skills activate <name>`。

### 接一个 MCP 服务器

写进 `.arbiter/mcp.json`（项目）或 `~/.arbiter/mcp.json`（全局）：

- 有 `command` → stdio
- 有 `url` → **默认 Streamable HTTP**；旧的 SSE 要显式写 `"type": "sse"`

工具会注册为 `mcp_{server}_{tool}`。

### 加权限规则

`.arbiter/permissions.json`（项目）+ `~/.arbiter/permissions.json`（用户）。

> ⚠️ **`PermissionEngine` 自己不做任何文件 IO** ——
> `arbiter/embedding/permission_loader.py::load_permission_rules()` 负责读，然后把 `(rules, sources)` 传进去。
> 改权限逻辑时别把 IO 塞回引擎。

### 加一个子 Agent

看 `arbiter/agents/`，以及 `tooling/agent_tools.py` 的接线方式。

---

## 调试与可观测

### 日志

`arbiter.log` 记录**每一次** LLM 请求/响应、带格式化 JSON 参数的工具调用、工具结果、token 用量、
时间戳 —— **不截断**。

> **内容不是原文**：文件 handler 上挂了 `_RedactingFormatter`，会把凭据形态的字符串改写成
> `[REDACTED:<kind>]`（模式来自 `arbiter/security/secret_scan.py`）。
>
> 它是 `Formatter` 而**不是 `Filter`**，这是刻意的 —— `Filter` 会改写共享的 `LogRecord`，
> 把脱敏泄漏到 logger 上的**每一个其他 handler**，包括嵌入方自己的。

调试需要原始字节时，那个 formatter 是唯一该动的地方。

### 回放

```bash
/replay on     # 之后每个回合写进 .arbiter/replays/*.jsonl
```

回放状态**不在 `Arbiter` 核心里** —— Transport 发 `TURN_BEGIN` / `TURN_END`，ReplayManager 订阅。

### 为什么调试要先看 `arbiter/llm/client.py`

工具执行或 LLM 行为不对劲时，**先读这个文件**。日志的落点和请求构造都在那里。

---

## 测试

```bash
uv run python -m pytest tests/        # 默认套件
uv run python -m pytest -m slow       # 干净安装冒烟（默认排除）
uv run python -m pytest tests/test_permissions.py -v
```

`pyproject.toml` 里 `addopts = "--tb=short -m 'not slow'"`，所以 `slow` 默认不跑。

### ⚠️ 一个会咬人的坑：测试会读你的**本地配置**

确认类测试（`test_menu_confirmation` / `test_readchar_confirmation` / `test_status_pause` …）
断言"按了某个键之后状态如何"。

**如果你的项目级 `.arbiter/settings.json` 里是 `{"mode": "full-access"}`，
工具确认会被自动放行 —— `readkey` 根本不会被调用，这些测试就集体失败。**

跑全量前二选一：

```bash
# 方案 A：临时移开本地配置
mv .arbiter .arbiter.bak && uv run python -m pytest tests/ && mv .arbiter.bak .arbiter

# 方案 B：用独立 HOME（同时避免读写 ~/.arbiter）
HOME=$(mktemp -d) uv run python -m pytest tests/
```

**这也是一个可以改进的地方** —— 测试目前没有对项目级配置做隔离。欢迎 PR。

### 环境相关的已知失败

某些测试依赖**外层环境**，在受限环境里会失败，与代码无关：

| 测试 | 依赖 | 受限时的现象 |
|---|---|---|
| `test_sandbox_policy.py` | macOS `sandbox-exec` | `sandbox_apply: Operation not permitted`（嵌套沙箱被禁） |
| `test_shell_stdin_devnull.py` | PATH 上有 `python` | `/bin/sh: python: command not found` |
| `test_acp_client_embedding.py` | 交互式终端行为 | 非 TTY 环境下状态断言失败 |

---

## 已知陷阱

- **`cli.py` 在 0.4.x 拆成了 `cli/` 包。** 老文档可能还写 `cli.py` —— 实际去看 `arbiter/cli/`。
- **`arbiter.harness` → `arbiter.host`**（0.4.2 改名）。旧名是废弃别名，0.5.0 移除。
- **`allow_all_tools` 已经没了。** 用 `/mode full-access` 或等价的宿主 API。
- **`arbiter -p` 只是 `arbiter run` 的薄壳。** 新自动化直接面向 `arbiter run`。
- **`Arbiter` 构造函数有 8 个遗留回调**（`confirmation_callback` / `step_callback` …）会发
  `DeprecationWarning`，0.5.0 移除。迁移面在 `arbiter.embedding.compat`。
- **`/goal --turns` 不是 `max_iterations`。** `--turns` 限制**外层**续跑次数
  （goal 循环驱动多少次 `chat()`），`max_iterations` 限制**单次 `chat()` 内**的工具循环。
  两者正交，同时生效。

### 🔴 批量执行命令别用 `subprocess.run`

用 `arbiter/capabilities/process.py::run_captured()`。

**为什么**：`subprocess.run(timeout=)` **只杀直接子进程**。如果孙子进程握着管道不放
（Windows 的 git 凭据助手、用户钩子里 background 出去的进程…），
`communicate()` 会**挂过超时** —— 而在 ACP-stdio 下，一个卡住的工具会**楔死整个回合**，
直到客户端超时断连。

`run_captured()` 做了这些：

- 子进程跑在**自己的进程组/会话**里，超时时 `killpg` / `taskkill /T` **杀整棵树**
- **显式处理 stdin**（有 `input=` 走管道，否则 `DEVNULL` —— 不让子进程读走 JSON-RPC 通道）
- 默认 `env=build_child_env()`，**剥掉 Arbiter 自己的 provider 凭据**（`HARNESS_ENV_KEYS`）
  → 插件钩子要 shell 出去调 provider 的话，得显式传 `env=` 或设 `ARBITER_SCRUB_CHILD_ENV=0`
- 解码用 `errors="replace"`

`search_file_content` 和插件钩子派发都走它；
`LocalShellExecutor.run` 保留自己的流式 + 空闲超时循环，但复用 `kill_process_tree` 和同一套净化环境。

---

## 文档在哪

| 内容 | 位置 |
|---|---|
| 深度手册（7 部分，双语） | [`developer-guide/`](developer-guide/) |
| 设计决策记录 | [`docs/design/`](docs/design/) |
| 配置与 API 参考 | [`docs/reference/configuration.md`](docs/reference/configuration.md) |
| 宿主契约 | [`docs/design/embedded-host-contract.md`](docs/design/embedded-host-contract.md) · [`docs/reference/host-api.md`](docs/reference/host-api.md) |
| 给 AI 编码助手的嵌入手册 | [`docs/guides/embed-for-agents.md`](docs/guides/embed-for-agents.md) |
| 变更记录 | [`CHANGELOG.md`](CHANGELOG.md) |

本地起文档站：

```bash
cd developer-guide && npx vitepress dev
```
