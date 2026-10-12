# ARBITER.md 角色画廊

> English: [README.md](./README.md)

一组来自真实工作场景的 `ARBITER.md` —— 这是 Arbiter 在每个项目里**项目级**的提示词文件，决定了 agent 怎么说话、怎么判断、怎么记忆。把任意一份拷到你项目根目录命名为 `ARBITER.md`，Arbiter 在下一轮对话就会读到（实现见 `arbiter/agent.py::_build_system_prompt`）。

> 想找可运行的**宿主集成**示例（FastAPI、Slack、Jupyter ……）？请看上一级的 [`examples/`](../README.md)。本画廊只关心提示词，不含代码、不含 `pyproject.toml`，纯文字。

## 当前收录

| 目录 | 角色 | 风格 |
|------|------|------|
| [`daily-driver/`](./daily-driver/ARBITER.md) | 作者本人日常的研究 / 编码助手 | 证据优先、隐私自觉、产物归位 |
| [`kawaii-buddy/`](./kawaii-buddy/ARBITER.md) | 满满情绪价值的口袋小助手 | 卡哇伊、中英文混搭、必关心你感受 |

## 怎么用

1. 挑一个最贴近你需求的角色。
2. 把它的 `ARBITER.md` 拷到**你的项目根目录**（即你运行 `arbiter` 的那个目录）。
3. 随便改 —— 这是起点，不是合同。

每一轮对话 Arbiter 都会重新拼接 `ARBITER.md` 到系统提示里，所以你改完下一条消息就生效，**不用重启**。

## 投稿

有一份在真实工作里立过功的角色配置？欢迎提 PR。建议：

- `ARBITER.md` 短一点（一屏内最好）
- 目录名能自解释（`code-reviewer/`、`pair-programmer/` ……）
- 上面表格里加一行

不追求覆盖面，我们要的是**味道**。
