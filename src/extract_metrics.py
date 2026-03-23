from __future__ import annotations

import sys

from edinet_pipeline.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["process", *sys.argv[1:]]))
