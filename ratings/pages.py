"""The dashboard's pages and shared sidebar (wired together in app.py)."""
from __future__ import annotations

from datetime import date, datetime

import altair as alt
import pandas as pd
import streamlit as st

from . import config, data, fetch, ui

CONSENSUS_TONE = {"Bullish": config.BUY, "Mixed": config.HOLD, "Bearish": config.SELL}


# ---------------------------------------------------------------- data loading
@st.cache_data(show_spinner=False)
def load(_stamp: float):
    raw = data.load_raw()
    if raw is None:
        return None
    return data.enrich(raw, fetch.load_universe(), data.load_prices())


def data_stamp() -> float:
    stamps = [p.stat().st_mtime for p in (config.RAW_CSV, config.PRICES_CSV) if p.exists()]
    return max(stamps, default=0.0)


def progress_bar(where):
    bar = where.progress(0.0, text="Starting…")

    def cb(done: int, total: int, sym: str) -> None:
        bar.progress(done / total, text=f"Fetching {sym} ({done}/{total})")

    return bar, cb


def refresh_all() -> None:
    bar, cb = progress_bar(st.sidebar)
    try:
        meta = fetch.fetch_all(progress=cb)
    except RuntimeError as exc:
        bar.empty()
        st.sidebar.error(str(exc))
        return
    bar.empty()
    st.sidebar.success(f"Loaded {meta['rating_actions']:,} rating actions.")
    st.cache_data.clear()


def sidebar() -> None:
    with st.sidebar:
        meta = data.load_meta()
        if meta:
            fetched = datetime.fromisoformat(meta["fetched_at"]).astimezone()
            st.caption(f"**Data:** Yahoo Finance  \n**Updated:** {fetched:%b %d, %Y · %H:%M}  \n"
                       f"**Stocks scanned:** {meta['tickers_scanned']:,}")
        else:
            st.caption("No data downloaded yet.")
        if st.button("Refresh data", icon=":material/refresh:", width="stretch", type="primary"):
            refresh_all()
        st.caption(f"Only ratings issued since {date.fromisoformat(config.START_DATE):%b %d, %Y} are shown.")


def empty_state() -> None:
    ui.page_header("Bank Analyst Ratings", eyebrow="Welcome")
    with st.container(key="card-empty"):
        ui.card_heading("No data yet",
                        "Click Refresh data in the sidebar to download the latest ratings. "
                        "The first download scans about 500 stocks and takes a few minutes.")
        st.info("No data yet. Click **Refresh data** in the sidebar, or run `python -m ratings.fetch`.")


def filter_row(df: pd.DataFrame, key: str) -> pd.DataFrame:
    c1, c2, c3 = st.columns([2, 2, 1.2])
    query = c1.text_input("Search", placeholder="Ticker or company, e.g. NVDA", key=f"{key}-q",
                          label_visibility="collapsed").strip().lower()
    chosen = c2.multiselect("Sector", sorted(df["sector"].dropna().unique()), key=f"{key}-sec",
                            placeholder="All sectors", label_visibility="collapsed")
    start = c3.date_input("Since", value=date.fromisoformat(config.START_DATE),
                          min_value=date.fromisoformat(config.START_DATE), key=f"{key}-since",
                          label_visibility="collapsed")
    if query:
        df = df[df["ticker"].str.lower().str.contains(query, regex=False)
                | df["company"].fillna("").str.lower().str.contains(query, regex=False)]
    if chosen:
        df = df[df["sector"].isin(chosen)]
    return df[df["date"] >= pd.Timestamp(start)]


