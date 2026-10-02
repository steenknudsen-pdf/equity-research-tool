"""Download analyst rating history from Yahoo Finance (free, no API key).

Yahoo exposes each stock's upgrade/downgrade history, including the firm,
the new and prior rating, and price targets. We pull it for every stock in
the universe (S&P 500 plus data/extra_tickers.txt) and keep 2025+ actions.

Run from the repo root:  python -m ratings.fetch
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable

import pandas as pd

from . import config

RAW_COLUMNS = [
    "ticker", "date", "firm", "to_grade", "from_grade", "action",
    "pt_action", "pt_current", "pt_prior",
]
_RENAME = {
    "GradeDate": "date", "Firm": "firm", "ToGrade": "to_grade", "FromGrade": "from_grade",
    "Action": "action", "priceTargetAction": "pt_action",
    "currentPriceTarget": "pt_current", "priorPriceTarget": "pt_prior",
}


def load_universe() -> pd.DataFrame:
    """Return Symbol/Security/GICS Sector for every stock to scan."""
    uni = pd.read_csv(config.UNIVERSE_CSV)[["Symbol", "Security", "GICS Sector"]]
    if config.EXTRA_TICKERS.exists():
        extra = [
            line.strip().upper()
            for line in config.EXTRA_TICKERS.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        extra = [s for s in extra if s not in set(uni["Symbol"])]
        uni = pd.concat(
            [uni, pd.DataFrame({"Symbol": extra, "Security": extra, "GICS Sector": "Other"})],
            ignore_index=True,
        )
    return uni


def yahoo_symbol(symbol: str) -> str:
    return symbol.replace(".", "-")  # BRK.B -> BRK-B


def fetch_ticker(symbol: str, retries: int = 3) -> pd.DataFrame:
    import yfinance as yf

    for attempt in range(retries):
        try:
            df = yf.Ticker(yahoo_symbol(symbol)).upgrades_downgrades
            break
        except Exception as exc:  # yfinance raises on empty history and on throttling
            if "No upgrade/downgrade history" in str(exc):
                return pd.DataFrame(columns=RAW_COLUMNS)
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    if df is None or df.empty:
        return pd.DataFrame(columns=RAW_COLUMNS)
    return normalize_history(df, symbol)


def normalize_history(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Turn yfinance's upgrades_downgrades frame into RAW_COLUMNS, 2025+ only."""
    df = df.reset_index().rename(columns=_RENAME)
    df["ticker"] = symbol
    for col in RAW_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] >= pd.Timestamp(config.START_DATE)]
    return df[RAW_COLUMNS]


def fetch_prices(symbols: list[str]) -> pd.DataFrame:
    import yfinance as yf

    ysyms = [yahoo_symbol(s) for s in symbols]
    closes = yf.download(ysyms, period="5d", progress=False, auto_adjust=False, threads=True)["Close"]
    last = closes.ffill().iloc[-1]
    back = {yahoo_symbol(s): s for s in symbols}
    return pd.DataFrame({"ticker": [back.get(s, s) for s in last.index], "price": last.values}).dropna()


def fetch_all(
    progress: Callable[[int, int, str], None] | None = None,
    workers: int = 8,
) -> dict:
    """Fetch ratings for the whole universe and write data/ files. Returns metadata."""
    symbols = load_universe()["Symbol"].tolist()
    frames, failed = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_ticker, s): s for s in symbols}
        for done, fut in enumerate(as_completed(futures), 1):
            sym = futures[fut]
            try:
                frames.append(fut.result())
            except Exception:
                failed.append(sym)
            if progress:
                progress(done, len(symbols), sym)

    frames = [f for f in frames if not f.empty]
    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=RAW_COLUMNS)
    if len(failed) == len(symbols):
        raise RuntimeError(
            "Every Yahoo Finance request failed - check your internet connection. "
            "Existing data was left untouched."
        )
    config.DATA_DIR.mkdir(exist_ok=True)
    raw.sort_values(["date", "ticker"], ascending=[False, True]).to_csv(config.RAW_CSV, index=False)

    try:
        fetch_prices(symbols).to_csv(config.PRICES_CSV, index=False)
        prices_ok = True
    except Exception:
        prices_ok = False

    meta = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tickers_scanned": len(symbols),
        "tickers_failed": failed,
        "rating_actions": int(len(raw)),
        "prices": prices_ok,
    }
    config.META_JSON.write_text(json.dumps(meta, indent=2))
    return meta


def _cli_progress(done: int, total: int, sym: str) -> None:
    sys.stdout.write(f"\r[{done}/{total}] {sym:<8}")
    sys.stdout.flush()


if __name__ == "__main__":
    meta = fetch_all(progress=_cli_progress)
    print(
        f"\nSaved {meta['rating_actions']} rating actions from {meta['tickers_scanned']} stocks"
        f" ({len(meta['tickers_failed'])} failed) -> {config.RAW_CSV}"
    )
