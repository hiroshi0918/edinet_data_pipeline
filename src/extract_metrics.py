"""旧スクリプトとの互換ラッパー — `edinet process` サブコマンドへの委譲.

このファイルは v0 時代の `python src/extract_metrics.py` 呼び出しを壊さないために
残されている互換シムです。新規開発は `edinet process --limit N` を直接使うことを
推奨します (パッケージインストール後に有効になる console_scripts 経由)。

例:
  python src/extract_metrics.py --limit 20
  python src/extract_metrics.py --limit 20 --retry-failed
"""

from __future__ import annotations

import sys

from edinet_pipeline.cli import main

if __name__ == "__main__":
    # 受け取った引数をそのまま `edinet process` の後ろに繋いで委譲する。
    raise SystemExit(main(["process", *sys.argv[1:]]))
