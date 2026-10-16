import streamlit as st
import pandas as pd
import numpy as np
import requests
from pathlib import Path
from io import BytesIO
import re

st.set_page_config(page_title="My Stock Research Lab", page_icon="📈", layout="wide")

ROOT = Path(__file__).parent
SAMPLE_PATH = ROOT / "sample_stocks.csv"
UNIVERSE_PATH = ROOT / "my_stock_research_50_company_universe.csv"
FMP_BASE = "https://financialmodelingprep.com/stable"
FIRST_FIVE = [
    {"symbol": "BEL", "name": "Bharat Electronics", "sector": "Defence Electronics"},
    {"symbol": "CUMMINSIND", "name": "Cummins India", "sector": "Industrial Engines"},
    {"symbol": "POLYCAB", "name": "Polycab India", "sector": "Cables & Electrical Equipment"},
    {"symbol": "COFORGE", "name": "Coforge", "sector": "IT Services"},
    {"symbol": "APOLLOHOSP", "name": "Apollo Hospitals Enterprise", "sector": "Healthcare"},
]

st.title("📈 My Stock Research Lab")
st.caption("Personal prototype • Indian equities • Research workspace")

@st.cache_data
def load_csv(path_string):
    return pd.read_csv(path_string)

def load_sample():
    return load_csv(str(SAMPLE_PATH)) if SAMPLE_PATH.exists() else pd.DataFrame()

def load_universe():
    return load_csv(str(UNIVERSE_PATH)) if UNIVERSE_PATH.exists() else pd.DataFrame()

def get_fmp_key():
    try:
        return st.secrets.get("FMP_API_KEY", "")
    except Exception:
        return ""

def fmp_get(endpoint, symbol, api_key):
    url = f"{FMP_BASE}/{endpoint}"
    response = requests.get(
        url,
        params={"symbol": symbol, "period": "annual", "limit": 5, "apikey": api_key},
        timeout=20,
    )
    try:
        data = response.json()
    except Exception:
        data = None
    return response.status_code, data

def describe_response(status_code, data):
    if status_code == 401:
        return "Authentication failed — check the secret name and API key."
    if status_code == 402:
        return "Endpoint or data restricted on this plan."
    if status_code == 403:
        return "Access forbidden — check plan permissions."
    if status_code == 429:
        return "Rate limit reached; wait before retrying."
    if status_code >= 500:
        return f"Provider server error (HTTP {status_code})."
    if status_code != 200:
        return f"HTTP {status_code}."
    if isinstance(data, dict):
        msg = data.get("Error Message") or data.get("message") or data.get("error")
        if msg:
            return f"Provider response: {str(msg)[:180]}"
        return "Unexpected response format."
    if isinstance(data, list) and len(data) > 0:
        return f"Data returned ({len(data)} records)."
    if isinstance(data, list) and len(data) == 0:
        return "No records returned for this symbol/endpoint."
    return "No usable data returned."

def test_one_company(company, api_key):
    # Try the common NSE suffix first, then the bare symbol if no statement data is found.
    candidates = [f'{company["symbol"]}.NS', company["symbol"]]
    endpoints = [
        ("Profile", "profile"),
        ("Income statement", "income-statement"),
        ("Balance sheet", "balance-sheet-statement"),
        ("Cash flow", "cash-flow-statement"),
    ]
    best = None
    for candidate in candidates:
        rows = []
        useful_records = 0
        for label, endpoint in endpoints:
            try:
                status, data = fmp_get(endpoint, candidate, api_key)
                message = describe_response(status, data)
                count = len(data) if isinstance(data, list) else 0
                if status == 200 and isinstance(data, list) and count > 0:
                    useful_records += count
                rows.append({
                    "Company": company["name"],
                    "Requested symbol": candidate,
                    "Data type": label,
                    "HTTP status": status,
                    "Records": count,
                    "Result": message,
                })
            except requests.exceptions.Timeout:
                rows.append({"Company": company["name"], "Requested symbol": candidate, "Data type": label,
                             "HTTP status": "Timeout", "Records": 0, "Result": "Request timed out."})
            except requests.exceptions.RequestException as exc:
                rows.append({"Company": company["name"], "Requested symbol": candidate, "Data type": label,
                             "HTTP status": "Network error", "Records": 0, "Result": str(exc)[:180]})
        if best is None or useful_records > best[0]:
            best = (useful_records, candidate, rows)
        # If statements have data for this candidate, do not make extra calls for the bare symbol.
        statement_rows = [r for r in rows if r["Data type"] != "Profile"]
        if any(r["Records"] > 0 for r in statement_rows):
            break
    return best[2]

