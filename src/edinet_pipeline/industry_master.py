"""EDINETコード集約一覧から業種情報を取り込む.

EDINET API のレスポンスには業種フィールドが無いため、`companies.industry`
カラム (alembic 0001 で予約済みだが未使用) を埋めるには、金融庁が別途配布
している「EDINETコード集約一覧 (Edinetcode.zip)」を取得する必要がある。
本モジュールはこのワンショット取り込みを担う。

公式 ZIP は Shift-JIS の CSV を内包し、「ＥＤＩＮＥＴコード」「提出者業種」
を含む。ヘッダ行が 1 行目空白で 2 行目にある場合があるため、列名で柔軟に
マッチさせる。
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path

import pandas as pd
import requests

from edinet_pipeline.config import Settings
from edinet_pipeline.db import PipelineRepository, db_connection
from edinet_pipeline.logging_utils import log_event

logger = logging.getLogger(__name__)

EDINET_CODE_COLUMN_CANDIDATES: tuple[str, ...] = (
    "ＥＤＩＮＥＴコード",
    "EDINETコード",
    "edinetCode",
)
INDUSTRY_COLUMN_CANDIDATES: tuple[str, ...] = (
    "提出者業種",
    "業種",
)
EDINET_CODE_ENCODING = "cp932"


def fetch_edinet_code_zip(source: str) -> bytes:
    """URL またはローカルパスから ZIP のバイト列を取得する."""
    if source.startswith(("http://", "https://")):
        response = requests.get(source, timeout=60)
        response.raise_for_status()
        return response.content
    return Path(source).read_bytes()


def parse_edinet_code_master(zip_bytes: bytes) -> pd.DataFrame:
    """ZIP を展開して CSV を edinet_code/industry の 2 列 DataFrame に変換する."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError("Edinetcode ZIP does not contain a CSV file")
        with zf.open(csv_names[0]) as f:
            raw = f.read()

    # ヘッダ行が 1 行目空 + 2 行目本物のパターンに対応するため、両方試す
    for skiprows in (0, 1):
        try:
            df = pd.read_csv(
                io.BytesIO(raw),
                encoding=EDINET_CODE_ENCODING,
                skiprows=skiprows,
                dtype=str,
            )
            code_col = _find_column(df, EDINET_CODE_COLUMN_CANDIDATES)
            industry_col = _find_column(df, INDUSTRY_COLUMN_CANDIDATES)
            break
        except (ValueError, UnicodeDecodeError):
            continue
    else:
        raise ValueError(
            "Could not locate EDINETコード/業種 columns in Edinetcode CSV"
        )

    out = df[[code_col, industry_col]].rename(
        columns={code_col: "edinet_code", industry_col: "industry"}
    )
    out = out.dropna(subset=["edinet_code"])
    out["edinet_code"] = out["edinet_code"].astype(str).str.strip()
    out["industry"] = out["industry"].astype(str).str.strip().replace({"": None, "nan": None})
    out = out.dropna(subset=["industry"])
    return out


def _find_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    raise ValueError(
        f"Column not found. tried={candidates}, available={list(df.columns)}"
    )


def update_industries(settings: Settings, *, source: str) -> dict[str, int]:
    """ZIP 取得 → パース → companies.industry を一括 UPDATE する.

    Returns:
        サマリ辞書 (fetched_rows / matched_existing / updated_rows)
    """
    zip_bytes = fetch_edinet_code_zip(source)
    df = parse_edinet_code_master(zip_bytes)
    mapping: list[tuple[str, str]] = [
        (str(row.edinet_code), str(row.industry)) for row in df.itertuples(index=False)
    ]

    with db_connection(settings.database_url) as connection:
        repository = PipelineRepository(connection)
        repository.update_industries(mapping)
        # execute_values + UPDATE FROM VALUES では cursor.rowcount が信頼できない
        # ことがあるため、UPDATE 後に SELECT で実際の充足数を取得する。
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM companies WHERE industry IS NOT NULL"
            )
            row = cursor.fetchone()
            updated_total = int(row[0]) if row else 0
        connection.commit()

    summary = {
        "fetched_rows": len(df),
        "industry_filled_total": updated_total,
    }
    log_event(
        logger,
        "info",
        "industries_updated",
        **summary,
    )
    return summary
