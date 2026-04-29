"""旧スクリプトとの互換ラッパー — `edinet fetch` サブコマンドへの委譲.

このファイルは v0 時代の `python src/fetch_edinet.py` 呼び出しを壊さないために
残されている互換シムです。新規開発は `edinet fetch --date YYYY-MM-DD` を直接
使うことを推奨します (パッケージインストール後に有効になる console_scripts 経由)。

引数の扱い:
  - 引数なしで呼ばれた場合: 環境変数 TARGET_DATE (未設定なら今日) を --date に渡す。
  - 引数ありで呼ばれた場合: そのまま `edinet fetch` のあとに繋いで委譲する。

例:
  TARGET_DATE=2024-03-29 python src/fetch_edinet.py
  python src/fetch_edinet.py --date 2024-03-29
"""

from __future__ import annotations

import os
import sys
from datetime import date

from edinet_pipeline.cli import main

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 既に CLI 引数を組んでいる場合はそのまま委譲する。
        raise SystemExit(main(["fetch", *sys.argv[1:]]))
    # 引数省略時は TARGET_DATE 環境変数 (未設定なら今日) を採用する。
    default_date = os.getenv("TARGET_DATE", date.today().isoformat())
    raise SystemExit(main(["fetch", "--date", default_date]))
