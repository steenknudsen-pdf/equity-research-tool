# Bank Analyst Ratings

A local dashboard of **current analyst ratings on US stocks from the top 10 research
firms in the Extel 2025 All-America Research survey**, similar to the analyst-ratings
pages on GuruFocus or MarketBeat.

The dashboard has three pages, all in a clean light theme:

* **Bank ratings:** pick a bank (J.P. Morgan by default) to see its current ratings
  in tabs: 🟢 **Buy / Overweight**, 🟡 **Neutral / Equal-weight**, 🔴 **Sell / Underweight**
  and ✂️ **Cutting** (every downgrade or lowered price target). Newest first.
* **Portfolio screener:** paste your tickers or upload your brokerage's CSV export.
  You'll see every top-10 bank's current rating on each holding side by side, a
  Bullish / Mixed / Bearish consensus, the average price target and upside, and any
  recent cuts. Pick a holding to see its full 2025–2026 rating history. Tickers outside
  the S&P 500 can be fetched with one click and are kept for future refreshes.
* **Overview:** the Buy/Neutral/Sell mix of each bank, the stocks the banks agree on
  most, and the latest rating actions across all banks.

Every list has a **Table view & CSV download** section underneath for spreadsheet
work. Each stock shows only a bank's **latest** rating, and only ratings issued on or
after **1 January 2025** count.

## Institutions (Extel 2025 All-America Research Team, top 10)

| Rank | Firm | | Rank | Firm |
|---|---|---|---|---|
| 1 | J.P. Morgan | | 6 | UBS |
| 2= | Morgan Stanley | | 7 | Wolfe Research |
| 2= | BofA Securities | | 8 | Wells Fargo Securities |
| 4 | Evercore ISI | | 9 | Barclays |
| 5 | Jefferies | | 10 | Bernstein |

To add or remove a firm, edit `INSTITUTIONS` in `ratings/config.py`.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Then click **🔄 Refresh data from Yahoo Finance** in the sidebar. The first refresh
scans about 500 stocks and takes a few minutes. You can also refresh from the terminal
with `python -m ratings.fetch`.

## Where the data comes from

The banks don't publish a free ratings feed. This tool reads the free, public
upgrade/downgrade history that **Yahoo Finance** shows for each stock, using the
`yfinance` library. You don't need an API key. Each rating action includes the firm,
the new and prior rating, the action type, and price targets.

* **Universe:** S&P 500 constituents (`data/sp500.csv`). To cover more stocks (for
  example ADRs or smaller caps), add tickers to `data/extra_tickers.txt`.
* **Limits:** Yahoo Finance isn't an official vendor feed. Coverage can lag, some
  actions may be missing, and `yfinance` can break when Yahoo changes its site. Check
  important calls against the bank's own research. This is not investment advice.

## Customizing

* **Banks:** edit `INSTITUTIONS` in `ratings/config.py`.
* **Colors and theme:** `.streamlit/config.toml` (the app always opens in light mode)
  and the CSS at the top of `ratings/ui.py`.
* **Your portfolio** is saved locally in `data/portfolio.txt`, and it never leaves your computer.

## Tests

```bash
pytest
```
