# 2.1 Install & Import

> **What you'll learn**
> - Which install line matches your usage (extras matrix)
> - The two imports you'll always need
> - How lazy loading keeps `import arbiter` cheap even with heavy deps

## Install

Pick the install line that matches your usage. Starting in 0.4.0,
`pip install arbiter` ships an embedding-only core — CLI / web fetch /
Chinese tokenization are opt-in extras.

```bash
# Embedding host (`from arbiter import Arbiter`) — minimum closure
pip install 'arbiter>=0.4.0'

# Need the web_fetch / web_search tools — adds beautifulsoup4
pip install 'arbiter[web]>=0.4.0'

# Need Chinese-text memory recall — adds jieba
pip install 'arbiter[i18n]>=0.4.0'

# CLI users only — adds rich/prompt-toolkit/readchar/pygments
pip install 'arbiter[cli]>=0.4.0'

# Upgrading from 0.3.x and want zero behaviour change
pip install 'arbiter[full]>=0.4.0'
```

Extras matrix is documented in [1.5 Requirements](/en/part-1/5-requirements).
0.3.x → 0.4.0 migration guide:
[`docs/migration/0.3.x-to-0.4.0.md`](https://github.com/jin-bo/agentao/blob/main/docs/migration/0.3.x-to-0.4.0.md).

## The two imports you always need

```python
from arbiter import Arbiter                  # main agent class
from arbiter.transport import SdkTransport    # callback bridge; preferred for embedding
```

Those two lines are essentially the price of admission. Everything else is opt-in:

```python
from arbiter.transport import (
    Transport,         # Protocol base (implement for a custom transport)
    AgentEvent,        # event object
    EventType,         # event enum
    NullTransport,     # silent transport (tests)
)

from arbiter.permissions import PermissionEngine, PermissionMode
from arbiter.cancellation import CancellationToken, AgentCancelledError
from arbiter.tools.base import Tool, ToolRegistry  # when authoring custom tools
```

## Lazy loading

`arbiter/__init__.py` uses **PEP 562 `__getattr__`** to defer heavy imports — `from arbiter import Arbiter` does not pull the OpenAI SDK, BeautifulSoup, jieba, filelock, rich, prompt_toolkit, readchar, click, pygments, starlette, or uvicorn.

What stays lazy now (load on first runtime use):

| Library | First triggered by |
|---|---|
| `openai` | `LLMClient(...)` construction (default LLM client only — hosts that inject `llm_client=` never load it) |
| `bs4` / `httpx` | `WebFetchTool.execute()` / `WebSearchTool.execute()` — note: post-0.4.0 these tools are skipped at registration if `bs4` is absent (the `[web]` extra is opt-in), so the model never sees a tool whose execute would fail |
| `jieba` | CJK-bearing query through `MemoryRetriever` — pure-Latin queries skip jieba entirely; if `[i18n]` is absent, CJK recall degrades to empty with a one-time warning |
| `filelock` | `SkillRegistry.save()` (CLI / `arbiter plugin install`) |
| `mcp` SDK (`McpClientManager`, `McpTool`) | first MCP server attach (`init_mcp` or hosts that pass `mcp_manager=`) |
| `rich`, `prompt_toolkit`, `readchar`, `click`, `pygments` | only loaded by `arbiter/cli/*` — never on the embed path |

For embedders:

- `import arbiter` is **cheap** — none of the above touch your import-time graph.
- Accessing `arbiter.Arbiter` triggers the agent module, which still avoids the deferred libs above.
- Hosts that pass their own `llm_client=` / `mcp_registry=` / file-system / shell never pay for the OpenAI SDK or the MCP SDK at all.
- `from arbiter.memory import ...` stays standalone — no LLM stack loaded.
- The invariant is enforced by `tests/test_no_cli_deps_in_core.py` (AST walk; fails if a top-level import of a deferred module slips outside `arbiter/cli/`) and `tests/test_import_cost.py` (`python -X importtime` subprocess; fails if any of the deferred names appear in the trace of `import arbiter`).

You can treat Arbiter as a "conditional dependency": import cost only when you actually use it.

```python
# Top of your FastAPI module
import arbiter  # lightweight, no side effects

def get_agent():
    from arbiter import Arbiter  # agent module loads, but openai/bs4/jieba do not
    return Arbiter(...)
```

## Version check

```python
import arbiter
print(arbiter.__version__)   # "0.4.0"
```

In production, verify at startup:

```python
import arbiter
from packaging.version import Version

MIN = Version("0.4.0")
if Version(arbiter.__version__) < MIN:
    raise RuntimeError(f"Need arbiter >= {MIN}, got {arbiter.__version__}")
```

## Minimal embedding skeleton

```python
"""Bare-minimum embedding boilerplate."""
from pathlib import Path
from arbiter import Arbiter
from arbiter.transport import SdkTransport

def make_agent(workdir: Path, on_token=None) -> Arbiter:
    transport = SdkTransport(
        on_event=lambda ev: on_token(ev.data.get("chunk", ""))
                             if on_event_is_text(ev) else None,
    )
    return Arbiter(transport=transport, working_directory=workdir)

def on_event_is_text(ev) -> bool:
    return ev.type.name == "LLM_TEXT"
```

Parameter meanings are covered next.

## TL;DR

- `pip install 'arbiter>=0.4.0'` is the embedding-only minimum — add `[web]` / `[i18n]` / `[cli]` / `[full]` etc. as needed.
- Two imports you'll always need: `from arbiter import Arbiter` + `from arbiter.transport import SdkTransport`.
- `import arbiter` is cheap — heavy libs (`openai`, `bs4`, `jieba`, `mcp`, `rich` …) are deferred to first runtime use.
- Pin in production: `arbiter>=0.4.0,<0.5`.

::: info Version note
- **0.4.0** — `pip install arbiter` now ships embedding-only core; `[web]`, `[cli]`, `[i18n]`, etc. are opt-in extras. `[full]` reproduces the 0.3.x dependency closure. See [migration guide](https://github.com/jin-bo/agentao/blob/main/docs/migration/0.3.x-to-0.4.0.md).
- **0.3.4** — Lazy-import deferral expanded to cover the full opt-in surface (OpenAI SDK, BeautifulSoup, jieba, filelock, rich, prompt_toolkit, readchar, click, pygments, starlette, uvicorn). Invariant enforced by `tests/test_no_cli_deps_in_core.py` and `tests/test_import_cost.py`.
:::

→ [2.2 Constructor Reference](./2-constructor-reference)
