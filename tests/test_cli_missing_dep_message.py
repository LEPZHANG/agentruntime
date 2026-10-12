"""Friendly missing-dep message from the ``arbiter`` CLI in core-only installs.

Three slow-marked tests against a built wheel:

- core-only: ``arbiter`` exits 2 with the named-package + install-line message
- core-only + ``[cli]``: ``arbiter --help`` boots and exits 0
- core-only: ``from arbiter.cli import entrypoint`` resolves without
  tripping rich/prompt_toolkit (precondition for the friendly path)

Run with::

    uv build && uv run pytest tests/test_cli_missing_dep_message.py -m slow
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.support.wheel import make_venv, require_wheel


pytestmark = [pytest.mark.slow]


def test_core_only_cli_prints_friendly_missing_dep(tmp_path: Path) -> None:
    wheel = require_wheel()
    venv = make_venv(tmp_path)
    venv.pip_install(str(wheel))

    proc = subprocess.run([str(venv.arbiter_script)], capture_output=True, text=True)

    assert proc.returncode == 2, (
        f"expected exit code 2, got {proc.returncode}.\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "arbiter CLI requires extra packages" in proc.stderr
    assert "pip install 'arbiter[cli]'" in proc.stderr
    assert "pip install 'arbiter[full]'" in proc.stderr
    # The shim must catch the ImportError before the traceback escapes —
    # otherwise the user sees the opaque ModuleNotFoundError we are here to hide.
    assert "Traceback" not in proc.stderr
    assert "ModuleNotFoundError" not in proc.stderr


def test_cli_extra_makes_arbiter_help_work(tmp_path: Path) -> None:
    wheel = require_wheel()
    venv = make_venv(tmp_path)
    venv.pip_install(f"{wheel}[cli]")

    proc = subprocess.run(
        [str(venv.arbiter_script), "--help"],
        capture_output=True, text=True,
    )

    assert proc.returncode == 0, (
        f"arbiter --help failed after [cli] install:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "usage: arbiter" in proc.stdout


def test_core_only_can_import_arbiter_cli_entrypoint(tmp_path: Path) -> None:
    """The shim only fires on call; the import itself must stay light."""
    wheel = require_wheel()
    venv = make_venv(tmp_path)
    venv.pip_install(str(wheel))

    proc = subprocess.run(
        [str(venv.python), "-c", "from arbiter.cli import entrypoint; print('import OK')"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"`from arbiter.cli import entrypoint` failed in core-only venv:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "import OK" in proc.stdout


def test_partial_cli_install_still_hits_friendly_path(tmp_path: Path) -> None:
    """Rich installed but other [cli] deps missing must still exit 2 cleanly.

    Without an upfront preflight, ``entrypoints.run_init_wizard``'s broad
    ``except Exception`` would swallow the deep ``ModuleNotFoundError``
    and emit a generic "Fatal error" — bypassing the friendly path that
    points at ``pip install 'arbiter[cli]'``.
    """
    wheel = require_wheel()
    venv = make_venv(tmp_path)
    venv.pip_install(str(wheel), "rich")  # rich only — prompt_toolkit/readchar/pygments still missing

    proc = subprocess.run([str(venv.arbiter_script)], capture_output=True, text=True)

    assert proc.returncode == 2, (
        f"expected exit code 2 in partial install, got {proc.returncode}.\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "arbiter CLI requires extra packages" in proc.stderr
    assert "Fatal error" not in proc.stdout and "Fatal error" not in proc.stderr