# ---------------------------------------------------------------- pages
def overview_page() -> None:
    df = load(data_stamp())
    if df is None:
        return empty_state()
    ui.page_header("Overview", eyebrow="Top 10 Extel 2025 research firms",
                   meta="How the top US research desks currently rate the S&P 500")
    df = filter_row(df, "ov")
    current = data.current_ratings(df)
    counts = current["bucket"].value_counts()
    recent = df[df["date"] >= pd.Timestamp.today().normalize() - pd.Timedelta(days=30)]
    n = max(len(current), 1)
    ui.kpis([
        ("📊", "blue", f"{len(current):,}", "Current ratings", f"{current['ticker'].nunique():,} stocks"),
        ("🟢", "buy", f"{counts.get(config.BUY, 0) / n:.0%}", "Rated Buy / Overweight",
         f"{counts.get(config.BUY, 0):,} ratings"),
        ("🔴", "sell", f"{counts.get(config.SELL, 0) / n:.0%}", "Rated Sell / Underweight",
         f"{counts.get(config.SELL, 0):,} ratings"),
        ("✂️", "hold", f"{len(data.cuts(recent)):,}", "Cuts in last 30 days", "Downgrades + lower targets"),
    ])

    left, right = st.columns([1.15, 1], gap="medium")
    with left, st.container(key="card-mix"):
        ui.card_heading("Rating mix by bank", "Current ratings per bank, in Extel rank order")
        rows = []
        for inst in config.INSTITUTIONS:
            mine = current[current["institution"] == inst.key]["bucket"].value_counts()
            for bucket in (config.BUY, config.HOLD, config.SELL):
                rows.append({"Bank": inst.name, "Rating": ui.TONES[bucket][1], "Count": int(mine.get(bucket, 0)),
                             "order": [config.BUY, config.HOLD, config.SELL].index(bucket)})
        chart = (
            alt.Chart(pd.DataFrame(rows))
            .mark_bar(height=16, stroke="#ffffff", strokeWidth=2)
            .encode(
                y=alt.Y("Bank:N", sort=[i.name for i in config.INSTITUTIONS], title=None,
                        axis=alt.Axis(labelColor="#5b6474", labelFontSize=12, ticks=False, domain=False)),
                x=alt.X("Count:Q", stack="zero", title=None,
                        axis=alt.Axis(grid=True, gridColor="#eef0f4", labelColor="#8a93a3",
                                      domain=False, ticks=False)),
                color=alt.Color("Rating:N", scale=alt.Scale(domain=[ui.TONES[b][1] for b in ui.CHART_COLORS],
                                                            range=list(ui.CHART_COLORS.values())),
                                legend=alt.Legend(orient="top", title=None, labelColor="#5b6474")),
                order=alt.Order("order:Q"),
                tooltip=["Bank", "Rating", "Count"],
            )
            .properties(height=360)
            .configure_view(stroke=None)
            .configure(font=ui.FONT_STACK, background="#ffffff")
        )
        st.altair_chart(chart, width="stretch", theme=None)

    with right, st.container(key="card-agree"):
        ui.card_heading("Where the banks agree", "Most Buy ratings minus Sell ratings across the top 10")
        cons = data.consensus(current).head(10)
        if cons.empty:
            ui.rating_list(cons)
        else:
            body = "".join(
                f"<tr><td>{ui.company_cell(r['ticker'], r['company'])}</td>"
                f"<td>{ui.dist_bar(int(r[config.BUY]), int(r[config.HOLD]), int(r[config.SELL]))}</td>"
                f"<td class='num'>{ui.money(r['price'])}</td></tr>"
                for _, r in cons.iterrows()
            )
            st.markdown("<div class='rlist-wrap'><table class='rlist'><thead><tr><th>Stock</th>"
                        "<th>Bank ratings</th><th class='num'>Price</th></tr></thead>"
                        f"<tbody>{body}</tbody></table></div>", unsafe_allow_html=True)
        ui.table_and_download(data.consensus(current), "bank_consensus.csv", "dl-cons")

    with st.container(key="card-latest"):
        ui.card_heading("Latest rating actions", "Every bank, newest first")
        ui.rating_list(df, show_bank=True, limit=25)
        ui.table_and_download(ui.export_frame(df), "latest_rating_actions.csv", "dl-latest")


