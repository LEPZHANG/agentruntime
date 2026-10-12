# 3.5 Zed / IDE Integration Walkthrough

Zed's external-agent feature speaks ACP natively — meaning Arbiter drops into Zed with no custom glue. The same pattern applies to any IDE / editor that supports external ACP agents. This section shows the end-to-end wiring.

## 3.5.1 What "ACP integration" means in an IDE

An IDE that implements the ACP client side can:

1. Launch any ACP server as a subprocess
2. Route user chat to `session/prompt`
3. Render `session/update` notifications as a scrolling chat UI
4. Pop `session/request_permission` as a modal
5. Forward editor context (open files, selection) via `cwd` + prompt text

The user just adds your agent in the IDE's settings — everything else is transport.

## 3.5.2 Registering Arbiter with Zed

Zed reads its agent config from `~/.config/zed/settings.json` (or the UI's **Settings → Agents**). Add an entry that points to `arbiter --acp --stdio`:

```json
{
  "agents": [
    {
      "name": "arbiter",
      "command": "arbiter",
      "args": ["--acp", "--stdio"],
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "OPENAI_MODEL": "gpt-5.4"
      }
    }
  ]
}
```

Restart Zed, open any project, and Arbiter appears in the agent picker.

### Notes

- `command` must be on `PATH`. If you installed via `uv tool install arbiter`, it's already there. Otherwise use the absolute path: `/Users/you/.local/bin/arbiter`
- The `env` block is merged with Zed's own environment. Prefer pulling API keys from `~/.zshenv` / `~/.bashrc` and leaving them out of `settings.json`
- Zed passes the workspace root as `cwd` in `session/new` — so `ARBITER.md`, `.arbiter/mcp.json`, skills, memory are all workspace-scoped automatically

## 3.5.3 End-to-end wire trace

What happens when the user types a message in Zed's agent pane:

```
USER types "find TODOs" in Zed                               time
                                                              ────▶
Zed → arbiter:  initialize (once per launch)
arbiter → Zed:  capabilities + extensions

Zed → arbiter:  session/new  {cwd: "/workspace"}
arbiter → Zed:  {sessionId: "sess-1"}

Zed → arbiter:  session/prompt  {sessionId, prompt:[{"type":"text",
                                                      "text":"find TODOs"}]}

arbiter → Zed:  session/update  agent_message_chunk  "Let me search..."
arbiter → Zed:  session/update  tool_call            {title:"grep -r TODO"}
arbiter → Zed:  session/update  tool_call_update     {output:"src/x.py:42: TODO ..."}
arbiter → Zed:  session/update  agent_message_chunk  "Found 3 TODOs in..."
arbiter → Zed:  response        {stopReason: "end_turn"}

(ongoing)       session/update  notifications stream to Zed's UI
```

Zed renders each `session/update` as you'd expect: text chunks stream into the reply, tool calls show as inline cards, permission requests pop as modals.

## 3.5.4 Required Zed capabilities

Arbiter advertises the following in `initialize`:

```json
{
  "agentCapabilities": {
    "loadSession": true,
    "promptCapabilities": { "image": true, "audio": false, "embeddedContext": false },
    "mcpCapabilities":   { "http": true, "sse": true }
  }
}
```

Meaning for Zed:

- ✅ `loadSession`: can restore prior conversations from disk
- ✅ `image` (0.4.8+): inline `{data, mimeType}` image blocks in prompts; non-vision models degrade to text tags — see [A.1](/en/appendix/a-api-reference#image-input-and-vision-degradation)
- ❌ `audio`: not supported
- ❌ `embeddedContext`: Zed can't push embedded resource fetches
- ✅ `http`: Zed can forward Streamable HTTP MCP servers
- ✅ `sse`: Zed can forward SSE MCP servers (legacy)

Zed falls back gracefully on unsupported capabilities.

## 3.5.5 Multi-workspace & multi-window

Zed spawns **one `arbiter` subprocess per agent instance**, and creates separate sessions via `session/new` for each project. That means:

- Multiple Zed windows share one `arbiter` process
- Each workspace's `.arbiter/memory.db` is isolated by `cwd`
- MCP servers spawned via per-session `mcpServers` are scoped to that session

If you prefer one process per workspace (tighter isolation, higher RAM), configure Zed to spawn a separate agent per workspace — consult Zed's own docs for the latest toggle name.

## 3.5.6 VS Code / Cursor / other editors

The pattern repeats:

1. Launch `arbiter --acp --stdio` as a child process
2. Speak NDJSON JSON-RPC 2.0 over stdio
3. Wire `session/update` → UI, `session/request_permission` → modal

A VS Code extension using the TypeScript `ACPClient` from [3.3.4](./3-host-client-architecture#3-3-4-typescript-node-reference-implementation) is outlined in [Blueprint B](/en/part-7/2-ide-plugin).

### JetBrains / IntelliJ

JetBrains IDEs can spawn subprocesses from plugins; the ACP client can be implemented in Kotlin or Java using the same three-loop pattern. No JetBrains-specific complications.

### Neovim

Use `vim.fn.jobstart()` (Lua) or similar to spawn `arbiter --acp --stdio`. Forward `session/update` to a floating window. Community plugins for LSP transport make this straightforward.

## 3.5.7 Environment & secrets

Across every IDE:

- **Never** commit API keys into workspace settings
- Prefer OS keychain (`security` on macOS, Credential Manager on Windows, `secret-tool` on Linux) + a small wrapper script that reads the key and execs `arbiter`
- Or: require the user to set `OPENAI_API_KEY` in their shell profile, and let the IDE inherit the environment

Example wrapper (macOS):

```bash
#!/usr/bin/env bash
# /usr/local/bin/arbiter-wrapper
export OPENAI_API_KEY="$(security find-generic-password -ws openai-api-key)"
exec arbiter "$@"
```

Point the IDE at `arbiter-wrapper` instead of `arbiter`.

## 3.5.8 Debugging integration issues

When things go wrong in the IDE:

| Symptom | Where to look |
|---------|---------------|
| Agent doesn't appear in picker | IDE's own log (e.g. Zed's `Help → Open Log`) |
| Agent crashes on first message | `<workspace>/arbiter.log` |
| Tool call hangs forever | IDE is probably not responding to `session/request_permission` — look at its permission UI code |
| All text comes as one big blob at end | IDE isn't treating `session/update` as streamed; check its UI rendering |
| MCP server doesn't show up | `mcpCapabilities.http` is true — stdio, Streamable HTTP, or SSE all work; check the entry's `type`/`url`/`command` |
| Conversation disappears after restart | IDE isn't calling `session/load` — feature may not be implemented yet |

Capture the wire trace by launching Arbiter manually and piping JSON in:

```bash
# Send hand-crafted JSON via stdin
arbiter --acp --stdio < trace.ndjson > output.ndjson 2> arbiter.stderr.log
```

This bisects whether the issue is in your JSON, in Arbiter's handling, or in the IDE's rendering.

## 3.5.9 Upgrading Arbiter cleanly

When a user updates the `arbiter` binary:

- Zed / VS Code spawn a new process on next launch — no action needed
- `protocolVersion` negotiation handles version mismatch: if the IDE sends version `2` and Arbiter supports `1`, Arbiter returns `1` and the IDE either continues or disconnects
- Skills, MCP, and memory are **workspace-scoped**, so they survive binary upgrades

Breaking protocol changes are avoided. If you need to pin a specific version, ask users to install with `uv tool install arbiter==0.2.14`.

## 3.5.10 Checklist for a new IDE integration

- [ ] ACP client implemented (three-loop architecture from [3.3](./3-host-client-architecture))
- [ ] Handshake sends `protocolVersion: 1` as an integer
- [ ] `session/update` rendered as streaming UI (chunks appear immediately)
- [ ] `session/request_permission` responses within the timeout, never silently drop
- [ ] `session/cancel` wired to a "Stop" button
- [ ] Subprocess cleanup on IDE shutdown (no orphan processes)
- [ ] Error path: subprocess exits → show error + allow reconnect
- [ ] Log the raw wire trace at debug level for support purposes

---

End of Part 3. Next: [Part 4 · Event layer & UI integration](/en/part-4/).
