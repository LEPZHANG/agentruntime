# Arbiter

> **A Governed Agent Runtime** — 受治理的 Agent 运行时，面向**本地优先、隐私优先、可嵌入**的场景。
>
> *"Order in Chaos, Path in Intelligence."*

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-3651-brightgreen)](#测试)

---

## 它解决什么问题

让 LLM 能**安全地动手**，比让它**说话**难得多。

模型会生成参数被截断的 JSON、会重复调用同一个工具打转、会被读到的文件内容注入、
会在你不知情的情况下删掉目录。

**运行时这一层的价值，就是把不可靠的模型包成可靠的系统。**

Arbiter 的设计前提是**对抗性**的 —— 假设模型会出错、工具会失败、输入不可信，
然后把每一个边界情况写进**类型化、有测试、fail-closed** 的控制流。

同一套内核驱动三个入口：**交互式 CLI**、**`arbiter run` 自动化**、**ACP server**。

---

## 快速开始

### 安装

> ⚠️ 尚未发布到 PyPI，请从源码安装。

```bash
git clone https://github.com/LEPZHANG/arbiter.git
cd arbiter

uv sync --extra cli            # 推荐（uv）
# 或用 pip：
# pip install -e '.[cli]'
```

### 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入：

```ini
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-5.4
```

### 跑起来

```bash
uv run arbiter                       # 交互式 CLI
uv run arbiter run --prompt "总结今天的日志"   # 非交互式（自动化 / CI）
uv run arbiter --acp --stdio         # ACP server（给编辑器/宿主用）
```

> `arbiter run` 的退出码：`0` 成功 · `1` 运行时错误 · `2` 用法错误 · `3` 权限/交互 ·
> `4` 超过最大迭代 · `130` 被中断。

---

## 四种权限模式

Agent 的每一次写入和 shell 调用都要过权限引擎。交互式里用 `/mode` 切换：

| 模式 | 行为 | 适用 |
|---|---|---|
| `read-only` | 禁止一切写入与 shell | 只让它读代码、查资料 |
| `workspace-write` | 允许工作区内写入与安全 shell（**默认**） | 日常开发 |
| `full-access` | 全部放行 | 隔离沙箱里跑 |
| `plan` | 只规划、不执行（用 `/plan` 进入） | 先看它打算怎么干 |

规则可写在 `.arbiter/permissions.json`（项目级）和 `~/.arbiter/permissions.json`（用户级）。

---

## 核心能力

### 1. 治理与安全（纵深防御）

| 层 | 机制 |
|---|---|
| **权限引擎** | 四种模式 + 项目/用户两级规则，来源带优先级 |
| **Shell 语义地板** | 执行前拦截**不可逆**操作（`rm -rf /`、`mkfs`、`dd of=/dev/rdisk`、fork bomb）。**不是字符串匹配** —— 做位置上下文分析：引号归一化、`$'...'`、命令替换下钻、`sh -c` 嵌套、heredoc 掩码 |
| **网络出口（SSRF）** | DNS 解析后校验**真实 IP**（防 DNS Rebinding）、识别 **IPv6 内嵌 IPv4** 与 **NAT64** 前缀、**重定向逐跳**复查 |
| **文件路径围栏** | 写入前解析**符号链接链**，拒绝 `../` 逃逸 |
| **进程隔离** | 子进程独立进程组，**超时杀整棵树**（防孙子进程挂住管道）；stdin 显式分离 |
| **凭据脱敏** | 统一凭据模式扫描，用于日志、工具输出、回放与记忆守卫 |
| **截断安全** | `finish_reason=length` 时**拒绝执行**其中的工具调用 —— 被砍断的参数可能"语法合法但语义危险"（`rm -rf /path` 被截成 `rm -rf /`） |

### 2. 工具执行管线

```
Plan → Confirm → Execute → Format
```

- 权限决策事件**先于**执行事件发出（满足宿主顺序契约）
- 多工具**线程池并行** + 实例级锁
- 每个调用发**配对的开始 / 结束**事件 —— **被拒的调用同样纳入**，保证审计与回放完整
- **参数修复阶梯**：严格 JSON → 双重编码 → 宽松解析 → 尾逗号 → Python 字面量 →（可选）括号配平
- 工具名修复；**doom-loop 检测**
- 回合结局收敛为**闭集词表**：`no_output` / `reasoning_only` / `length_truncated` / `doom_loop` / `llm_error`

### 3. 记忆与上下文

- **SQLite 双作用域记忆**（用户 / 项目）+ 会话摘要 + 软删除
- **7 因素召回打分**：标签精确命中（按查询长度分档）、标题 Jaccard、关键词覆盖、正文覆盖、
  路径提示、时间新鲜度、陈旧惩罚；配 `semantic > 0` **门控过滤**
- **倒排索引 + 写版本脏标 + 中文分词**，把打分从全量降到候选子集
- **经验结晶**：从会话抽取 `preference` / `constraint` / `decision` / `workflow` 四类洞见 →
  **进人工审核队列** → 批准后才写入；三级置信度 `auto_summary` → `inferred` → `explicit_user`
- **长上下文管理**：以 API 返回的真实 `prompt_tokens` 为**锚点**做增量估算 →
  两级压缩（工具结果头尾截断 → LLM 结构化摘要）→ provider 溢出错误识别与降级恢复
- **写入与读取不对称**：记忆**写入**对 LLM 开放，**检索 / 删除仅限人工 CLI**

### 4. 协议与可观测

- **MCP**（stdio / Streamable HTTP / SSE）与 **ACP**（JSON-RPC）双入口
- **JSONL 事件回放**：每个回合可完整重放
- **脱敏日志**：记录每次 LLM 请求 / 响应、工具调用与结果、token 用量，落盘前统一脱敏
- **宿主契约**：稳定的事件类型与 Pydantic schema，宿主可直接嵌入 `Arbiter(...)`

---

## 嵌入到你的应用

不需要环境变量发现 —— 宿主拥有每一个输入：

```python
from pathlib import Path
from arbiter import Arbiter
from arbiter.llm import LLMClient
from arbiter.transport import NullTransport

agent = Arbiter(
    working_directory=Path("/tmp/agent-run-1"),
    llm_client=LLMClient(api_key="sk-...", base_url="...", model="..."),
    transport=NullTransport(),
)
print(agent.chat("Summarize today's logs."))
agent.close()
```

宿主通过 `arbiter.host` 订阅事件（工具生命周期、权限决策、子 Agent 生命周期）：

```python
from arbiter.host import HostEvent, ToolLifecycleEvent, PermissionDecisionEvent
```

---

## 常用 CLI 命令

| 命令 | 作用 |
|---|---|
| `/mode read-only\|workspace-write\|full-access` | 切换权限姿态 |
| `/plan` · `/plan implement` · `/plan show` | 计划模式 |
| `/goal <目标> --for 30m` | 长任务自动续跑（带时间/turn 预算） |
| `/memory search\|delete\|user\|project\|status` | 记忆管理（**仅人工可用**） |
| `/mcp list\|add\|remove` | MCP 服务器管理 |
| `/model` · `/provider` · `/temperature` · `/thinking` | LLM 配置 |
| `/replay on\|off` | 回合回放 |
| `/help` | 完整命令列表 |

---

## 文档

| 我想…… | 看 |
|---|---|
| **用起来**（本文件） | 上面几节 + [`docs/reference/configuration.md`](docs/reference/configuration.md) |
| **改代码 / 加功能** | **[`DEVELOPMENT.md`](DEVELOPMENT.md)** ← 开发者入口 |
| **CLI 全部命令** | [`developer-guide/zh/cli/`](developer-guide/zh/cli/) |
| **深度手册**（7 部分） | [`developer-guide/zh/`](developer-guide/zh/) |
| **English** | [`developer-guide/en/`](developer-guide/en/) |

本地浏览文档站：

```bash
cd developer-guide && npx vitepress dev
```

---

## 测试

```bash
uv run python -m pytest tests/        # 默认套件（3651 个测试）
uv run python -m pytest -m slow       # 干净安装冒烟测试
```

测试代码行数**略高于源码** —— 这是刻意的取舍，不是副产品。

---

## 许可

MIT。见 [LICENSE](LICENSE)。
