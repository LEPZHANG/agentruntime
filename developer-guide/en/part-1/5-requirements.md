# 1.5 Requirements

> **What you'll learn**
> - The Python / OS / network / disk requirements before embedding
> - Which extras to install for the features you want
> - A 7-line checklist to verify your environment is ready

Verify your environment before embedding Arbiter.

## Python version

- **Minimum: Python 3.10**
- Recommended: 3.11 or 3.12 (better tracebacks and perf)
- 3.13 works but is not exhaustively verified

## Package management

Arbiter's own repo uses **`uv`**. When embedding, **pip is fine** — `arbiter` is a standard PyPI package.

Starting in 0.4.0, `pip install arbiter` ships only the embedding core; pick the
install line that matches your usage:

```bash
# Embedding host (`from arbiter import Arbiter`) — minimum closure
pip install arbiter

# Need the web_fetch / web_search tools — adds beautifulsoup4
pip install 'arbiter[web]'

# Need Chinese-text memory recall — adds jieba
pip install 'arbiter[i18n]'

# CLI users (the `arbiter` console script) — adds rich/prompt-toolkit/readchar/pygments
pip install 'arbiter[cli]'

# uv users mirror the same pattern
uv add 'arbiter[cli]'
```

## LLM credentials

Arbiter calls LLMs through an OpenAI-compatible interface. Configure at least one credential set:

| Env var | Purpose | Example |
|--------|---------|---------|
| `OPENAI_API_KEY` | API key (**required**) | `sk-...` |
| `OPENAI_BASE_URL` | API endpoint (**required**) | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Model id (**required**) | `gpt-5.4` |
| `LLM_TEMPERATURE` | Sampling temp (optional, default 0.2) | `0.3` |
| `LLM_PROVIDER` | Vendor tag (optional, default OPENAI) | `ANTHROPIC` |

> **All three — `{PROVIDER}_API_KEY`, `{PROVIDER}_BASE_URL`, and `{PROVIDER}_MODEL` — are required.** `LLMClient.__init__` raises `ValueError` immediately at startup if any is missing. Constructor args `api_key=`, `base_url=`, and `model=` can substitute for the env vars when embedding programmatically.

### Verified compatible endpoints

| Vendor | base_url | Default model |
|--------|----------|---------------|
| OpenAI | (default) | gpt-5.4 / gpt-5 family |
| Anthropic | `https://api.anthropic.com/v1` | claude-sonnet-4-6 |
| Gemini | via OpenAI-compatible gateway | gemini-flash-latest |
| DeepSeek | `https://api.deepseek.com` | deepseek-chat |
| Self-hosted vLLM | `http://your-host:8000/v1` | depends on your deployment |

## OS support matrix

| OS | Core runtime | Shell sandbox | MCP | Notes |
|----|-------------|---------------|-----|-------|
| macOS 13+ | ✅ Full | ✅ `sandbox-exec` | ✅ | Recommended for dev |
| Linux | ✅ Full | ❌ No sandbox (recommend container / user namespace) | ✅ | Preferred for production |
| Windows | ⚠️ Basic | ❌ No sandbox | ⚠️ Some MCP servers are Unix-only | Prefer WSL2 |

> The shell sandbox is an **optional extra layer** (Part 6.2). Without it, `run_shell_command` is still gated by the **permission engine** and **tool confirmation**.

## Network

- **Outbound**: LLM calls hit your configured `base_url`; some tools (`web_fetch`, `web_search`) hit the public internet
- **Inbound**: **none**. Arbiter does not listen on a port; ACP mode uses stdio
- **MCP SSE servers**: if you use SSE-based MCP servers, the host must reach their URLs

## Disk layout

When embedded, Arbiter reads/writes these paths:

| Path | Purpose | Can disable? |
|------|---------|--------------|
| `<working_directory>/.arbiter/` | Project-level config (MCP, permissions, memory) | Constrained by permission rules |
| `<working_directory>/ARBITER.md` | Project instructions (you write this) | Skip the file and nothing loads |
| `<working_directory>/arbiter.log` | Runtime log | Disable via custom logger |
| `~/.arbiter/` | User-level config, memory | Relocate or skip |

In production, set `<working_directory>` to a **per-tenant / per-session temp dir** so sessions stay isolated (Part 7.1 covers this).

## Optional dependencies

Capabilities split into extras post-0.4.0; combine them with comma syntax
(`arbiter[cli,web]`):

```bash
# CLI / interactive UI (P0.9 demoted these from the bundled core)
pip install 'arbiter[cli]'       # rich + prompt-toolkit + readchar + pygments
pip install 'arbiter[web]'       # beautifulsoup4 — required for web_fetch / web_search
pip install 'arbiter[i18n]'      # jieba — Chinese-text memory recall

# Heavy file-format tools
pip install 'arbiter[pdf]'       # PDF reading (pymupdf, pdfplumber)
pip install 'arbiter[excel]'     # Excel read/write (pandas, openpyxl)
pip install 'arbiter[image]'     # Image processing (Pillow)
pip install 'arbiter[crypto]'    # pycryptodome
pip install 'arbiter[google]'    # google-genai
pip install 'arbiter[crawl4ai]'  # crawl4ai
pip install 'arbiter[tokenizer]' # tiktoken — precise token accounting

# Meta extras
pip install 'arbiter[full]'      # Everything (0.3.x-equivalent closure)
```

> Without `[web]`, the registry **omits** `web_fetch` and `web_search` entirely
> — the model will not see them in its tool schema, avoiding the trap where a
> model calls a tool that fails with a generic ImportError. Without `[i18n]`,
> CJK memory recall degrades gracefully (one-time warning + empty CJK tokens);
> Latin queries skip jieba entirely so they pay no cost. The `[cli]` extra is
> required to run the `arbiter` console script — bare installs print a friendly
> `pip install arbiter[cli]` hint and exit 2.

See [`docs/migration/0.3.x-to-0.4.0.md`](https://github.com/jin-bo/agentao/blob/main/docs/migration/0.3.x-to-0.4.0.md) for the full 0.3.x → 0.4.0 migration matrix.

## Version compatibility

- Arbiter is currently in **0.x (Beta)**. Breaking changes can land between minor versions — pin exact versions:
  ```
  arbiter>=0.4.0,<0.5
  ```
- This guide targets **v0.4.0 GA**. Version-specific notes will be flagged inline.
- The single break in 0.4.0 is the dependency split (P0.9). 0.3.x users who
  want zero behaviour change can use `pip install 'arbiter[full]'`.

## Checklist

```bash
# All of these should succeed
python --version                        # >= 3.10
pip show arbiter | grep Version          # your pinned version
echo $OPENAI_API_KEY | head -c 10       # key prefix visible
echo $OPENAI_BASE_URL                   # must be non-empty
echo $OPENAI_MODEL                      # must be non-empty
arbiter --help                          # CLI reachable (optional)
python -c "from arbiter import Arbiter; print('OK')"
python -c "from arbiter.transport import SdkTransport; print('OK')"
```

Environment green — move on to Part 2 for actual integration work.

## TL;DR

- **Python ≥ 3.10** required; 3.11 / 3.12 recommended.
- **3 env vars** required: `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` (constructor args also work).
- **Default install is embedding-only**. Add extras as needed: `[web]`, `[i18n]`, `[cli]`, `[pdf]`, `[excel]`, `[image]`, `[full]` (everything).
- **No inbound port** — agent is a library or stdio subprocess; outbound goes to your LLM endpoint and any tool URLs.
- **Pin a version range** in production: `arbiter>=0.4.0,<0.5`.

→ [Part 2 · Python In-Process Embedding](/en/part-2/)
