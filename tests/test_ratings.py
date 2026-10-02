"""Tests use synthetic rating actions shaped like yfinance's output (no network)."""
import json

import pandas as pd
import pytest

from ratings import config, data, fetch


@pytest.mark.parametrize("firm,key", [
    ("JP Morgan", "jpm"), ("J.P. Morgan", "jpm"), ("JPMorgan", "jpm"),
    ("B of A Securities", "bofa"), ("BofA Securities", "bofa"),
    ("Morgan Stanley", "ms"), ("Evercore ISI Group", "evercore"),
    ("Wells Fargo", "wells"), ("Sanford C. Bernstein", "bernstein"),
    ("UBS", "ubs"), ("Wolfe Research", "wolfe"),
])
def test_institution_matching(firm, key):
    assert config.institution_for(firm).key == key


@pytest.mark.parametrize("firm", ["Goldman Sachs", "Citigroup", "Deutsche Bank", "Mizuho", ""])
def test_untracked_firms(firm):
    assert config.institution_for(firm) is None


@pytest.mark.parametrize("grade,bucket", [
    ("Overweight", config.BUY), ("Strong Buy", config.BUY), ("Outperform", config.BUY),
    ("Neutral", config.HOLD), ("Equal-Weight", config.HOLD), ("Market Perform", config.HOLD),
    ("In-Line", config.HOLD), ("Underweight", config.SELL), ("Sell", config.SELL),
    ("Underperform", config.SELL), ("Something", config.OTHER),
])
def test_buckets(grade, bucket):
    assert config.bucket_for(grade) == bucket


def yahoo_frame(rows):
    df = pd.DataFrame(rows, columns=["GradeDate", "Firm", "ToGrade", "FromGrade", "Action",
                                     "priceTargetAction", "currentPriceTarget", "priorPriceTarget"])
    df["GradeDate"] = pd.to_datetime(df["GradeDate"])
    return df.set_index("GradeDate")


def test_normalize_history_drops_pre_2025():
    df = yahoo_frame([
        ("2025-03-01", "JP Morgan", "Overweight", "Neutral", "up", "Raises", 200, 150),
        ("2024-12-31", "JP Morgan", "Neutral", "", "init", "Announces", 150, 0),
    ])
    out = fetch.normalize_history(df, "AAPL")
    assert list(out.columns) == fetch.RAW_COLUMNS
    assert out["date"].tolist() == [pd.Timestamp("2025-03-01")]


UNIVERSE = pd.DataFrame({
    "Symbol": ["AAPL", "MSFT", "XOM"],
    "Security": ["Apple", "Microsoft", "Exxon"],
    "GICS Sector": ["Information Technology", "Information Technology", "Energy"],
})


def sample_raw():
    rows = [
        ("AAPL", "2025-02-01", "JP Morgan", "Neutral", "", "init", "Announces", 200, 0),
        ("AAPL", "2026-01-10", "JP Morgan", "Overweight", "Neutral", "up", "Raises", 260, 200),
        ("MSFT", "2025-06-01", "JP Morgan", "Overweight", "Overweight", "main", "Lowers", 450, 500),
        ("XOM", "2025-09-15", "JP Morgan", "Underweight", "Neutral", "down", "Lowers", 90, 120),
        ("XOM", "2025-05-01", "Morgan Stanley", "Equal-Weight", "", "reit", "Maintains", 110, 110),
        ("MSFT", "2025-07-01", "Goldman Sachs", "Buy", "", "main", "Raises", 600, 550),
    ]
    raw = pd.DataFrame(rows, columns=fetch.RAW_COLUMNS)
    raw["date"] = pd.to_datetime(raw["date"])
    return raw


PRICES = pd.DataFrame({"ticker": ["AAPL", "MSFT", "XOM"], "price": [200.0, 400.0, 100.0]})


def test_current_ratings_and_cuts():
    df = data.enrich(sample_raw(), UNIVERSE, PRICES)
    assert "Goldman Sachs" not in set(df["firm"])  # not a top-10 Extel firm
    jpm = df[df["institution"] == "jpm"]
    cur = data.current_ratings(jpm)
    # AAPL shows only its latest (upgraded) rating; newest first overall.
    assert cur["ticker"].tolist() == ["AAPL", "XOM", "MSFT"]
    assert cur.set_index("ticker").loc["AAPL", "bucket"] == config.BUY
    assert cur.set_index("ticker").loc["AAPL", "upside"] == pytest.approx(0.30)
    # Downgrade on XOM and price-target cut on MSFT (still Overweight).
    assert set(data.cuts(jpm)["ticker"]) == {"XOM", "MSFT"}


def test_consensus():
    cur = data.current_ratings(data.enrich(sample_raw(), UNIVERSE, PRICES))
    cons = data.consensus(cur).set_index("ticker")
    assert cons.loc["XOM", "Banks covering"] == 2
    assert cons.loc["XOM", "Net bullish"] == -1
    assert cons.index[0] in {"AAPL", "MSFT"}


def test_parse_tickers():
    assert data.parse_tickers("aapl, MSFT\n$nvda;brk.b  AAPL 123 ") == ["AAPL", "MSFT", "NVDA", "BRK.B"]


