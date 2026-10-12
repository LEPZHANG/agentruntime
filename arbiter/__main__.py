"""Module entry point so ``python -m arbiter`` works.

This is a thin shim around :func:`arbiter.cli.entrypoint` so users can
launch Arbiter via either:

  - the installed console script (``arbiter [args]``), or
  - ``python -m arbiter [args]`` — useful when the console script is
    not on PATH (CI, virtualenvs without activation, vendored installs).

Both paths land in the same argparse, so ``python -m arbiter --acp --stdio``
launches the ACP server (Issue 12) just like ``arbiter --acp --stdio``.
"""

from arbiter.cli import entrypoint


if __name__ == "__main__":
    entrypoint()
