import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

st.set_page_config(page_title="My AI Stock Research Lab", page_icon="📈", layout="wide")

DATA_PATH = Path(__file__).parent / "sample_stocks.csv"

st.title("📈 My Stock Research Lab")
st.caption("Personal prototype • Indian equities • Sample data only — not investment advice")

st.info(
    "This first version uses illustrative sample companies and synthetic financial figures. "
    "It does not connect to live market data and must not be used to make real investment decisions."
)

@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    return df

df = load_data()

with st.sidebar:
    st.header("Screening rules")
    min_mcap = st.number_input("Minimum market cap (₹ crore)", min_value=0, max_value=1000000, value=200, step=100)
    max_mcap = st.number_input("Maximum market cap (₹ crore)", min_value=1, max_value=1000000, value=5000, step=500)
    min_sales_growth = st.slider("Minimum 3-year sales CAGR (%)", min_value=-20, max_value=80, value=15)
    min_profit_growth = st.slider("Minimum 3-year profit CAGR (%)", min_value=-50, max_value=100, value=15)
    max_de = st.slider("Maximum debt/equity", min_value=0.0, max_value=3.0, value=0.5, step=0.1)
    min_roce = st.slider("Minimum ROCE (%)", min_value=-10, max_value=60, value=20)
    require_below_industry_pe = st.checkbox("Require P/E below industry P/E", value=True)
    st.divider()
    st.caption("Edit filters to see how the shortlist changes.")

# Make pass/fail reasons transparent
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
    reasons = [name for name, passed in checks.items() if not passed]
    return pd.Series({"Passes Screen": len(reasons) == 0, "Failed Checks": ", ".join(reasons) if reasons else "—"})

# A simple, explainable heuristic score. Not a prediction.
def calculate_score(row):
    sales = np.clip((row["Sales CAGR 3Y (%)"] / 30) * 20, 0, 20)
    profit = np.clip((row["Profit CAGR 3Y (%)"] / 30) * 20, 0, 20)
    roce = np.clip((row["ROCE (%)"] / 30) * 20, 0, 20)
    debt = np.clip((1 - row["Debt/Equity"] / 1.5) * 15, 0, 15)
    if pd.notna(row["P/E"]) and pd.notna(row["Industry P/E"]) and row["Industry P/E"] > 0:
        valuation = np.clip((row["Industry P/E"] - row["P/E"]) / row["Industry P/E"] * 25 + 12.5, 0, 25)
    else:
        valuation = 0
    return round(float(sales + profit + roce + debt + valuation), 1)

df["Score / 100"] = df.apply(calculate_score, axis=1)
checks = df.apply(screen_row, axis=1)
df = pd.concat([df, checks], axis=1)

passed = df[df["Passes Screen"]].sort_values("Score / 100", ascending=False)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Sample companies", len(df))
c2.metric("Passing current filters", len(passed))
c3.metric("Highest illustrative score", f'{df["Score / 100"].max():.1f}/100')
c4.metric("Live data connected", "No")

st.subheader("Screening results")
show_all = st.toggle("Show all companies, including failures", value=False)
view = df if show_all else passed
cols = [
    "Ticker", "Company", "Sector", "Market Cap (₹ Cr)", "Sales CAGR 3Y (%)",
    "Profit CAGR 3Y (%)", "ROCE (%)", "Debt/Equity", "P/E", "Industry P/E",
    "Score / 100", "Passes Screen", "Failed Checks"
]
st.dataframe(view[cols].sort_values("Score / 100", ascending=False), use_container_width=True, hide_index=True)

csv = view[cols].to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download current table as CSV", data=csv, file_name="stock_screen_results.csv", mime="text/csv")

st.subheader("Company deep dive")
selected_ticker = st.selectbox("Choose a sample company", df["Ticker"].tolist())
company = df[df["Ticker"] == selected_ticker].iloc[0]

left, right = st.columns(2)
with left:
    st.markdown(f"### {company['Company']} ({company['Ticker']})")
    st.write(f"**Sector:** {company['Sector']}")
    st.write(f"**Illustrative score:** {company['Score / 100']}/100")
    st.write(f"**Screen status:** {'Passes current filters' if company['Passes Screen'] else 'Does not pass all filters'}")
    st.write(f"**Checks to review:** {company['Failed Checks']}")
with right:
    st.markdown("### Key metrics")
    st.write(f"Market cap: ₹{company['Market Cap (₹ Cr)']:,.0f} crore")
    st.write(f"Sales CAGR (3Y): {company['Sales CAGR 3Y (%)']}%")
    st.write(f"Profit CAGR (3Y): {company['Profit CAGR 3Y (%)']}%")
    st.write(f"ROCE: {company['ROCE (%)']}%")
    st.write(f"Debt/equity: {company['Debt/Equity']}")
    st.write(f"P/E vs industry P/E: {company['P/E']} vs {company['Industry P/E']}")

st.subheader("How the score is calculated")
st.markdown(
    """
    This prototype uses a transparent heuristic:
    - Sales CAGR: up to 20 points
    - Profit CAGR: up to 20 points
    - ROCE: up to 20 points
    - Debt/equity: up to 15 points
    - P/E relative to industry P/E: up to 25 points

    **Important:** This is a demonstration score, not a validated investment model. It does not account for
    governance, cash-flow conversion, dilution, cyclicality, promoter pledging, one-off profits, or data quality.
    A high score is not a prediction of multibagger returns.
    """
)

st.caption("Next milestone: replace synthetic sample data with verified financial statements and document each metric's calculation.")
