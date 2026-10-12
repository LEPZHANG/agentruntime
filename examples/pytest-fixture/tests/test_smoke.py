"""Smoke tests proving the example fixtures construct + run a turn."""

from __future__ import annotations

from arbiter import Arbiter


def test_agent_fixture_yields_a_constructed_arbiter(agent: Arbiter) -> None:
    assert isinstance(agent, Arbiter)
    # No turn has run yet.
    assert agent.messages == []


def test_agent_fixture_runs_one_turn(agent: Arbiter) -> None:
    """The patched ``_llm_call`` makes ``chat`` return the scripted reply."""
    reply = agent.chat("hello")
    assert reply == "fixture reply"
    # The user + assistant entries are both on the message log.
    roles = [m["role"] for m in agent.messages]
    assert "user" in roles and "assistant" in roles


def test_agents_are_isolated_per_test(agent: Arbiter) -> None:
    """Each test gets its own working_directory + message buffer.

    Pair this with ``test_agents_are_isolated_per_test_round_two`` to
    confirm — the second test would see history from the first if the
    fixture leaked state.
    """
    agent.chat("first test message")
    assert len(agent.messages) >= 2  # user + assistant


def test_agents_are_isolated_per_test_round_two(agent: Arbiter) -> None:
    """Companion to the previous test — must start with empty history."""
    assert agent.messages == []


def test_agent_with_reply_factory_scripts_responses(agent_with_reply) -> None:
    """The factory variant lets one test script different replies."""
    a1 = agent_with_reply("first reply")
    assert a1.chat("hi") == "first reply"

    a2 = agent_with_reply("second reply")
    assert a2.chat("hi again") == "second reply"
