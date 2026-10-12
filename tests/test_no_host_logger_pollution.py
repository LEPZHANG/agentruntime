"""P0.7 regression: arbiter must not pollute the host's logging stack.

Embedded hosts care most about *not* having their root logger mutated.
``logging.basicConfig`` on the host's root would re-route every other
library's log output, and a stray ``logging.getLogger().setLevel(...)``
would flip every logger that hadn't pinned its own level. This test
captures the root-logger snapshot before and after:

1. ``import arbiter``
2. ``from arbiter import Arbiter``  (lazy resolution path)
3. ``Arbiter(...)``                 (construction with injected LLMClient)

and asserts the snapshot is unchanged. The construction step uses an
injected ``LLMClient`` (the embed-host pattern) so the package-internal
``arbiter`` logger setup that runs only on the default-LLMClient path
does not interfere with the assertion.

The check is intentionally narrow — it covers root only, not the
``arbiter.*`` family. The package may freely configure its own
namespace; the contract is "stay on your side of the fence."
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch


def _root_snapshot() -> dict[str, Any]:
    root = logging.getLogger()
    return {
        "level": root.level,
        "handler_ids": [id(h) for h in root.handlers],
        "filter_ids": [id(f) for f in root.filters],
        "propagate": root.propagate,
        "disabled": root.disabled,
    }


def test_import_arbiter_does_not_touch_root_logger() -> None:
    """Plain ``import arbiter`` must not configure root.

    Lazy ``__getattr__`` keeps this fast (P0.5); we also assert here that
    nothing in the package-init path quietly calls ``logging.basicConfig``
    or attaches a handler to root.
    """
    before = _root_snapshot()
    import arbiter  # noqa: F401

    after = _root_snapshot()
    assert before == after, (
        "import arbiter mutated the root logger:\n"
        f"  before: {before}\n  after : {after}"
    )


def test_from_arbiter_import_arbiter_does_not_touch_root_logger() -> None:
    """Resolving the lazy ``Arbiter`` attribute must not touch root either."""
    before = _root_snapshot()
    from arbiter import Arbiter  # noqa: F401

    after = _root_snapshot()
    assert before == after, (
        "Resolving Arbiter mutated the root logger:\n"
        f"  before: {before}\n  after : {after}"
    )


def test_arbiter_construction_does_not_touch_root_logger(tmp_path: Path) -> None:
    """Constructing ``Arbiter(...)`` against an injected LLMClient leaves root alone.

    This is the property hosts care about most. Even when the default
    ``LLMClient`` adds a *package-namespace* file handler, root must not
    gain handlers, change level, or get a filter.
    """
    before = _root_snapshot()

    # Construct with a mock LLMClient via the documented embedded-host
    # path ("inject your own llm_client"). Going through this seam is
    # what the test claims to cover — the alternative env-backfill
    # codepath in conftest.py would not exercise the same ctor branch.
    mock_llm = Mock()
    mock_llm.logger = Mock()
    mock_llm.model = "gpt-test"
    with patch("arbiter.tooling.mcp_tools.McpClientManager"), patch(
        "arbiter.tooling.mcp_tools.load_mcp_config", return_value={}
    ):
        from arbiter.agent import Arbiter

        agent = Arbiter(working_directory=tmp_path, llm_client=mock_llm)
        try:
            after = _root_snapshot()
        finally:
            agent.close()

    assert before == after, (
        "Constructing Arbiter mutated the root logger — embedded hosts "
        "rely on this not happening:\n"
        f"  before: {before}\n  after : {after}"
    )


def test_arbiter_logger_namespace_is_self_contained(tmp_path: Path) -> None:
    """Any handler arbiter adds must live under the ``arbiter`` namespace.

    Hosts that filter on logger name expect arbiter output to be tagged
    consistently. A stray handler on ``""`` (root) or on a sibling
    namespace would defeat that filter.
    """
    mock_llm = Mock()
    mock_llm.logger = Mock()
    mock_llm.model = "gpt-test"
    with patch("arbiter.tooling.mcp_tools.McpClientManager"), patch(
        "arbiter.tooling.mcp_tools.load_mcp_config", return_value={}
    ):
        from arbiter.agent import Arbiter

        agent = Arbiter(working_directory=tmp_path, llm_client=mock_llm)
        try:
            # Iterate every existing logger; any handler bound to a name
            # outside the ``arbiter`` family violates the contract.
            offenders: list[str] = []
            manager = logging.Logger.manager
            for name, logger in list(manager.loggerDict.items()):
                if not isinstance(logger, logging.Logger):
                    continue
                if logger.handlers and not (
                    name == "arbiter" or name.startswith("arbiter.")
                ):
                    # Some test harnesses pre-populate other loggers; only
                    # complain about handlers tagged as ours.
                    bad = [
                        h
                        for h in logger.handlers
                        if getattr(h, "_arbiter_llm_file_handler", False)
                    ]
                    if bad:
                        offenders.append(f"{name}: {bad!r}")
            assert not offenders, (
                "arbiter installed handlers outside its own namespace:\n  "
                + "\n  ".join(offenders)
            )
        finally:
            agent.close()