sample_df = load_sample()
universe_df = load_universe()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Demo Screener", "50-Company Universe", "Data Status", "Provider Test", "Financial Reports Importer"])

with tab1:
    st.warning("The demo screener uses fictional illustrative financial figures. Do not use these scores to make investment decisions.")
    if sample_df.empty:
        st.error("sample_stocks.csv was not found beside app.py.")
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
            valuation = 0
            if pd.notna(row["P/E"]) and pd.notna(row["Industry P/E"]) and row["Industry P/E"] > 0:
                valuation = np.clip((row["Industry P/E"] - row["P/E"]) / row["Industry P/E"] * 25 + 12.5, 0, 25)
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
                checks["P/E vs industry"] = pd.notna(row["P/E"]) and pd.notna(row["Industry P/E"]) and row["P/E"] < row["Industry P/E"]
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
        st.error("my_stock_research_50_company_universe.csv was not found. Upload it beside app.py.")
    else:
        st.info("Candidate list only. Current market capitalisation and financial statements have not been verified or loaded.")
        sectors = ["All sectors"] + sorted(universe_df["Sector"].dropna().unique().tolist()) if "Sector" in universe_df else ["All sectors"]
        selected_sector = st.selectbox("Filter by sector", sectors)
        shown = universe_df if selected_sector == "All sectors" or "Sector" not in universe_df else universe_df[universe_df["Sector"] == selected_sector]
        search = st.text_input("Search company or NSE symbol")
        if search:
            mask = shown.astype(str).apply(lambda col: col.str.contains(search, case=False, na=False)).any(axis=1)
            shown = shown[mask]
        st.metric("Companies in current view", len(shown))
        display_cols = [c for c in ["NSE Symbol", "Company Name", "Sector", "Universe Status", "Market Cap (₹ Cr)", "Financial Data Status", "Notes"] if c in shown.columns]
        st.dataframe(shown[display_cols], use_container_width=True, hide_index=True)
        st.download_button("Download current company universe as CSV", shown.to_csv(index=False).encode("utf-8"),
                           "company_universe.csv", "text/csv")

with tab3:
    st.subheader("Data status")
    status_rows = [
        {"Dataset": "Demo screener", "File": "sample_stocks.csv", "Status": "Synthetic illustrative figures only" if not sample_df.empty else "File missing"},
        {"Dataset": "50-company universe", "File": "my_stock_research_50_company_universe.csv", "Status": f"{len(universe_df)} company candidates loaded; financial data not yet collected" if not universe_df.empty else "File missing"},
        {"Dataset": "FMP provider test", "File": "Streamlit secret FMP_API_KEY", "Status": "Configured" if get_fmp_key() else "Not configured"},
    ]
    st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)
    st.caption("The API key is never displayed in this app. Test requests only run when you press the button in the Provider Test tab.")

with tab4:
    st.subheader("Financial Modeling Prep — provider test")
    st.write("This test checks whether the provider returns profile and annual financial-statement records for the first five candidate companies. It does not import data into the screener.")
    api_key = get_fmp_key()
    if not api_key:
        st.error('No FMP_API_KEY secret found. In Streamlit Community Cloud, open app settings → Secrets and add FMP_API_KEY = "your_key".')
    else:
        st.success("FMP_API_KEY secret found. The key is hidden.")
        st.warning("This test can make up to 40 API requests if NSE-suffixed symbols return no statement data. Use it once initially. FMP's free Basic plan has request limits and may restrict some endpoints.")
        if st.button("Test first five companies", type="primary"):
            results = []
            progress = st.progress(0)
            status_text = st.empty()
            for idx, company in enumerate(FIRST_FIVE):
                status_text.write(f'Testing {company["name"]} ({company["symbol"]})…')
                results.extend(test_one_company(company, api_key))
                progress.progress((idx + 1) / len(FIRST_FIVE))
            result_df = pd.DataFrame(results)
            st.session_state["fmp_test_results"] = result_df
            status_text.write("Test complete.")
        if "fmp_test_results" in st.session_state:
            result_df = st.session_state["fmp_test_results"]
            st.dataframe(result_df, use_container_width=True, hide_index=True)
            st.download_button("Download provider test results", result_df.to_csv(index=False).encode("utf-8"),
                               "fmp_provider_test_results.csv", "text/csv")
            usable = result_df[(result_df["HTTP status"] == 200) & (result_df["Records"] > 0)]
            st.metric("Endpoint checks returning records", len(usable))
            st.info("A successful response only confirms records were returned. We still need to verify reporting periods, currency, consolidated vs standalone basis, units and agreement with company filings before using any figures.")
            st.caption("If results show 401, check the secret. If 402/403, the endpoint may not be included in your plan. If zero records, the symbol format or coverage may differ.")


