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


@pytest.fixture(autouse=True)
def clear_streamlit_cache():
    import streamlit as st

    st.cache_data.clear()


def test_app_renders(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    sample_raw().to_csv(tmp_path / "ratings_raw.csv", index=False)
    PRICES.to_csv(tmp_path / "prices.csv", index=False)
    (tmp_path / "meta.json").write_text(json.dumps(
        {"fetched_at": "2026-01-15T12:00:00+00:00", "tickers_scanned": 3, "tickers_failed": [],
         "rating_actions": 6, "prices": True}))
    monkeypatch.setattr(config, "RAW_CSV", tmp_path / "ratings_raw.csv")
    monkeypatch.setattr(config, "PRICES_CSV", tmp_path / "prices.csv")
    monkeypatch.setattr(config, "META_JSON", tmp_path / "meta.json")
    monkeypatch.setattr(fetch, "load_universe", lambda: UNIVERSE)

    at = AppTest.from_file(str(config.ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value == "J.P. Morgan"
    subheaders = [s.value for s in at.subheader]
    assert subheaders[0].startswith("🟢 Buy / Overweight (2)")
    assert any(s.startswith("✂️ Cutting") and "(2)" in s for s in subheaders)

    at.sidebar.radio[0].set_value("All institutions").run()
    assert not at.exception
    assert at.title[0].value == "All institutions"


def test_app_empty_state(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(config, "RAW_CSV", tmp_path / "missing.csv")
    monkeypatch.setattr(config, "META_JSON", tmp_path / "missing.json")
    at = AppTest.from_file(str(config.ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert "No data yet" in at.info[0].value
