"""Turn raw rating actions into the per-institution views shown in the app."""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from . import config


def load_raw() -> pd.DataFrame | None:
    if not config.RAW_CSV.exists():
        return None
    return pd.read_csv(config.RAW_CSV, parse_dates=["date"])


def load_meta() -> dict:
    if not config.META_JSON.exists():
        return {}
    return json.loads(config.META_JSON.read_text())


def load_prices() -> pd.DataFrame | None:
    if not config.PRICES_CSV.exists():
        return None
    return pd.read_csv(config.PRICES_CSV)


def enrich(raw: pd.DataFrame, universe: pd.DataFrame, prices: pd.DataFrame | None = None) -> pd.DataFrame:
    """Tag each action with its institution, bucket, company info and upside."""
    df = raw[raw["date"] >= pd.Timestamp(config.START_DATE)].copy()
    inst = df["firm"].map(config.institution_for)
    df["institution"] = inst.map(lambda i: i.key if i else None)
    df = df[df["institution"].notna()]
    df["bucket"] = df["to_grade"].fillna("").map(config.bucket_for)
    df["action_label"] = df["action"].map(config.ACTION_LABELS).fillna(df["action"])
    df["from_grade"] = df["from_grade"].replace("", pd.NA)

    info = universe.rename(columns={"Symbol": "ticker", "Security": "company", "GICS Sector": "sector"})
    df = df.merge(info, on="ticker", how="left")
    df["company"] = df["company"].fillna(df["ticker"])
    if prices is not None and not prices.empty:
        df = df.merge(prices, on="ticker", how="left")
    else:
        df["price"] = np.nan
    pt = pd.to_numeric(df["pt_current"], errors="coerce").replace(0, np.nan)
    df["pt_current"] = pt
    df["pt_prior"] = pd.to_numeric(df["pt_prior"], errors="coerce").replace(0, np.nan)
    df["upside"] = pt / df["price"] - 1
    df["pt_cut"] = (df["pt_prior"].notna() & (df["pt_current"] < df["pt_prior"])) | (
        df["pt_action"].astype(str).str.lower() == "lowers"
    )
    return df.sort_values("date", ascending=False, kind="stable")


def current_ratings(df: pd.DataFrame) -> pd.DataFrame:
    """Latest 2025+ rating per (institution, stock), newest first."""
    return df.drop_duplicates(["institution", "ticker"], keep="first")


def cuts(df: pd.DataFrame) -> pd.DataFrame:
    """Every 2025+ downgrade or price-target cut, newest first."""
    return df[(df["action"] == "down") | df["pt_cut"]]


def consensus(current: pd.DataFrame) -> pd.DataFrame:
    """Per stock: how many top-10 banks rate it Buy / Neutral / Sell."""
    counts = (
        current.pivot_table(index="ticker", columns="bucket", values="institution", aggfunc="count", fill_value=0)
        .reindex(columns=list(config.BUCKET_ORDER), fill_value=0)
    )
    names = {i.key: i.name for i in config.INSTITUTIONS}
    by_bucket = (
        current.assign(name=current["institution"].map(names))
        .groupby(["ticker", "bucket"])["name"].agg(lambda s: ", ".join(sorted(s)))
        .unstack()
    )
    out = counts.join(by_bucket, rsuffix=" banks")
    meta = current.drop_duplicates("ticker").set_index("ticker")[["company", "sector", "price"]]
    out = meta.join(out, how="inner")
    out["Banks covering"] = counts.sum(axis=1)
    out["Net bullish"] = out[config.BUY] - out[config.SELL]
    return out.sort_values(["Net bullish", "Banks covering"], ascending=False).reset_index()


_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def parse_tickers(text: str) -> list[str]:
    """Split pasted text ("AAPL, msft\nNVDA") into unique, valid tickers."""
    out = []
    for tok in re.split(r"[\s,;]+", text.upper()):
        tok = tok.strip().lstrip("$")
        if tok and _TICKER_RE.match(tok) and tok not in out:
            out.append(tok)
    return out


