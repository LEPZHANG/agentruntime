"""Main entry point for Arbiter."""

import warnings
warnings.filterwarnings("ignore", message="urllib3.*or chardet.*doesn't match")

from arbiter.cli import entrypoint

if __name__ == "__main__":
    entrypoint()