with tab5:
    st.subheader("Financial Reports Importer")
    st.write("Import company filings for review, or upload a structured CSV/XLSX to calculate basic financial metrics. This does not automatically certify figures or make investment recommendations.")
    st.warning("PDF extraction is a review aid, not reliable end-to-end financial-data extraction. Always check figures against the original filing, units, consolidated/standalone basis and fiscal year before using them.")

    template_columns = [
        "Company Name", "NSE Symbol", "FY", "Revenue (₹ Cr)", "Net Profit (₹ Cr)",
        "EBIT (₹ Cr)", "Total Debt (₹ Cr)", "Equity (₹ Cr)", "Capital Employed (₹ Cr)",
        "Market Cap (₹ Cr)", "P/E", "Industry P/E", "Source Filing", "Source Page/URL", "Basis"
    ]
    template_example = pd.DataFrame(columns=template_columns)
    st.download_button("Download financial data template (CSV)", template_example.to_csv(index=False).encode("utf-8"),
                       "financial_data_template.csv", "text/csv")

    upload = st.file_uploader("Upload annual report / quarterly result PDF, or structured CSV/XLSX", type=["pdf", "csv", "xlsx", "xls"], key="financial_report_upload")
    if upload is not None:
        suffix = Path(upload.name).suffix.lower()
        if suffix == ".pdf":
            try:
                import pdfplumber
                with pdfplumber.open(BytesIO(upload.getvalue())) as pdf:
                    st.caption(f"PDF loaded: {len(pdf.pages)} pages. Extracting text and candidate tables for manual verification.")
                    page_options = list(range(1, len(pdf.pages) + 1))
                    selected_pages = st.multiselect("Choose pages to inspect", page_options,
                                                    default=page_options[:min(3, len(page_options))])
                    extracted_text = []
                    extracted_tables = []
                    for page_num in selected_pages:
                        page = pdf.pages[page_num - 1]
                        extracted_text.append(f"--- Page {page_num} ---\n{page.extract_text() or '[No selectable text found on this page]'}")
                        for table_idx, table in enumerate(page.extract_tables() or [], start=1):
                            if table:
                                df_table = pd.DataFrame(table)
                                extracted_tables.append((page_num, table_idx, df_table))
                    if extracted_text:
                        with st.expander("Extracted page text (review against PDF)", expanded=False):
                            st.text_area("Text", "\n\n".join(extracted_text), height=280, key="pdf_extracted_text")
                            st.download_button("Download extracted text", "\n\n".join(extracted_text).encode("utf-8"),
                                               "extracted_filing_text.txt", "text/plain")
                    if extracted_tables:
                        table_labels = [f"Page {page_num}, table {table_idx}" for page_num, table_idx, _ in extracted_tables]
                        chosen = st.selectbox("Preview an extracted table", range(len(table_labels)),
                                              format_func=lambda i: table_labels[i])
                        table_df = extracted_tables[chosen][2]
                        st.dataframe(table_df, use_container_width=True, hide_index=True)
                        st.download_button("Download selected table as CSV", table_df.to_csv(index=False, header=False).encode("utf-8"),
                                           f"pdf_page_{extracted_tables[chosen][0]}_table_{extracted_tables[chosen][1]}.csv", "text/csv")
                    elif selected_pages:
                        st.info("No tables were detected on the selected pages. The PDF may be scanned or use a layout that table extraction cannot interpret. Try pages with selectable text, or enter verified values in the template.")
            except ImportError:
                st.error("PDF reader dependency is missing. Confirm requirements.txt includes pdfplumber, then reboot the Streamlit app.")
            except Exception as exc:
                st.error(f"Could not read this PDF: {str(exc)[:250]}")
        else:
            try:
                if suffix == ".csv":
                    raw_df = pd.read_csv(upload)
                else:
                    raw_df = pd.read_excel(upload)
                st.write("Uploaded data preview")
                st.dataframe(raw_df.head(100), use_container_width=True, hide_index=True)
                missing = [c for c in template_columns if c not in raw_df.columns]
                if missing:
                    st.error("This file does not use the full template column names. Download the template above, copy verified figures into it, and upload again. Missing columns: " + ", ".join(missing))
                else:
                    data_df = raw_df.copy()
                    numeric_cols = ["Revenue (₹ Cr)", "Net Profit (₹ Cr)", "EBIT (₹ Cr)", "Total Debt (₹ Cr)",
                                    "Equity (₹ Cr)", "Capital Employed (₹ Cr)", "Market Cap (₹ Cr)", "P/E", "Industry P/E"]
                    for col in numeric_cols:
                        data_df[col] = pd.to_numeric(data_df[col], errors="coerce")
                    data_df["FY sort"] = data_df["FY"].astype(str).str.extract(r"(\d{4})", expand=False)
                    data_df["FY sort"] = pd.to_numeric(data_df["FY sort"], errors="coerce")
                    metric_rows = []
                    for (symbol, company), grp in data_df.groupby(["NSE Symbol", "Company Name"], dropna=False):
                        grp = grp.sort_values("FY sort")
                        latest = grp.iloc[-1]
                        row = {"NSE Symbol": symbol, "Company Name": company, "Latest FY": latest["FY"],
                               "Revenue (₹ Cr)": latest["Revenue (₹ Cr)"], "Net Profit (₹ Cr)": latest["Net Profit (₹ Cr)"],
                               "Market Cap (₹ Cr)": latest["Market Cap (₹ Cr)"], "P/E": latest["P/E"], "Industry P/E": latest["Industry P/E"],
                               "Debt/Equity": latest["Total Debt (₹ Cr)"] / latest["Equity (₹ Cr)"] if pd.notna(latest["Total Debt (₹ Cr)"]) and pd.notna(latest["Equity (₹ Cr)"]) and latest["Equity (₹ Cr)"] != 0 else np.nan,
                               "ROCE (%)": latest["EBIT (₹ Cr)"] / latest["Capital Employed (₹ Cr)"] * 100 if pd.notna(latest["EBIT (₹ Cr)"]) and pd.notna(latest["Capital Employed (₹ Cr)"]) and latest["Capital Employed (₹ Cr)"] != 0 else np.nan,
                               "Annual rows supplied": len(grp), "Source Filing": latest["Source Filing"], "Source Page/URL": latest["Source Page/URL"], "Basis": latest["Basis"]}
                        for metric_col, output_col in [("Revenue (₹ Cr)", "Sales CAGR 3Y (%)"), ("Net Profit (₹ Cr)", "Profit CAGR 3Y (%)")]:
                            values = grp[metric_col].dropna()
                            # CAGR only when at least four annual observations exist and the earliest/latest values are positive.
                            if len(values) >= 4 and values.iloc[0] > 0 and values.iloc[-1] > 0:
                                row[output_col] = ((values.iloc[-1] / values.iloc[0]) ** (1 / (len(values) - 1)) - 1) * 100
                            else:
                                row[output_col] = np.nan
                        row["P/E below industry P/E"] = bool(pd.notna(row["P/E"]) and pd.notna(row["Industry P/E"]) and row["P/E"] < row["Industry P/E"])
                        metric_rows.append(row)
                    metrics_df = pd.DataFrame(metric_rows)
                    st.subheader("Calculated metrics (based only on uploaded figures)")
                    st.dataframe(metrics_df, use_container_width=True, hide_index=True)
                    st.download_button("Download calculated metrics", metrics_df.to_csv(index=False).encode("utf-8"),
                                       "calculated_financial_metrics.csv", "text/csv")
                    st.download_button("Download uploaded data copy", data_df.drop(columns=["FY sort"]).to_csv(index=False).encode("utf-8"),
                                       "uploaded_financial_data_copy.csv", "text/csv")
                    st.caption("CAGR is shown only when at least four positive annual values are available. The calculation uses the first and last available observations; check that fiscal years are consecutive. ROCE = EBIT ÷ capital employed. Debt/equity = total debt ÷ equity. Ensure all figures are in ₹ crore and use a consistent consolidated or standalone basis.")
            except Exception as exc:
                st.error(f"Could not read this file: {str(exc)[:250]}")

    st.markdown("**Recommended workflow for the first five companies**")
    st.markdown("1. Download annual reports/results from each company's official investor-relations website or exchange filing.\n2. Use PDF extraction to locate likely tables, but verify every value against the PDF.\n3. Enter verified annual figures into the CSV template, one row per company per financial year.\n4. Upload the completed CSV/XLSX to calculate preliminary metrics.\n5. Keep the filing name/link, page number, reporting period, and consolidated/standalone basis with every row.")
