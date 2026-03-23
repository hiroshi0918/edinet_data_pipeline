from __future__ import annotations

import os
import sys
from datetime import date

from edinet_pipeline.cli import main

if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit(main(["fetch", *sys.argv[1:]]))
    default_date = os.getenv("TARGET_DATE", date.today().isoformat())
    raise SystemExit(main(["fetch", "--date", default_date]))
