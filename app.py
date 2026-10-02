"""Local dashboard: current (2025+) analyst ratings from the top 10 Extel banks.

Run:  streamlit run app.py
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from ratings import config, data, fetch

st.set_page_config(page_title="Bank Analyst Ratings", page_icon="📈", layout="wide")

OVERVIEW = "All institutions"
BUCKET_ICONS = {config.BUY: "🟢", config.HOLD: "🟡", config.SELL: "🔴", config.OTHER: "⚪"}


@st.cache_data(show_spinner=False)
def load(_stamp: float):
    raw = data.load_raw()
    if raw is None:
        return None
    return data.enrich(raw, fetch.load_universe(), data.load_prices())


def data_stamp() -> float:
    return config.RAW_CSV.stat().st_mtime if config.RAW_CSV.exists() else 0.0


def refresh() -> None:
    bar = st.sidebar.progress(0.0, text="Starting…")

    def cb(done: int, total: int, sym: str) -> None:
        bar.progress(done / total, text=f"Fetching {sym} ({done}/{total})")

    try:
        meta = fetch.fetch_all(progress=cb)
    except RuntimeError as exc:
        bar.empty()
        st.sidebar.error(str(exc))
        return
    bar.empty()
    st.sidebar.success(f"Loaded {meta['rating_actions']:,} rating actions.")
    st.cache_data.clear()


def rating_table(df: pd.DataFrame, show_bank: bool = False) -> None:
    cols = (["Bank"] if show_bank else []) + [
        "Date", "Ticker", "Company", "Sector", "Rating", "Prior rating", "Action",
        "Price target", "Prior target", "Price", "Upside",
    ]
    names = {i.key: i.name for i in config.INSTITUTIONS}
    view = pd.DataFrame({
        "Bank": df["institution"].map(names),
        "Date": df["date"].dt.date,
        "Ticker": df["ticker"],
        "Company": df["company"],
        "Sector": df["sector"],
        "Rating": df["to_grade"],
        "Prior rating": df["from_grade"],
        "Action": df["action_label"],
        "Price target": df["pt_current"],
        "Prior target": df["pt_prior"],
        "Price": df["price"],
        "Upside": df["upside"] * 100,
    })[cols]
    st.dataframe(
        view,
        hide_index=True,
        width="stretch",
        height=min(38 + 35 * len(view), 560),
        column_config={
            "Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
            "Price target": st.column_config.NumberColumn(format="$%.2f"),
            "Prior target": st.column_config.NumberColumn(format="$%.2f"),
            "Price": st.column_config.NumberColumn(format="$%.2f"),
            "Upside": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar:
        st.subheader("Filters")
        query = st.text_input("Ticker or company", placeholder="e.g. NVDA").strip().lower()
        sectors = sorted(df["sector"].dropna().unique())
        chosen = st.multiselect("Sector", sectors)
        start = st.date_input(
            "Ratings since",
            value=date.fromisoformat(config.START_DATE),
            min_value=date.fromisoformat(config.START_DATE),
        )
    if query:
        df = df[df["ticker"].str.lower().str.contains(query, regex=False)
                | df["company"].fillna("").str.lower().str.contains(query, regex=False)]
    if chosen:
        df = df[df["sector"].isin(chosen)]
    return df[df["date"] >= pd.Timestamp(start)]


def institution_page(inst: config.Institution, df: pd.DataFrame) -> None:
    mine = df[df["institution"] == inst.key]
    current = data.current_ratings(mine)
    cut = data.cuts(mine)
    tie = " (tied)" if sum(i.extel_rank == inst.extel_rank for i in config.INSTITUTIONS) > 1 else ""

    st.title(inst.name)
    st.caption(f"Extel 2025 All-America Research · #{inst.extel_rank}{tie} by published positions · "
               f"latest rating per stock issued since {config.START_DATE}, newest first")

    counts = current["bucket"].value_counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟢 Buy / Overweight", int(counts.get(config.BUY, 0)))
    c2.metric("🟡 Neutral / Equal-weight", int(counts.get(config.HOLD, 0)))
    c3.metric("🔴 Sell / Underweight", int(counts.get(config.SELL, 0)))
    c4.metric("✂️ Downgrades & target cuts", len(cut))

    if current.empty and cut.empty:
        st.info("No 2025–2026 ratings from this bank match the current filters.")
        return

    for bucket in config.BUCKET_ORDER:
        part = current[current["bucket"] == bucket]
        if bucket == config.OTHER and part.empty:
            continue
        st.subheader(f"{BUCKET_ICONS[bucket]} {bucket} ({len(part)})")
        if part.empty:
            st.caption("None.")
        else:
            rating_table(part)

    st.subheader(f"✂️ Cutting: downgrades & price-target cuts ({len(cut)})")
    st.caption("Every downgrade or lowered price target since "
               f"{config.START_DATE}, including on stocks the bank still rates Buy.")
    if cut.empty:
        st.caption("None.")
    else:
        rating_table(cut)


def overview_page(df: pd.DataFrame) -> None:
    current = data.current_ratings(df)
    st.title("All institutions")
    st.caption(f"Top 10 Extel 2025 All-America research firms · current ratings issued since {config.START_DATE}")

    rows = []
    for inst in config.INSTITUTIONS:
        mine = current[current["institution"] == inst.key]
        counts = mine["bucket"].value_counts()
        rows.append({
            "Extel rank": inst.extel_rank,
            "Institution": inst.name,
            "🟢 Buy / OW": int(counts.get(config.BUY, 0)),
            "🟡 Neutral": int(counts.get(config.HOLD, 0)),
            "🔴 Sell / UW": int(counts.get(config.SELL, 0)),
            "✂️ Cuts": len(data.cuts(df[df["institution"] == inst.key])),
            "Latest action": mine["date"].max().date() if not mine.empty else None,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.subheader("Where the banks agree")
    st.caption("Stocks ranked by number of Buy ratings minus Sell ratings across the top 10 banks.")
    cons = data.consensus(current)
    st.dataframe(cons, hide_index=True, width="stretch", height=420,
                 column_config={"price": st.column_config.NumberColumn("Price", format="$%.2f")})

    st.subheader("Latest rating actions, all banks")
    rating_table(df.head(200), show_bank=True)


def main() -> None:
    with st.sidebar:
        st.header("📈 Bank Analyst Ratings")
        labels = [OVERVIEW] + [f"#{i.extel_rank} {i.name}" for i in config.INSTITUTIONS]
        choice = st.radio("Institution", labels, index=1)

        meta = data.load_meta()
        if meta:
            fetched = datetime.fromisoformat(meta["fetched_at"]).astimezone()
            st.caption(f"Data from Yahoo Finance, refreshed {fetched:%Y-%m-%d %H:%M}. "
                       f"{meta['tickers_scanned']} stocks scanned.")
        if st.button("🔄 Refresh data from Yahoo Finance", width="stretch"):
            refresh()

    df = load(data_stamp())
    if df is None:
        st.title("Bank Analyst Ratings")
        st.info("No data yet. Click **🔄 Refresh data from Yahoo Finance** in the sidebar "
                "(takes a few minutes the first time), or run `python -m ratings.fetch`.")
        return

    df = apply_filters(df)
    if choice == OVERVIEW:
        overview_page(df)
    else:
        inst = config.INSTITUTIONS[labels.index(choice) - 1]
        institution_page(inst, df)


main()
