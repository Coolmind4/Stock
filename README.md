# My Stock Research Lab v0.3

## Expected files in the same GitHub folder
- app.py
- requirements.txt
- sample_stocks.csv
- my_stock_research_50_company_universe.csv

## Streamlit secret
In Streamlit Community Cloud → app Settings → Secrets:
FMP_API_KEY = "your_actual_api_key"

Never commit your API key to GitHub or paste it into chat.

## What changed
Added a Provider Test tab that checks profile, income statement, balance sheet and cash-flow statement endpoints for the first five company candidates. This only tests API availability; it does not import figures into the screener.

## Important
- Demo Screener still uses synthetic figures.
- The 50-company list is a candidate universe, not a buy recommendation.
- Validate data, fiscal periods, units, currency and consolidated/standalone basis against company filings before using it.