def tickers_from_csv(frame: pd.DataFrame) -> list[str]:
    """Pick the ticker column out of an uploaded portfolio/brokerage export."""
    for col in frame.columns:
        if str(col).strip().lower() in {"ticker", "symbol", "tickers", "symbols"}:
            return parse_tickers(" ".join(frame[col].dropna().astype(str)))
    return parse_tickers(" ".join(frame.iloc[:, 0].dropna().astype(str)))


def consensus_label(buy: int, hold: int, sell: int) -> str:
    total = buy + hold + sell
    if total == 0:
        return "Not covered"
    score = (buy - sell) / total
    if score >= 0.5:
        return "Bullish"
    if score <= -0.25:
        return "Bearish"
    return "Mixed"


def portfolio_view(current: pd.DataFrame, cut_actions: pd.DataFrame, tickers: list[str],
                   universe: pd.DataFrame | None = None, prices: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per holding: every top-10 bank's current rating plus a consensus summary."""
    rows = []
    recent = pd.Timestamp.today().normalize() - pd.Timedelta(days=90)
    names = universe.set_index("Symbol")["Security"].to_dict() if universe is not None else {}
    px = prices.set_index("ticker")["price"].to_dict() if prices is not None and not prices.empty else {}
    for t in tickers:
        mine = current[current["ticker"] == t]
        counts = mine["bucket"].value_counts()
        buy, hold, sell = (int(counts.get(b, 0)) for b in (config.BUY, config.HOLD, config.SELL))
        pts = mine["pt_current"].dropna()
        price = mine["price"].dropna().iloc[0] if mine["price"].notna().any() else px.get(t, np.nan)
        row = {
            "ticker": t,
            "company": mine["company"].iloc[0] if not mine.empty else names.get(t, t),
            "sector": mine["sector"].iloc[0] if not mine.empty else None,
            "price": price,
            "buy": buy, "hold": hold, "sell": sell, "covering": buy + hold + sell,
            "consensus": consensus_label(buy, hold, sell),
            "avg_pt": pts.mean() if not pts.empty else np.nan,
            "latest": mine["date"].max() if not mine.empty else pd.NaT,
            "cuts_90d": int(((cut_actions["ticker"] == t) & (cut_actions["date"] >= recent)).sum()),
        }
        row["upside"] = row["avg_pt"] / price - 1 if price and not np.isnan(price) else np.nan
        by_bank = mine.set_index("institution")
        for inst in config.INSTITUTIONS:
            if inst.key in by_bank.index:
                r = by_bank.loc[inst.key]
                row[f"{inst.key}_grade"] = r["to_grade"]
                row[f"{inst.key}_bucket"] = r["bucket"]
                row[f"{inst.key}_date"] = r["date"]
                row[f"{inst.key}_pt"] = r["pt_current"]
            else:
                row[f"{inst.key}_grade"] = None
                row[f"{inst.key}_bucket"] = None
                row[f"{inst.key}_date"] = pd.NaT
                row[f"{inst.key}_pt"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def portfolio_export(view: pd.DataFrame) -> pd.DataFrame:
    """Flat, spreadsheet-friendly version of portfolio_view for CSV download."""
    out = view[["ticker", "company", "sector", "price", "consensus", "buy", "hold", "sell",
                "covering", "avg_pt", "upside", "cuts_90d"]].rename(columns={
        "ticker": "Ticker", "company": "Company", "sector": "Sector", "price": "Price",
        "consensus": "Consensus", "buy": "Buy ratings", "hold": "Neutral ratings",
        "sell": "Sell ratings", "covering": "Banks covering", "avg_pt": "Avg price target",
        "upside": "Upside to avg target", "cuts_90d": "Cuts last 90 days",
    })
    for inst in config.INSTITUTIONS:
        out[inst.name] = view[f"{inst.key}_grade"]
    return out
