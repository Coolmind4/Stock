# My Stock Research Lab v0.4 — Financial Reports Importer

## Files expected in the GitHub app folder
- `app.py`
- `requirements.txt`
- `sample_stocks.csv` (keep your existing file)
- `my_stock_research_50_company_universe.csv` (keep your existing file)

## What's new
- Adds a **Financial Reports Importer** tab without removing the existing Demo Screener, 50-Company Universe, Data Status, or Provider Test tabs.
- Upload annual-report/results PDFs to extract selectable text and candidate tables for review and download.
- Upload structured CSV/XLSX files based on `financial_data_template.csv` to calculate preliminary revenue CAGR, profit CAGR, debt/equity, ROCE and P/E vs industry P/E.
- Keeps source filing, page/URL, fiscal year, and consolidated/standalone basis fields alongside data.

## Important limitations
- PDF table extraction is a convenience for finding information, not a guaranteed or fully automated financial-statement parser. Scanned PDFs and complex layouts may not extract correctly.
- Always verify figures against the original filing, including units, currency, reporting period and consolidated vs standalone basis.
- CAGR requires at least four positive annual observations. Verify years are consecutive before relying on the result.
- This app does not provide investment advice or live market data. The Demo Screener still uses fictional illustrative figures.

## Deploy update
Replace only `app.py` and `requirements.txt` in your existing GitHub repository with the files in this update. Keep your existing CSV files and Streamlit Secrets. Do not put API keys in GitHub.
