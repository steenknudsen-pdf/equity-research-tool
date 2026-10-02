"""Styling and small HTML components for the dashboard (light, card-based)."""
from __future__ import annotations

import html
import math

import pandas as pd
import streamlit as st

from . import config

# Rating buckets use a fixed polarity scale; every pill also carries its text,
# so meaning never depends on color alone.
TONES = {
    config.BUY: ("buy", "Buy"),
    config.HOLD: ("hold", "Neutral"),
    config.SELL: ("sell", "Sell"),
    config.OTHER: ("other", "Other"),
}
FONT_STACK = "Inter, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
CHART_COLORS = {config.BUY: "#1f9d55", config.HOLD: "#a9afbb", config.SELL: "#d64545"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {
  --bg: #f4f6fa; --card: #ffffff; --line: #e9ecf2; --ink: #1d2433; --ink-2: #5b6474;
  --ink-3: #8a93a3; --accent: #2a78d6; --accent-soft: #eaf2fc;
  --buy: #157a3f; --buy-bg: #e5f5ec; --hold: #4d5566; --hold-bg: #eef0f4;
  --sell: #b42f2f; --sell-bg: #fdecec; --other: #6b5a2e; --other-bg: #f7f1e1;
  --shadow: 0 1px 2px rgba(16,24,40,.04), 0 4px 16px rgba(16,24,40,.06);
}
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stMarkdown, .stApp table {
  font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
}
.block-container { padding-top: 2.2rem; max-width: 1400px; }
header[data-testid="stHeader"] { background: transparent; }
section[data-testid="stSidebar"] { border-right: 1px solid var(--line); }
section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }

/* Cards: any st.container whose key starts with "card" */
[class*="st-key-card"] {
  background: var(--card); border: 1px solid var(--line) !important; border-radius: 16px;
  box-shadow: var(--shadow); padding: 20px 22px 16px;
}
.card-title { font-size: 1.02rem; font-weight: 600; color: var(--ink); margin: 0 0 2px; }
.card-sub { font-size: .82rem; color: var(--ink-3); margin: 0 0 12px; }

/* Page header */
.page-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px;
  flex-wrap: wrap; margin-bottom: 6px; }
.page-head h1 { font-size: 1.75rem; font-weight: 700; margin: 0; padding: 0; color: var(--ink); }
.page-head .eyebrow { font-size: .78rem; font-weight: 600; letter-spacing: .06em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 4px; }
.page-head .meta { color: var(--ink-3); font-size: .85rem; }
.badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px;
  border-radius: 999px; background: var(--accent-soft); color: var(--accent);
  font-size: .78rem; font-weight: 600; }

/* KPI tiles */
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 16px;
  margin: 14px 0 18px; }
.kpi { background: var(--card); border: 1px solid var(--line); border-radius: 16px;
  box-shadow: var(--shadow); padding: 16px 18px; display: flex; gap: 14px; align-items: center; }
.kpi .ic { width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center;
  font-size: 1.15rem; flex: none; }
.kpi .lbl { color: var(--ink-2); font-size: .8rem; font-weight: 500; }
.kpi .val { color: var(--ink); font-size: 1.55rem; font-weight: 700; line-height: 1.2; }
.kpi .sub { color: var(--ink-3); font-size: .75rem; }
.ic.blue { background: var(--accent-soft); } .ic.buy { background: var(--buy-bg); }
.ic.hold { background: var(--hold-bg); } .ic.sell { background: var(--sell-bg); }

/* Pills */
.pill { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: .76rem;
  font-weight: 600; white-space: nowrap; }
.pill.buy { background: var(--buy-bg); color: var(--buy); }
.pill.hold { background: var(--hold-bg); color: var(--hold); }
.pill.sell { background: var(--sell-bg); color: var(--sell); }
.pill.other { background: var(--other-bg); color: var(--other); }
.pill.none { background: transparent; color: var(--ink-3); font-weight: 500; }
.chip { font-size: .78rem; font-weight: 600; white-space: nowrap; }
.chip.up { color: var(--buy); } .chip.down { color: var(--sell); } .chip.flat { color: var(--ink-3); }

/* Rating list */
.rlist { width: 100%; border-collapse: separate; border-spacing: 0; }
.rlist-wrap { max-height: 620px; overflow: auto; margin: 0 -6px; }
.rlist th { position: sticky; top: 0; background: var(--card); z-index: 1; text-align: left;
  font-size: .72rem; font-weight: 600; letter-spacing: .04em; text-transform: uppercase;
  color: var(--ink-3); padding: 8px 10px; border-bottom: 1px solid var(--line); }
.rlist td { padding: 11px 10px; border-bottom: 1px solid var(--line); font-size: .86rem;
  color: var(--ink); vertical-align: middle; }
