"""Static configuration: tracked institutions, rating buckets, date window."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("RATINGS_DATA_DIR", ROOT / "data"))
UNIVERSE_CSV = ROOT / "data" / "sp500.csv"
EXTRA_TICKERS = ROOT / "data" / "extra_tickers.txt"
RAW_CSV = DATA_DIR / "ratings_raw.csv"
PRICES_CSV = DATA_DIR / "prices.csv"
META_JSON = DATA_DIR / "meta.json"
PORTFOLIO_TXT = DATA_DIR / "portfolio.txt"

# Only ratings issued on/after this date count as "current".
START_DATE = "2025-01-01"


@dataclass(frozen=True)
class Institution:
    key: str
    name: str
    short: str
    extel_rank: int
    # Prefixes matched against the firm name with all non-alphanumerics
    # removed and lower-cased (e.g. "J.P. Morgan" -> "jpmorgan").
    prefixes: tuple[str, ...]

    def matches(self, firm: str) -> bool:
        squashed = squash(firm)
        return any(squashed.startswith(p) for p in self.prefixes)


# Extel (formerly Institutional Investor) 2025 All-America Research Team
# leaders table, top 10 by published positions. BofA and Morgan Stanley tied
# for 2nd. Order here is the order shown in the dashboard.
INSTITUTIONS: tuple[Institution, ...] = (
    Institution("jpm", "J.P. Morgan", "JPM", 1, ("jpmorgan", "jpm")),
    Institution("ms", "Morgan Stanley", "MS", 2, ("morganstanley",)),
    Institution("bofa", "BofA Securities", "BofA", 2, ("bofa", "bankofamerica", "merrilllynch")),
    Institution("evercore", "Evercore ISI", "EVR", 4, ("evercore",)),
    Institution("jefferies", "Jefferies", "JEF", 5, ("jefferies",)),
    Institution("ubs", "UBS", "UBS", 6, ("ubs",)),
    Institution("wolfe", "Wolfe Research", "Wolfe", 7, ("wolfe",)),
    Institution("wells", "Wells Fargo Securities", "WFS", 8, ("wellsfargo",)),
    Institution("barclays", "Barclays", "BARC", 9, ("barclays",)),
    Institution("bernstein", "Bernstein", "BERN", 10, ("bernstein", "sanfordcbernstein", "societegeneralebernstein")),
)
INSTITUTIONS_BY_KEY = {i.key: i for i in INSTITUTIONS}


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def institution_for(firm: str) -> Institution | None:
    for inst in INSTITUTIONS:
        if inst.matches(firm):
            return inst
    return None


BUY, HOLD, SELL, OTHER = "Buy / Overweight", "Neutral / Equal-weight", "Sell / Underweight", "Other"
BUCKET_ORDER = (BUY, HOLD, SELL, OTHER)

# Banks use their own scales; map each wording (squashed) onto three buckets.
_GRADE_BUCKETS = {
    BUY: (
        "strongbuy", "buy", "convictionbuy", "overweight", "outperform", "marketoutperform",
        "sectoroutperform", "outperformer", "positive", "accumulate", "add", "toppick",
        "longtermbuy", "speculativebuy", "moderatebuy", "overweighttoppick",
    ),
    HOLD: (
        "hold", "neutral", "equalweight", "marketperform", "sectorperform", "peerperform",
        "inline", "sectorweight", "marketweight", "perform", "mixed", "fairvalue",
    ),
    SELL: (
        "sell", "strongsell", "underweight", "underperform", "marketunderperform",
        "sectorunderperform", "underperformer", "reduce", "negative", "moderatesell",
    ),
}
_GRADE_LOOKUP = {g: bucket for bucket, grades in _GRADE_BUCKETS.items() for g in grades}


def bucket_for(grade: str) -> str:
    return _GRADE_LOOKUP.get(squash(grade), OTHER)


ACTION_LABELS = {
    "up": "Upgrade",
    "down": "Downgrade",
    "init": "Initiated",
    "main": "Maintained",
    "reit": "Reiterated",
}
