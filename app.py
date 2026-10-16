import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

st.set_page_config(page_title="My Stock Research Lab", page_icon="📈", layout="wide")

ROOT = Path(__file__).parent
SAMPLE_PATH = ROOT / "sample_stocks.csv"
UNIVERSE_PATH = ROOT / "my_stock_research_50_company_universe.csv"

st.title("📈 My Stock Research Lab")
st.caption("Personal prototype • Indian equities • Research workspace")

@st.cache_data
def load_csv(path_string):
    return pd.read_csv(path_string)

def load_sample():
    if SAMPLE_PATH.exists():
        return load_csv(str(SAMPLE_PATH))
    return pd.DataFrame()

def load_universe():
    if UNIVERSE_PATH.exists():
        return load_csv(str(UNIVERSE_PATH))
    return pd.DataFrame()

sample_df = load_sample()
universe_df = load_universe()

tab1, tab2, tab3 = st.tabs(["Demo Screener", "50-Company Universe", "Data Status"])

with tab1:
    st.warning(
        "The demo screener uses fictional illustrative financial figures. "
        "Do not use these sample scores or companies to make investment decisions."
    )
    if sample_df.empty:
        st.error("sample_stocks.csv was not found. Upload it to the same GitHub folder as app.py.")
    else:
        with st.sidebar:
            st.header("Demo screening rules")
            min_mcap = st.number_input("Minimum market cap (₹ crore)", min_value=0, max_value=1000000, value=200, step=100)
            max_mcap = st.number_input("Maximum market cap (₹ crore)", min_value=1, max_value=1000000, value=5000, step=500)
            min_sales_growth = st.slider("Minimum 3-year sales CAGR (%)", min_value=-20, max_value=80, value=15)
            min_profit_growth = st.slider("Minimum 3-year profit CAGR (%)", min_value=-50, max_value=100, value=15)
            max_de = st.slider("Maximum debt/equity", min_value=0.0, max_value=3.0, value=0.5, step=0.1)
            min_roce = st.slider("Minimum ROCE (%)", min_value=-10, max_value=60, value=20)
            require_below_industry_pe = st.checkbox("Require P/E below industry P/E", value=True)

        def score_row(row):
            sales = np.clip((row["Sales CAGR 3Y (%)"] / 30) * 20, 0, 20)
            profit = np.clip((row["Profit CAGR 3Y (%)"] / 30) * 20, 0, 20)
            roce = np.clip((row["ROCE (%)"] / 30) * 20, 0, 20)
            debt = np.clip((1 - row["Debt/Equity"] / 1.5) * 15, 0, 15)
            if pd.notna(row["P/E"]) and pd.notna(row["Industry P/E"]) and row["Industry P/E"] > 0:
                valuation = np.clip((row["Industry P/E"] - row["P/E"]) / row["Industry P/E"] * 25 + 12.5, 0, 25)
            else:
                valuation = 0
            return round(float(sales + profit + roce + debt + valuation), 1)

        def screen_row(row):
            checks = {
                "Market cap": min_mcap <= row["Market Cap (₹ Cr)"] <= max_mcap,
                "Sales CAGR": row["Sales CAGR 3Y (%)"] >= min_sales_growth,
                "Profit CAGR": row["Profit CAGR 3Y (%)"] >= min_profit_growth,
                "Debt/equity": row["Debt/Equity"] <= max_de,
                "ROCE": row["ROCE (%)"] >= min_roce,
            }
            if require_below_industry_pe:
                checks["P/E vs industry"] = (
                    pd.notna(row["P/E"]) and pd.notna(row["Industry P/E"]) and row["P/E"] < row["Industry P/E"]
                )
            failures = [name for name, passed in checks.items() if not passed]
            return pd.Series({"Passes Screen": len(failures) == 0, "Failed Checks": ", ".join(failures) if failures else "—"})

        work = sample_df.copy()
        work["Score / 100"] = work.apply(score_row, axis=1)
        work = pd.concat([work, work.apply(screen_row, axis=1)], axis=1)
        passed = work[work["Passes Screen"]].sort_values("Score / 100", ascending=False)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Demo companies", len(work))
        c2.metric("Passing demo filters", len(passed))
        c3.metric("Highest demo score", f'{work["Score / 100"].max():.1f}/100')
        c4.metric("Live financial data", "Not connected")
        show_all = st.toggle("Show all demo companies, including failures", value=False)
        view = work if show_all else passed
        cols = ["Ticker", "Company", "Sector", "Market Cap (₹ Cr)", "Sales CAGR 3Y (%)",
                "Profit CAGR 3Y (%)", "ROCE (%)", "Debt/Equity", "P/E", "Industry P/E",
                "Score / 100", "Passes Screen", "Failed Checks"]
        st.dataframe(view[cols].sort_values("Score / 100", ascending=False), use_container_width=True, hide_index=True)
        st.download_button("Download demo results as CSV", view[cols].to_csv(index=False).encode("utf-8"),
                           "demo_screen_results.csv", "text/csv")
        ticker = st.selectbox("Choose a demo company", work["Ticker"].tolist())
        row = work[work["Ticker"] == ticker].iloc[0]
        st.subheader(f'{row["Company"]} ({row["Ticker"]})')
        st.write(f'**Demo score:** {row["Score / 100"]}/100')
        st.write(f'**Screen status:** {"Passes current filters" if row["Passes Screen"] else "Does not pass all filters"}')
        st.write(f'**Failed checks:** {row["Failed Checks"]}')
        st.caption("Scores use illustrative synthetic data only. They are not predictions or recommendations.")