def bank_page() -> None:
    df = load(data_stamp())
    if df is None:
        return empty_state()
    names = [i.name for i in config.INSTITUTIONS]
    choice = st.pills("Institution", names, default=names[0], key="bank", label_visibility="collapsed")
    inst = config.INSTITUTIONS[names.index(choice or names[0])]
    tie = " (tied)" if sum(i.extel_rank == inst.extel_rank for i in config.INSTITUTIONS) > 1 else ""
    ui.page_header(inst.name, eyebrow="Bank ratings",
                   meta="Latest rating per stock, newest first",
                   badge=f"Extel 2025 · #{inst.extel_rank}{tie}")

    df = filter_row(df, "bank")
    mine = df[df["institution"] == inst.key]
    current = data.current_ratings(mine)
    cut = data.cuts(mine)
    counts = current["bucket"].value_counts()
    ui.kpis([
        ("🟢", "buy", int(counts.get(config.BUY, 0)), "Buy / Overweight"),
        ("🟡", "hold", int(counts.get(config.HOLD, 0)), "Neutral / Equal-weight"),
        ("🔴", "sell", int(counts.get(config.SELL, 0)), "Sell / Underweight"),
        ("✂️", "blue", len(cut), "Downgrades & target cuts"),
    ])

    with st.container(key="card-bank"):
        groups = [(b, current[current["bucket"] == b]) for b in config.BUCKET_ORDER]
        groups = [(b, g) for b, g in groups if b != config.OTHER or not g.empty]
        labels = [f"{ui.TONES[b][1]} ({len(g)})" for b, g in groups] + [f"Cutting ({len(cut)})"]
        tabs = st.tabs(labels)
        for tab, (bucket, part) in zip(tabs, groups):
            with tab:
                ui.rating_list(part)
                ui.table_and_download(ui.export_frame(part, show_bank=False),
                                      f"{inst.key}_{ui.TONES[bucket][0]}.csv", f"dl-{bucket}")
        with tabs[-1]:
            st.caption("Every downgrade or lowered price target, including on stocks the bank still rates Buy.")
            ui.rating_list(cut)
            ui.table_and_download(ui.export_frame(cut, show_bank=False), f"{inst.key}_cuts.csv", "dl-cut")


def load_saved_portfolio() -> str:
    return config.PORTFOLIO_TXT.read_text() if config.PORTFOLIO_TXT.exists() else ""


