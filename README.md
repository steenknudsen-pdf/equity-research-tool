# Bank Analyst Ratings

A local dashboard of **current analyst ratings on US stocks from the top 10 research
firms in the Extel 2025 All-America Research survey**, similar to the analyst-ratings
pages on GuruFocus or MarketBeat.

Pick an institution in the sidebar to see its ratings, grouped and newest first:

1. 🟢 **Buy / Overweight**, including Strong Buy, Outperform and similar
2. 🟡 **Neutral / Equal-weight**, including Hold, Market Perform, In-Line and similar
3. 🔴 **Sell / Underweight**, including Underperform, Reduce and similar
4. ✂️ **Cutting**, every downgrade or lowered price target

Each stock shows only that bank's **latest** rating, and only ratings issued on or after
**1 January 2025** count, so stale calls are excluded. The **All institutions** page
compares the banks side by side and ranks the stocks where the banks agree most.

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

## Tests

```bash
pytest
```
