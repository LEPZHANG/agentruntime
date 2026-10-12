"""Capability protocols re-exported on the public ``arbiter.host`` surface.

This is the only inbound surface in ``arbiter.host``: the other three
pillars (events, ACP schema, permission state) flow Arbiter → host;
these protocols flow host → Arbiter, letting embedded hosts override
IO by injecting their own implementations into
``Arbiter(filesystem=..., shell=..., mcp_registry=..., memory_manager=...)``.

Importing them directly from ``arbiter.host.protocols`` keeps host code
on the stable boundary instead of reaching into ``arbiter.capabilities.*``,
which is internal and may move.

The value types (``FileEntry``, ``FileStat``, ``ShellRequest``,
``ShellResult``, ``BackgroundHandle``) are part of the public contract too:
hosts implementing a ``Protocol`` must produce these shapes.

See ``docs/reference/host-api.md`` for the host-injection walkthrough.
"""

from __future__ import annotations

from ..capabilities.filesystem import FileEntry, FileStat, FileSystem
from ..capabilities.mcp import MCPRegistry
from ..capabilities.memory import MemoryStore
from ..capabilities.shell import (
    BackgroundHandle,
    ShellExecutor,
    ShellRequest,
    ShellResult,
)

__all__ = [
    "BackgroundHandle",
    "FileEntry",
    "FileStat",
    "FileSystem",
    "MCPRegistry",
    "MemoryStore",
    "ShellExecutor",
    "ShellRequest",
    "ShellResult",
]