def portfolio_page() -> None:
    df = load(data_stamp())
    if df is None:
        return empty_state()
    ui.page_header("Portfolio screener", eyebrow="Your holdings",
                   meta="See how every top-10 bank currently rates the stocks you own")

    with st.container(key="card-input"):
        ui.card_heading("Your holdings", "Paste tickers, or upload a CSV export from your brokerage")
        c1, c2 = st.columns([1.4, 1], gap="medium")
        text = c1.text_area("Tickers", value=load_saved_portfolio(), height=110,
                            placeholder="AAPL, MSFT, NVDA, JPM", label_visibility="collapsed")
        upload = c2.file_uploader("CSV with a Ticker or Symbol column", type="csv",
                                  label_visibility="collapsed")
        tickers = data.parse_tickers(text)
        if upload is not None:
            tickers += [t for t in data.tickers_from_csv(pd.read_csv(upload)) if t not in tickers]
        if tickers and ", ".join(tickers) != ", ".join(data.parse_tickers(load_saved_portfolio())):
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            config.PORTFOLIO_TXT.write_text(", ".join(tickers))

        universe = fetch.load_universe()
        missing = [t for t in tickers if t not in set(universe["Symbol"])]
        if missing:
            st.warning(f"{len(missing)} ticker(s) aren't in the S&P 500 list yet: {', '.join(missing)}. "
                       "Fetch them to include their ratings (they'll be kept for future refreshes).")
            if st.button(f"Fetch ratings for {', '.join(missing)}", icon=":material/download:"):
                bar, cb = progress_bar(st)
                try:
                    res = fetch.fetch_symbols(missing, progress=cb)
                except RuntimeError as exc:
                    st.error(str(exc))
                else:
                    if res["failed"]:
                        st.error(f"Couldn't fetch: {', '.join(res['failed'])}")
                    st.cache_data.clear()
                    st.rerun()
                finally:
                    bar.empty()

    if not tickers:
        st.markdown('<div class="empty">Add some tickers above to screen your portfolio.</div>',
                    unsafe_allow_html=True)
        return

    current = data.current_ratings(df)
    view = data.portfolio_view(current, data.cuts(df), tickers, universe, data.load_prices())
    labels = view["consensus"].value_counts()
    ui.kpis([
        ("💼", "blue", len(view), "Holdings screened", f"{int((view['covering'] > 0).sum())} covered by top-10 banks"),
        ("🟢", "buy", int(labels.get("Bullish", 0)), "Bullish consensus", "Mostly Buy / Overweight"),
        ("🔴", "sell", int((view["sell"] > 0).sum()), "Have a Sell rating", "At least one top-10 bank"),
        ("✂️", "hold", int(view["cuts_90d"].sum()), "Cuts in last 90 days", "Downgrades + lower targets"),
    ])

    with st.container(key="card-grid"):
        ui.card_heading("How your holdings stack up",
                        "Each bank's current rating · B/N/S = Buy/Neutral/Sell count · "
                        "hover a rating for its exact wording, date and price target")
        bank_heads = "".join(f"<th class='bank' title='{ui.esc(i.name)}'>{ui.esc(i.short)}</th>"
                             for i in config.INSTITUTIONS)
        body = []
        for _, r in view.iterrows():
            cells = []
            for inst in config.INSTITUTIONS:
                bucket = r[f"{inst.key}_bucket"]
                bucket = bucket if isinstance(bucket, str) else None
                tip = ""
                if bucket:
                    tip = f"{inst.name}: {r[f'{inst.key}_grade']} · {r[f'{inst.key}_date']:%b %d, %Y}"
                    if not pd.isna(r[f"{inst.key}_pt"]):
                        tip += f" · PT ${r[f'{inst.key}_pt']:,.0f}"
                cells.append(f"<td class='bank'>{ui.pill(ui.TONES.get(bucket, ('', ''))[1] if bucket else None, bucket, tip)}</td>")
            tone = CONSENSUS_TONE.get(r["consensus"])
            body.append(
                f"<tr><td>{ui.company_cell(r['ticker'], r['company'])}</td>"
                f"<td>{ui.pill(r['consensus'], tone) if tone else '<span class=muted>' + r['consensus'] + '</span>'}"
                f"<div style='margin-top:6px'>{ui.dist_bar(r['buy'], r['hold'], r['sell'], compact=True)}</div></td>"
                + "".join(cells)
                + f"<td class='num'>{ui.money(r['avg_pt'])}</td>"
                f"<td class='num'>{ui.upside_chip(r['upside'])}</td>"
                f"<td class='num'>{r['cuts_90d'] or '<span class=muted>0</span>'}</td></tr>"
            )
        st.markdown(
            "<div class='rlist-wrap'><table class='rlist grid'><thead><tr><th>Stock</th><th>Consensus</th>"
            f"{bank_heads}<th class='num'>Avg target</th><th class='num'>Upside</th>"
            f"<th class='num'>Cuts 90d</th></tr></thead><tbody>{''.join(body)}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        ui.table_and_download(data.portfolio_export(view), "portfolio_screen.csv", "dl-port")

    with st.container(key="card-detail"):
        ui.card_heading("Holding detail", "Every 2025–2026 action on this stock by the top-10 banks")
        pick = st.selectbox("Holding", tickers, label_visibility="collapsed",
                            format_func=lambda t: f"{t} · {view.set_index('ticker').loc[t, 'company']}")
        history = df[df["ticker"] == pick]
        ui.rating_list(history, show_bank=True)
        ui.table_and_download(ui.export_frame(history), f"{pick}_rating_history.csv", "dl-hist")