with tab2:
    st.subheader("Candidate universe: 50 Indian companies")
    if universe_df.empty:
        st.error("my_stock_research_50_company_universe.csv was not found beside app.py.")
        st.write("Upload the CSV to the same GitHub repository folder as app.py, then reboot the app.")
    else:
        st.info(
            "This is a candidate list for research, not a buy list. Company identity and sector are listed; "
            "financial statements, current market capitalisation and screening metrics have not yet been verified or loaded."
        )
        if "Sector" in universe_df.columns:
            sectors = ["All sectors"] + sorted(universe_df["Sector"].dropna().unique().tolist())
            selected_sector = st.selectbox("Filter by sector", sectors)
            shown = universe_df if selected_sector == "All sectors" else universe_df[universe_df["Sector"] == selected_sector]
        else:
            shown = universe_df
        search = st.text_input("Search company or NSE symbol")
        if search:
            mask = shown.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
            shown = shown[mask]
        st.metric("Companies in current view", len(shown))
        display_cols = [c for c in ["NSE Symbol", "Company Name", "Sector", "Universe Status",
                                     "Market Cap (₹ Cr)", "Financial Data Status", "Notes"] if c in shown.columns]
        st.dataframe(shown[display_cols], use_container_width=True, hide_index=True)
        st.download_button("Download current company universe as CSV", shown.to_csv(index=False).encode("utf-8"),
                           "company_universe.csv", "text/csv")

with tab3:
    st.subheader("Data status")
    status_rows = [
        {"Dataset": "Demo screener", "File": "sample_stocks.csv", "Status": "Synthetic illustrative figures only" if not sample_df.empty else "File missing"},
        {"Dataset": "50-company universe", "File": "my_stock_research_50_company_universe.csv", "Status": f"{len(universe_df)} company candidates loaded; financial data not yet collected" if not universe_df.empty else "File missing"},
    ]
    st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)
    st.markdown(
        """
        ### Next data milestone
        1. Verify each company's listing and identifier.
        2. Collect reported financial statements from permitted sources.
        3. Record source URL, reporting period, publication date and whether figures are consolidated.
        4. Calculate ratios with tests and compare them with reported figures.
        5. Only then show real scores. Missing data must remain visibly missing.
        """
    )
