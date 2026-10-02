"""Turn raw rating actions into the per-institution views shown in the app."""
from __future__ import annotations

import json

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