.rlist tr:last-child td { border-bottom: none; }
.rlist tr:hover td { background: #fafbfd; }
.rlist .num { text-align: right; font-variant-numeric: tabular-nums; }
.rlist th.num { text-align: right; }
.co { display: flex; align-items: center; gap: 10px; min-width: 150px; }
.av { width: 34px; height: 34px; border-radius: 10px; background: var(--accent-soft);
  color: var(--accent); display: grid; place-items: center; font-size: .68rem; font-weight: 700;
  flex: none; letter-spacing: -.02em; }
.co .tk { font-weight: 600; } .co .nm { color: var(--ink-3); font-size: .78rem;
  max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.muted { color: var(--ink-3); } .strike { color: var(--ink-3); text-decoration: line-through;
  font-size: .78rem; margin-left: 4px; }
.arrow { color: var(--ink-3); margin: 0 4px; }

/* Distribution bar (Buy / Neutral / Sell) */
.dist { display: flex; height: 8px; border-radius: 999px; overflow: hidden; gap: 2px;
  background: var(--card); min-width: 90px; }
.dist span { display: block; height: 100%; }
.dist .b { background: #1f9d55; } .dist .h { background: #a9afbb; } .dist .s { background: #d64545; }
.dist-lbl { font-size: .72rem; color: var(--ink-3); margin-top: 4px; white-space: nowrap; }

/* Portfolio grid */
.grid td, .grid th { padding-left: 6px; padding-right: 6px; }
.grid .co { min-width: 120px; } .grid .co .nm { max-width: 115px; }
.grid .pill { padding: 3px 8px; } .grid .dist { min-width: 80px; }
.grid td.bank { text-align: center; padding: 8px 3px; }
.grid th.bank { text-align: center; padding: 8px 4px; }
.empty { text-align: center; padding: 28px 10px; color: var(--ink-3); font-size: .9rem; }

/* Bank picker pills */
[data-testid="stPills"] button { border-radius: 999px !important; }
div[data-testid="stTabs"] button p { font-weight: 600; }
div[data-testid="stExpander"] details { border-radius: 12px; border-color: var(--line); }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)) or value is pd.NA:
        return ""
    return html.escape(str(value))


def money(value) -> str:
    if value is None or pd.isna(value):
        return '<span class="muted">—</span>'
    return f"${value:,.2f}"


def upside_chip(value) -> str:
    if value is None or pd.isna(value):
        return '<span class="muted">—</span>'
    pct = value * 100
    cls = "up" if pct > 0.05 else "down" if pct < -0.05 else "flat"
    arrow = "▲" if cls == "up" else "▼" if cls == "down" else "•"
    return f'<span class="chip {cls}">{arrow} {pct:+.1f}%</span>'


def pill(grade, bucket, title: str = "") -> str:
    if not bucket or pd.isna(bucket):
        return '<span class="pill none">—</span>'
    cls, _ = TONES.get(bucket, TONES[config.OTHER])
    t = f' title="{esc(title)}"' if title else ""
    return f'<span class="pill {cls}"{t}>{esc(grade) or TONES[bucket][1]}</span>'


def avatar(ticker: str) -> str:
    return f'<div class="av">{esc(ticker[:5])}</div>'


def company_cell(ticker, company) -> str:
    return (f'<div class="co">{avatar(ticker)}<div><div class="tk">{esc(ticker)}</div>'
            f'<div class="nm">{esc(company)}</div></div></div>')


def page_header(title: str, eyebrow: str = "", meta: str = "", badge: str = "") -> None:
    st.markdown(
        '<div class="page-head"><div>'
        + (f'<div class="eyebrow">{esc(eyebrow)}</div>' if eyebrow else "")
        + f"<h1>{esc(title)}</h1>"
        + (f'<div class="meta">{esc(meta)}</div>' if meta else "")
        + "</div>"
        + (f'<span class="badge">{esc(badge)}</span>' if badge else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def kpis(items: list[tuple[str, str, object, str]]) -> None:
    """items: (icon, tone, value, label[, sub])"""
    cells = []
    for item in items:
        icon, tone, value, label, *rest = item
        sub = f'<div class="sub">{esc(rest[0])}</div>' if rest and rest[0] else ""
        cells.append(f'<div class="kpi"><div class="ic {tone}">{icon}</div><div>'
                     f'<div class="lbl">{esc(label)}</div><div class="val">{esc(value)}</div>{sub}</div></div>')
    st.markdown(f'<div class="kpis">{"".join(cells)}</div>', unsafe_allow_html=True)


def card_heading(title: str, sub: str = "") -> None:
    st.markdown(f'<div class="card-title">{esc(title)}</div>'
                + (f'<div class="card-sub">{esc(sub)}</div>' if sub else ""), unsafe_allow_html=True)


def dist_bar(buy: int, hold: int, sell: int, compact: bool = False) -> str:
    total = buy + hold + sell
    if not total:
        return '<span class="muted">Not covered</span>'
    segs = "".join(
        f'<span class="{c}" style="width:{n / total * 100:.1f}%"></span>'
        for c, n in (("b", buy), ("h", hold), ("s", sell)) if n
    )
    return (f'<div class="dist" title="{buy} Buy · {hold} Neutral · {sell} Sell">{segs}</div>'
            f'<div class="dist-lbl">' + (f"{buy}B · {hold}N · {sell}S" if compact
                                         else f"{buy} Buy · {hold} Neutral · {sell} Sell") + "</div>")


def rating_list(df: pd.DataFrame, show_bank: bool = False, limit: int | None = None) -> None:
    """Readable list of rating actions (newest first)."""
    if df.empty:
        st.markdown('<div class="empty">Nothing here for the current filters.</div>', unsafe_allow_html=True)
        return
    names = {i.key: i.name for i in config.INSTITUTIONS}
    rows = df if limit is None else df.head(limit)
    head = ("<tr>" + ("<th>Bank</th>" if show_bank else "")
            + "<th>Stock</th><th>Rating</th><th>Action</th><th class='num'>Price target</th>"
              "<th class='num'>Price</th><th class='num'>Upside</th><th class='num'>Date</th></tr>")
    body = []
    for r in rows.itertuples(index=False):
        prior = ""
        if isinstance(r.from_grade, str) and r.from_grade and r.from_grade != r.to_grade:
            prior = f'<span class="muted">{esc(r.from_grade)}</span><span class="arrow">→</span>'
        pt = money(r.pt_current)
        if not pd.isna(r.pt_prior) and not pd.isna(r.pt_current) and r.pt_prior != r.pt_current:
            pt += f'<span class="strike">${r.pt_prior:,.0f}</span>'
        body.append(
            "<tr>"
            + (f"<td>{esc(names.get(r.institution, ''))}</td>" if show_bank else "")
            + f"<td>{company_cell(r.ticker, r.company)}</td>"
            + f"<td>{prior}{pill(r.to_grade, r.bucket)}</td>"
            + f'<td class="muted">{esc(r.action_label)}</td>'
            + f'<td class="num">{pt}</td>'
            + f'<td class="num">{money(r.price)}</td>'
            + f'<td class="num">{upside_chip(r.upside)}</td>'
            + f'<td class="num muted">{r.date:%b %d, %Y}</td>'
            + "</tr>"
        )
    more = ""
    if limit is not None and len(df) > limit:
        more = f'<div class="card-sub" style="margin-top:8px">Showing {limit} of {len(df)}. Open the table view for all rows.</div>'
    st.markdown(f'<div class="rlist-wrap"><table class="rlist"><thead>{head}</thead>'
                f'<tbody>{"".join(body)}</tbody></table></div>{more}', unsafe_allow_html=True)


def export_frame(df: pd.DataFrame, show_bank: bool = True) -> pd.DataFrame:
    names = {i.key: i.name for i in config.INSTITUTIONS}
    out = pd.DataFrame({
        "Bank": df["institution"].map(names),
        "Date": df["date"].dt.date,
        "Ticker": df["ticker"],
        "Company": df["company"],
        "Sector": df["sector"],
        "Rating": df["to_grade"],
        "Rating group": df["bucket"],
        "Prior rating": df["from_grade"],
        "Action": df["action_label"],
        "Price target": df["pt_current"],
        "Prior target": df["pt_prior"],
        "Price": df["price"],
        "Upside %": (df["upside"] * 100).round(1),
    })
    return out if show_bank else out.drop(columns="Bank")


def table_and_download(df: pd.DataFrame, filename: str, key: str) -> None:
    """Spreadsheet-style view plus CSV download, tucked into an expander."""
    with st.expander(f"Table view & CSV download ({len(df)} rows)"):
        st.dataframe(
            df, hide_index=True, width="stretch", height=min(38 + 35 * len(df), 420),
            column_config={
                "Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "Price target": st.column_config.NumberColumn(format="$%.2f"),
                "Prior target": st.column_config.NumberColumn(format="$%.2f"),
                "Price": st.column_config.NumberColumn(format="$%.2f"),
                "Avg price target": st.column_config.NumberColumn(format="$%.2f"),
                "Upside %": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )
        st.download_button("⬇ Download CSV", df.to_csv(index=False).encode(), file_name=filename,
                           mime="text/csv", key=key)
