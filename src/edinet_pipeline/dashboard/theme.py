"""ダッシュボードのビジュアル基盤 — 「開示台帳 (Disclosure Ledger)」テーマ.

有価証券報告書という公式文書の質感を、冷たい紙色 + 藍 (indigo) のパレットと、
見出しの明朝体 (Shippori Mincho) で表現する。データ本体は Noto Sans JP + 等幅
(Roboto Mono) で清潔に保つ。色は config.toml と本モジュールで共有し、Plotly や
表セルのグラデーションにも同じ値を使ってページ間の一貫性を担保する。

公開 API:
  inject_global_css()       — フォント読み込み + コンポーネント装飾 (各ページ冒頭で 1 回)
  app_brand_header()        — アプリ最上部のブランドヘッダー
  page_header(eyebrow,...)  — 各ページの「英字ラベル + 明朝見出し + 細罫」バンド
  style_plotly(fig)         — Plotly 図にテーマ (フォント・色・余白) を適用
  ratio_table(df, cols)     — 比率列を淡clay→淡tealで塗った Styler を返す (matplotlib 不要)
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ------------------------------------------------------------------ #
#  パレット (config.toml と一致させる)
# ------------------------------------------------------------------ #

PAPER = "#F4F6F9"
CARD = "#FFFFFF"
INK = "#1B2330"
INK_SOFT = "#5B6675"
RULE = "#E3E7EE"
ACCENT = "#2E5BDA"       # 藍 — primary / trust
ACCENT_DEEP = "#163A86"
GOOD = "#1E8A6E"         # teal — 高い = パリティに近い
WARN = "#D98A1F"         # amber — 注意 / 開示が薄い
BAD = "#C0483F"          # clay — 格差が大きい / 最下位

# 比率セルのグラデーション端点 (0% 寄り = 淡clay, 100% 寄り = 淡teal, 中央 = ほぼ白)
_GRAD_LOW = "#F1C8BF"
_GRAD_MID = "#FBFBFC"
_GRAD_HIGH = "#B4E0CE"

_FONT_BODY = "'Noto Sans JP', system-ui, sans-serif"
_FONT_DISPLAY = "'Shippori Mincho', 'Noto Serif JP', serif"
_FONT_MONO = "'Roboto Mono', ui-monospace, monospace"

_FONT_IMPORT = (
    "https://fonts.googleapis.com/css2?"
    "family=Shippori+Mincho:wght@600;700"
    "&family=Noto+Sans+JP:wght@400;500;700"
    "&family=Roboto+Mono:wght@500;600&display=swap"
)


# ------------------------------------------------------------------ #
#  色ユーティリティ
# ------------------------------------------------------------------ #


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _lerp_hex(c1: str, c2: str, t: float) -> str:
    """2 色を t∈[0,1] で線形補間した hex を返す (matplotlib 非依存)."""
    t = max(0.0, min(1.0, t))
    a, b = _hex_to_rgb(c1), _hex_to_rgb(c2)
    mixed = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return "#{:02X}{:02X}{:02X}".format(*mixed)


def _ratio_color(value: float, vmin: float = 0.0, vmax: float = 100.0) -> str:
    """比率値を 0%寄り=淡clay → 50%=白 → 100%寄り=淡teal の発散配色に写像する."""
    if value is None or pd.isna(value):
        return ""
    span = vmax - vmin or 1.0
    t = (float(value) - vmin) / span
    if t <= 0.5:
        return _lerp_hex(_GRAD_LOW, _GRAD_MID, t / 0.5)
    return _lerp_hex(_GRAD_MID, _GRAD_HIGH, (t - 0.5) / 0.5)


# ------------------------------------------------------------------ #
#  グローバル CSS (フォント + コンポーネント装飾)
# ------------------------------------------------------------------ #


def inject_global_css() -> None:
    """フォント読み込みとコンポーネント装飾を注入する (毎回実行で確実に DOM に残す).

    Streamlit は再実行のたびに DOM を作り直すため、CSS は毎回出力する必要がある
    (フォントはブラウザキャッシュが効くのでコストは無視できる)。
    """
    st.markdown(
        f"""
        <style>
        @import url('{_FONT_IMPORT}');

        html, body, [class*="css"], .stApp, [data-testid="stMarkdownContainer"] {{
            font-family: {_FONT_BODY};
            color: {INK};
        }}
        .stApp {{ background: {PAPER}; }}

        /* 既定の余白を詰めてヘッダーを締める */
        .block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1180px; }}

        /* ---- ブランドヘッダー ---- */
        .ledger-brand {{
            display: flex; align-items: baseline; gap: 0.7rem; flex-wrap: wrap;
            border-bottom: 2px solid {INK}; padding-bottom: 0.5rem; margin-bottom: 0.2rem;
        }}
        .ledger-brand .mark {{
            font-family: {_FONT_DISPLAY}; font-weight: 700; font-size: 1.55rem;
            color: {INK}; letter-spacing: 0.02em;
        }}
        .ledger-brand .sub {{
            font-family: {_FONT_MONO}; font-size: 0.72rem; color: {INK_SOFT};
            letter-spacing: 0.16em; text-transform: uppercase; margin-left: 0.2rem;
        }}
        .ledger-brand .tag {{
            margin-left: auto; align-self: center; font-family: {_FONT_MONO};
            font-size: 0.68rem; color: {ACCENT}; border: 1px solid {ACCENT};
            border-radius: 999px; padding: 0.12rem 0.6rem; letter-spacing: 0.06em;
        }}

        /* ---- ページヘッダーバンド ---- */
        .ledger-eyebrow {{
            font-family: {_FONT_MONO}; font-size: 0.72rem; font-weight: 600;
            letter-spacing: 0.22em; text-transform: uppercase; color: {ACCENT};
            margin: 0 0 0.15rem 0;
        }}
        .ledger-title {{
            font-family: {_FONT_DISPLAY}; font-weight: 700; font-size: 2.0rem;
            line-height: 1.18; color: {INK}; margin: 0;
        }}
        .ledger-rule {{
            height: 3px; width: 56px; background: {ACCENT}; margin: 0.55rem 0 0.5rem 0;
        }}
        .ledger-desc {{
            font-size: 0.93rem; color: {INK_SOFT}; max-width: 70ch; margin: 0 0 0.2rem 0;
        }}

        /* ---- メトリクスをカード化 (左に藍の罫、数値は等幅) ---- */
        [data-testid="stMetric"] {{
            background: {CARD}; border: 1px solid {RULE}; border-left: 4px solid {ACCENT};
            border-radius: 0.55rem; padding: 0.7rem 0.95rem;
            box-shadow: 0 1px 2px rgba(27,35,48,0.04);
        }}
        [data-testid="stMetricValue"] {{
            font-family: {_FONT_MONO}; font-weight: 600; color: {INK}; font-size: 1.5rem;
        }}
        [data-testid="stMetricLabel"] p {{
            font-size: 0.78rem; color: {INK_SOFT}; letter-spacing: 0.02em;
        }}

        /* ---- セクション小見出し ---- */
        [data-testid="stHeading"] h2, [data-testid="stHeading"] h3 {{
            font-family: {_FONT_DISPLAY}; color: {INK}; letter-spacing: 0.01em;
        }}

        /* ---- 数値・コードは等幅 ---- */
        code, [data-testid="stMetricValue"] {{ font-family: {_FONT_MONO}; }}

        /* ---- サイドバー ---- */
        [data-testid="stSidebar"] {{ background: {CARD}; border-right: 1px solid {RULE}; }}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 {{
            font-family: {_FONT_DISPLAY};
        }}

        /* ---- ラジオ (指標切替) を横並びチップ風に ---- */
        [data-testid="stRadio"] [role="radiogroup"] {{ gap: 0.4rem; }}

        /* ---- 比率バー・カード (シグネチャ: パリティへの距離) ---- */
        .ledger-rcard {{
            background: {CARD}; border: 1px solid {RULE}; border-radius: 0.55rem;
            padding: 0.7rem 0.85rem 0.85rem; box-shadow: 0 1px 2px rgba(27,35,48,0.04);
        }}
        .ledger-rcard .rc-label {{
            font-size: 0.78rem; color: {INK_SOFT}; margin-bottom: 0.15rem;
        }}
        .ledger-rcard .rc-value {{
            font-family: {_FONT_MONO}; font-weight: 600; font-size: 1.45rem; color: {INK};
            line-height: 1.1;
        }}
        .ledger-rcard .rc-track {{
            margin-top: 0.5rem; height: 8px; border-radius: 6px; background: {PAPER};
            border: 1px solid {RULE}; overflow: hidden;
        }}
        .ledger-rcard .rc-fill {{ height: 100%; border-radius: 6px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def app_brand_header() -> None:
    """アプリ最上部のブランドヘッダー (明朝のロゴ + 等幅のサブ)."""
    st.markdown(
        '<div class="ledger-brand">'
        '<span class="mark">EDINET 開示台帳</span>'
        '<span class="sub">Human Capital &amp; Financials</span>'
        '<span class="tag">有価証券報告書</span>'
        "</div>",
        unsafe_allow_html=True,
    )


def ratio_bar_card_html(label: str, value: float | None) -> str:
    """比率を「ラベル + 等幅の値 + パリティバー」のカード HTML にして返す.

    バーの幅は 0〜100% にクリップ、色は 0%寄り=淡clay→100%寄り=淡teal。値が
    NULL のときは「—」と空のトラックを示す。company_lookup の人的資本表示に使う。
    """
    if value is None or pd.isna(value):
        shown, width, color = "—", 0.0, RULE
    else:
        v = float(value)
        shown = f"{v:.1f}%"
        width = max(0.0, min(100.0, v))
        color = _ratio_color(v)
    return (
        '<div class="ledger-rcard">'
        f'<div class="rc-label">{label}</div>'
        f'<div class="rc-value">{shown}</div>'
        f'<div class="rc-track"><div class="rc-fill" '
        f'style="width:{width:.1f}%;background:{color};"></div></div>'
        "</div>"
    )


def page_header(eyebrow: str, title: str, description: str | None = None) -> None:
    """各ページの「英字ラベル + 明朝見出し + 細罫 + 説明」バンドを描画する."""
    html = [
        f'<div class="ledger-eyebrow">{eyebrow}</div>',
        f'<h1 class="ledger-title">{title}</h1>',
        '<div class="ledger-rule"></div>',
    ]
    if description:
        html.append(f'<p class="ledger-desc">{description}</p>')
    st.markdown("".join(html), unsafe_allow_html=True)


# ------------------------------------------------------------------ #
#  Plotly テーマ
# ------------------------------------------------------------------ #


def style_plotly(fig: go.Figure, *, height: int | None = None) -> go.Figure:
    """Plotly 図にテーマ (フォント・背景・グリッド・余白) を適用する."""
    fig.update_layout(
        font=dict(family="Noto Sans JP, sans-serif", color=INK, size=12),
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        margin=dict(l=10, r=16, t=24, b=10),
        legend=dict(font=dict(size=11)),
    )
    fig.update_xaxes(gridcolor=RULE, zerolinecolor=RULE, linecolor=RULE)
    fig.update_yaxes(gridcolor=RULE, zerolinecolor=RULE, linecolor=RULE)
    if height is not None:
        fig.update_layout(height=height)
    return fig


def median_color(t: float) -> str:
    """0→1 を 淡藍 → 濃teal の連続色に写像する (箱ひげの中央値順の着色用)."""
    return _lerp_hex("#9DB8E8", GOOD, t)


# ------------------------------------------------------------------ #
#  表 (Styler) — 比率列を発散グラデーションで塗る
# ------------------------------------------------------------------ #


def ratio_table(
    df: pd.DataFrame,
    ratio_columns: list[str],
    *,
    vmin: float = 0.0,
    vmax: float = 100.0,
) -> pd.io.formats.style.Styler:
    """比率列を 0%寄り=淡clay→100%寄り=淡teal で塗った Styler を返す.

    matplotlib に依存しないよう、各セルの背景色を手動補間で算出する。Streamlit の
    st.dataframe は Styler の background-color / color を尊重する。
    """
    def _style_col(col: pd.Series) -> list[str]:
        return [
            f"background-color: {_ratio_color(v, vmin, vmax)}; color: {INK};"
            if pd.notna(v)
            else f"color: {INK_SOFT};"
            for v in col
        ]

    styler = df.style
    for col in ratio_columns:
        if col in df.columns:
            styler = styler.apply(_style_col, subset=[col])
    styler = styler.format(
        {c: "{:.1f}%" for c in ratio_columns if c in df.columns}, na_rep="—"
    )
    return styler