def test_tickers_from_csv():
    frame = pd.DataFrame({"Account": ["x", "y"], "Symbol": ["aapl", "msft"], "Qty": [1, 2]})
    assert data.tickers_from_csv(frame) == ["AAPL", "MSFT"]
    assert data.tickers_from_csv(pd.DataFrame({"anything": ["XOM"]})) == ["XOM"]


@pytest.mark.parametrize("counts,label", [
    ((0, 0, 0), "Not covered"), ((3, 1, 0), "Bullish"), ((1, 1, 1), "Mixed"), ((0, 1, 2), "Bearish"),
])
def test_consensus_label(counts, label):
    assert data.consensus_label(*counts) == label


def test_portfolio_view():
    df = data.enrich(sample_raw(), UNIVERSE, PRICES)
    view = data.portfolio_view(data.current_ratings(df), data.cuts(df), ["XOM", "AAPL", "TSLA"],
                               UNIVERSE, PRICES).set_index("ticker")
    assert view.loc["XOM", "jpm_grade"] == "Underweight"
    assert view.loc["XOM", "ms_grade"] == "Equal-Weight"
    assert view.loc["XOM", "covering"] == 2 and view.loc["XOM", "consensus"] == "Bearish"
    assert view.loc["XOM", "avg_pt"] == pytest.approx(100)
    assert view.loc["AAPL", "consensus"] == "Bullish"
    assert view.loc["AAPL", "upside"] == pytest.approx(0.30)
    assert view.loc["TSLA", "consensus"] == "Not covered"
    out = data.portfolio_export(view.reset_index())
    assert "J.P. Morgan" in out.columns and len(out) == 3


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    import streamlit as st

    st.cache_data.clear()
    sample_raw().to_csv(tmp_path / "ratings_raw.csv", index=False)
    PRICES.to_csv(tmp_path / "prices.csv", index=False)
    (tmp_path / "meta.json").write_text(json.dumps(
        {"fetched_at": "2026-01-15T12:00:00+00:00", "tickers_scanned": 3, "tickers_failed": [],
         "rating_actions": 6, "prices": True}))
    (tmp_path / "portfolio.txt").write_text("AAPL, XOM")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "RAW_CSV", tmp_path / "ratings_raw.csv")
    monkeypatch.setattr(config, "PRICES_CSV", tmp_path / "prices.csv")
    monkeypatch.setattr(config, "META_JSON", tmp_path / "meta.json")
    monkeypatch.setattr(config, "PORTFOLIO_TXT", tmp_path / "portfolio.txt")
    monkeypatch.setattr(fetch, "load_universe", lambda: UNIVERSE)
    return tmp_path


def page_html(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def run_page(page: str):
    """Run the full app (default page) or a single page function by name."""
    from streamlit.testing.v1 import AppTest

    if not page:
        return AppTest.from_file(str(config.ROOT / "app.py"), default_timeout=30).run()
    script = f"from ratings import pages, ui\nui.inject_css()\npages.{page}()\n"
    return AppTest.from_string(script, default_timeout=30).run()


def test_bank_page(app_data):
    at = run_page("")
    assert not at.exception
    html = page_html(at)
    assert "<h1>J.P. Morgan</h1>" in html
    assert [t.label for t in at.tabs] == ["Buy (2)", "Neutral (0)", "Sell (1)", "Cutting (2)"]
    assert "AAPL" in html and "Overweight" in html


def test_overview_page(app_data):
    at = run_page("overview_page")
    assert not at.exception
    assert "<h1>Overview</h1>" in page_html(at)


def test_portfolio_page(app_data):
    at = run_page("portfolio_page")
    assert not at.exception
    html = page_html(at)
    assert "How your holdings stack up" in html
    assert "Bearish" in html and "Bullish" in html  # XOM and AAPL


def test_app_empty_state(tmp_path, monkeypatch):
    import streamlit as st

    st.cache_data.clear()
    monkeypatch.setattr(config, "RAW_CSV", tmp_path / "missing.csv")
    monkeypatch.setattr(config, "META_JSON", tmp_path / "missing.json")
    at = run_page("")
    assert not at.exception
    assert "No data yet" in at.info[0].value


def test_fetch_symbols_merges(app_data, monkeypatch):
    extra = app_data / "extra.txt"
    monkeypatch.setattr(config, "EXTRA_TICKERS", extra)

    def fake_fetch(symbol):
        if symbol == "BAD":
            raise ConnectionError("nope")
        df = pd.DataFrame([(symbol, pd.Timestamp("2026-02-01"), "UBS", "Buy", "", "init", "Announces", 50, None)],
                          columns=fetch.RAW_COLUMNS)
        return df

    monkeypatch.setattr(fetch, "fetch_ticker", fake_fetch)
    monkeypatch.setattr(fetch, "fetch_prices", lambda syms: pd.DataFrame({"ticker": ["ARM"], "price": [40.0]}))
    res = fetch.fetch_symbols(["ARM", "BAD"])
    assert res == {"fetched": ["ARM"], "failed": ["BAD"]}
    raw = data.load_raw()
    assert set(raw["ticker"]) == {"AAPL", "MSFT", "XOM", "ARM"}  # old rows kept, new merged
    assert "ARM" in extra.read_text() and "BAD" not in extra.read_text()
    prices = pd.read_csv(config.PRICES_CSV).set_index("ticker")["price"]
    assert prices["ARM"] == 40.0 and prices["AAPL"] == 200.0
