"""Embedded harness factory + host-side persistence for :class:`arbiter.agent.Arbiter`.

`build_from_environment()` captures every implicit env / dotenv / cwd /
``.arbiter/*.json`` read that the agent constructor would otherwise
perform and routes them through explicit-injection kwargs. CLI and
ACP entrypoints go through this single surface so embedded hosts that
already have explicit config can construct :class:`Arbiter` directly
without any of the env-touching side effects.

`sessions` (formerly the top-level :mod:`arbiter.session`) holds the
``.arbiter/sessions/*.json`` save/load/list/delete helpers. The legacy
import path remains as a deprecation shim until 0.5.0; new code should
``from arbiter.embedding.sessions import save_session, ...`` and pass
``project_root`` explicitly.

`permission_loader` holds :func:`load_permission_rules`, the public
helper that reads ``<user_root>/permissions.json``. Hosts pass the
returned ``(rules, sources)`` to ``PermissionEngine(rules=..., loaded_sources=...)``
so the engine itself does no file I/O.
"""

from .factory import build_from_environment
from .permission_loader import load_permission_rules
from .sessions import (
    delete_all_sessions,
    delete_session,
    format_session_time_local,
    list_sessions,
    load_session,
    save_session,
    strip_system_reminders,
)

__all__ = [
    "build_from_environment",
    "load_permission_rules",
    "save_session",
    "load_session",
    "list_sessions",
    "delete_session",
    "delete_all_sessions",
    "strip_system_reminders",
    "format_session_time_local",
]
