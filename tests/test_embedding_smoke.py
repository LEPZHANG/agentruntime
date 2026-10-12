"""Small smoke tests for the embedded harness entry surface."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock


def test_embedding_public_modules_import() -> None:
    """Host-facing modules import without constructing the runtime."""
    import arbiter  # noqa: F401
    import arbiter.embedding  # noqa: F401
    import arbiter.host  # noqa: F401
    import arbiter.host.protocols  # noqa: F401


def test_explicit_embedded_construction_and_observer_api(tmp_path: Path) -> None:
    """Pure-injection construction works and exposes stable observer hooks."""
    mock_llm = Mock()
    mock_llm.logger = Mock()
    mock_llm.model = "gpt-test"

    from arbiter import Arbiter
    from arbiter.mcp import InMemoryMCPRegistry
    from arbiter.transport import NullTransport

    agent = Arbiter(
        working_directory=tmp_path,
        llm_client=mock_llm,
        transport=NullTransport(),
        project_instructions="",
        mcp_registry=InMemoryMCPRegistry(),
    )
    try:
        seen = []

        def observer(event):
            seen.append(event)

        handle = agent.add_host_event_observer(observer)
        assert handle is observer
        assert agent.remove_host_event_observer(observer) is True
        assert agent.remove_host_event_observer(observer) is False
        assert seen == []
    finally:
        agent.close()
