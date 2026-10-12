"""Bidirectional Arbiter ↔ Claude tool-name alias mapping.

Plugin hook payloads use Claude-compatible tool names so a hook script
written against Claude Code (``Read``, ``Bash``, ``Edit``) can run
under Arbiter without modification.
"""

from __future__ import annotations


# Arbiter tool name -> Claude-compatible alias
_TOOL_ALIASES: dict[str, str] = {
    "read_file": "Read",
    "write_file": "Write",
    "replace": "Edit",
    "run_shell_command": "Bash",
    "glob": "Glob",
    "search_file_content": "Grep",
    "web_fetch": "WebFetch",
    "web_search": "WebSearch",
    "list_directory": "LS",
    "save_memory": "SaveMemory",
    "ask_user": "AskUser",
    "todo_write": "TodoWrite",
    "plan_save": "PlanSave",
    "plan_finalize": "PlanFinalize",
    "activate_skill": "ActivateSkill",
}


class ToolAliasResolver:
    """Bidirectional mapping between Arbiter tool names and Claude aliases."""

    def __init__(self, extra: dict[str, str] | None = None) -> None:
        self._to_claude = dict(_TOOL_ALIASES)
        if extra:
            self._to_claude.update(extra)
        self._to_arbiter = {v: k for k, v in self._to_claude.items()}

    def to_claude_name(self, arbiter_name: str) -> str:
        return self._to_claude.get(arbiter_name, arbiter_name)

    def to_arbiter_name(self, claude_name: str) -> str:
        return self._to_arbiter.get(claude_name, claude_name)
