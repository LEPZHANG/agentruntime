# Agentao

> **A Governed Agent Runtime** — 受治理的 Agent 运行时，面向**本地优先、隐私优先、可嵌入**的场景。
>
> *"Order in Chaos, Path in Intelligence."*

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-agentao.cn-blue)](https://agentao.cn)

> **仓库名 vs 包名**：仓库叫 `agentruntime`，**Python 包名是 `agentao`**。
> 安装与导入都用 `agentao`。

---

## 它解决什么问题

让 LLM 能**安全地动手**，比让它**说话**难得多。模型会生成参数被截断的 JSON、会重复调用同一个工具打转、
会被读到的文件内容注入、会在你不知情的情况下删掉目录。

**运行时这一层的价值，就是把不可靠的模型包成可靠的系统。**

它的设计前提是**对抗性**的 —— 假设模型会出错、工具会失败、输入不可信，
然后把每一个边界情况写进**类型化、有测试、fail-closed** 的控制流。

同一套内核驱动三个入口：**交互式 CLI**、**`agentao run` 自动化**、**ACP server（JSON-RPC）**。

---

## 核心能力

### 1. 治理与安全（纵深防御）

| 层 | 机制 |
|---|---|
| **权限引擎** | 四种模式 `read-only` / `workspace-write` / `full-access` / `plan`；项目级 + 用户级 JSON 规则，来源带优先级 |
| **Shell 语义地板** | 执行前拦截**不可逆**操作（`rm -rf /`、`mkfs`、`dd of=/dev/rdisk`、fork bomb）。**不是字符串匹配** —— 做位置上下文分析：引号归一化、`$'...'`、命令替换下钻、`sh -c` 嵌套、heredoc 掩码 |
| **网络出口（SSRF）** | DNS 解析后校验**真实 IP**（防 DNS Rebinding）、识别 **IPv6 内嵌 IPv4** 与 **NAT64** 前缀、**重定向逐跳**复查、支持允许 CIDR |
| **文件路径围栏** | 写入前解析**符号链接链**，拒绝 `../` 逃逸与绝对路径写系统文件 |
| **进程隔离** | 子进程独立进程组，**超时杀整棵树**（防孙子进程挂住管道）；stdin 显式分离 |
| **凭据脱敏** | 统一的凭据模式扫描，用于日志、工具输出、回放与记忆守卫 |
| **截断安全** | `finish_reason=length` 时**拒绝执行**其中的工具调用 —— 被砍断的参数可能"语法合法但语义危险"（`rm -rf /path` 被截成 `rm -rf /`） |

### 2. 工具执行管线

```
Plan → Confirm → Execute → Format
```

- 权限决策事件**先于**执行事件发出（满足宿主顺序契约）
- 多工具**线程池并行** + 实例级锁
- 每个调用发**配对的开始 / 结束**生命周期事件 —— **被拒的调用同样纳入**，保证审计与回放完整
- **参数修复阶梯**：严格 JSON → 双重编码 → 宽松解析 → 尾逗号 → Python 字面量 →（可选）括号配平
- 工具名修复；**doom-loop 检测**（识别重复无效调用）
- 回合结局收敛为**闭集词表**：`no_output` / `reasoning_only` / `length_truncated` / `doom_loop` / `llm_error`

### 3. 记忆与上下文

- **SQLite 双作用域记忆**（用户 / 项目）+ 会话摘要 + 软删除
- **7 因素记忆召回打分**：标签精确命中（按查询长度分档）、标题 Jaccard、关键词覆盖、正文覆盖、
  路径提示、时间新鲜度、陈旧惩罚；配 `semantic > 0` **门控过滤**排除无关记忆
- **倒排索引 + 写版本脏标 + 中文分词**，把打分从全量降到候选子集
- **经验结晶（crystallization）**：从会话抽取 `preference` / `constraint` / `decision` / `workflow`
  四类洞见 → **进人工审核队列** → 批准后才写入；带三级置信度 `auto_summary` → `inferred` → `explicit_user`
- **自生成技能**：让 Agent 从会话证据为自己写 `SKILL.md`，并设**四道 NO-OP 门控**拒绝无效技能
  （与已有技能重复 / 无法展开为具体步骤 / 属通用常识 / 仅对单次任务有效）
- **长上下文管理**：以 API 返回的真实 `prompt_tokens` 为**锚点**做增量估算 →
  两级压缩（工具结果头尾截断 → LLM 结构化摘要）→ provider 溢出错误识别与降级恢复 → 最近读取文件重注入
- **写入与读取不对称**：记忆**写入**对 LLM 开放，**检索 / 删除仅限人工 CLI** ——
  Agent 不能单方面改写自己的长期记忆

### 4. 协议与可观测

- **MCP**（stdio / Streamable HTTP / SSE）与 **ACP**（JSON-RPC）双入口
- **JSONL 事件回放**：每个回合可完整重放
- **脱敏日志**：记录每次 LLM 请求 / 响应、工具调用与结果、token 用量，落盘前统一脱敏
- **宿主契约**：稳定的事件类型与 Pydantic schema，宿主可直接嵌入 `Agentao(...)`

---

## 快速开始

```bash
pip install 'agentao[cli]'      # 交互式 CLI 所需的最小安装
cp .env.example .env            # 填入 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL
agentao                         # 交互式
agentao run --prompt "..."      # 非交互式
agentao --acp --stdio           # ACP server
```

**嵌入到你的应用**（不依赖环境变量发现）：

```python
from pathlib import Path
from agentao import Agentao
from agentao.llm import LLMClient
from agentao.transport import NullTransport

agent = Agentao(
    working_directory=Path("/tmp/agent-run-1"),
    llm_client=LLMClient(api_key="sk-...", base_url="...", model="..."),
    transport=NullTransport(),
)
print(agent.chat("Summarize today's logs."))
agent.close()
```

**权限模式**（交互式内 `/mode` 切换）：

| 模式 | 行为 |
|---|---|
| `read-only` | 禁止一切写入与 shell |
| `workspace-write` | 允许工作区内写入与安全 shell（默认） |
| `full-access` | 全部放行 |
| `plan` | 只规划、不执行 |

---

## 架构

```
agentao/
├─ agent.py              门面：sync chat() / async arun()
├─ runtime/              回合机制：ChatLoopRunner / ToolRunner / 参数修复 /
│                        截断安全 / doom-loop / 模型分层
├─ permissions.py        权限引擎（规则 + 模式 + 地板）
├─ permissions_hardline/ Shell 语义扫描：位置上下文 / heredoc / 解码 / 模式
├─ security/             path_policy / url_policy(SSRF) / secret_scan
├─ memory/               SQLite 记忆 / 倒排召回 / 结晶 / 守卫
├─ context_manager.py    token 锚点 / 两级压缩 / 溢出恢复
├─ host/                 【公开宿主契约】事件、事件流、权限视图
├─ replay/               JSONL 回放录制与投影
├─ mcp/  acp/            MCP 客户端 / ACP 服务端
├─ agents/               子 Agent 委派与结果回收
├─ skills/  plugins/     技能与插件
└─ prompts/  plan/       提示装配 / 计划模式
```

**规模**：约 **270 个 Python 源文件、204 个测试文件**，
**测试代码行数略高于源码** —— 这是刻意的取舍，不是副产品。

---

## 设计原则

1. **Fail-closed** —— 判定不了就拒绝，不做乐观假设
2. **不可逆操作 vs "昂贵但可恢复"操作分层** —— 前者做成库内不变量的"地板"，
   后者（`git reset --hard`、`pip install`、`curl | sh`）交给宿主策略
3. **顺序契约** —— 权限决策事件先于执行事件；开始 / 结束事件严格配对
4. **"看到的文本"与"执行的含义"要显式分离** —— 凡二者可能不一致处，都做归一化并写测试
5. **人留在回路里** —— 记忆与技能的自我进化必须过审核队列，不能让 Agent 静默改写长期状态

---

## 文档

| 读者 | 入口 |
|---|---|
| **CLI 用户** | [`developer-guide/zh/cli/`](developer-guide/zh/cli/) · [agentao.cn/zh/cli/](https://agentao.cn/zh/cli/) |
| **嵌入开发者** | [`developer-guide/zh/`](developer-guide/zh/) · [agentao.cn](https://agentao.cn) |
| **English** | [`developer-guide/en/`](developer-guide/en/) · [agentao.cn/en/](https://agentao.cn/en/) |
| **配置与 API 参考** | [`docs/reference/configuration.md`](docs/reference/configuration.md) |

本地浏览文档：

```bash
cd developer-guide && npx vitepress dev
```

---

## 许可

MIT。见 [LICENSE](LICENSE)。
