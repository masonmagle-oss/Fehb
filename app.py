# FEHB + FEDVIP 2026 Cost Comparison Tool (v2.0)
# Mason Magle | Streamlit Web App
# ------------------------------------------------
# Run with: streamlit run app.py

import streamlit as st
import pandas as pd

st.set_page_config(page_title="FEHB + FEDVIP 2026", page_icon="💼", layout="wide")

st.markdown("<h1 style='text-align:center;'>💼 FEHB + FEDVIP 2026 Plan Finder</h1>", unsafe_allow_html=True)
st.caption("Filter by ZIP, compare costs, and include Dental/Vision add-ons.")

@st.cache_data
def load_fe():
    plans_base = pd.read_excel("FEHB_2026_General_Use_Calculator_PRO_v1.7_Failsafe.xlsx", sheet_name="Plans")
    key = pd.read_excel("2026-fehb-plan-key_100525.xlsx", sheet_name="2026 FEHB Plan Key")
    rates = pd.read_excel("2026-fehb-rates_100525.xlsx", sheet_name="2026 FEHB Rates")

    plans_base["Plan Option Display"] = (
        plans_base["Plan Option Name"].fillna('') + ' ' + plans_base["Plan Option Type"].fillna('')
    ).str.replace(r'\s+', ' ', regex=True).str.strip()

    rates["Enrollment Code"] = rates["Plan Code"].astype(str) + rates["Enrollment Code"].astype(str)
    rates_fam = rates[
        (rates["Rate Type"] == "NP Active") &
        (rates["Enrollment Type"] == "Self & Family") &
        (rates["Biweekly/Monthly"] == "Monthly")
    ][["Enrollment Code", "Employee Pays", "Government Pays"]].rename(
        columns={"Employee Pays": "Employee /mo", "Government Pays": "Govt /mo"}
    )
    rates_fam["Annual (employee)"] = rates_fam["Employee /mo"] * 12

    merged = plans_base.merge(
        key[["Enrollment Code","Carrier Name","Plan Option Name","Plan Option Type","Plan Code",
              "Network Type","Carrier URL","SBC URL","Provider Directory URL","Plan Formulary URL"]],
        left_on="Enrl_Code", right_on="Enrollment Code", how="left"
    ).merge(rates_fam, on="Enrollment Code", how="left")

    merged["Plan (Full Name)"] = (
        (merged["Carrier Name"].fillna('') + ' ' + merged["Plan Option Name_y"].fillna('')).str.strip()
    )
    merged.loc[merged["Plan (Full Name)"]=="","Plan (Full Name)"]=merged["Plan Option Display"]

    merged["Website"] = merged["Carrier URL"].apply(lambda x:
        f"[Visit site]({x})" if isinstance(x,str) and x.startswith("http") else "")
    merged["PlanCode2"] = merged["Enrl_Code"].str[:2]

    view = merged[["Plan (Full Name)","Plan Option Type_x","Network Type_x","Enrl_Code","PlanCode2",
                   "Employee /mo","Annual (employee)","Website",
                   "SBC URL","Provider Directory URL","Plan Formulary URL"]].rename(
        columns={"Plan Option Type_x":"Option Type","Network Type_x":"Network"}
    )
    return view

@st.cache_data
def load_zip():
    return pd.read_excel("2026-fehb-service-area_100525.xlsx", sheet_name="2026 FEHB Service Area")

@st.cache_data
def load_fedvip():
    dental = pd.read_excel("2026-fedvip-rates_100525.xlsx", sheet_name="Dental", header=2)
    vision = pd.read_excel("2026-fedvip-rates_100525.xlsx", sheet_name="Vision", header=2)
    d_month = dental[["Plan - Option","Self & Family."]].rename(columns={"Plan - Option":"Plan","Self & Family.":"Dental /mo"})
    v_month = vision[["Plan - Option","Self & Family."]].rename(columns={"Plan - Option":"Plan","Self & Family.":"Vision /mo"})
    return d_month, v_month

plans_view = load_fe()
zip_table = load_zip()
dental_rates, vision_rates = load_fedvip()

st.sidebar.header("Filters & Options")
zip_input = st.sidebar.text_input("ZIP Code:", "58104").strip()
include_dental = st.sidebar.checkbox("Include FEDVIP Dental", value=False)
include_vision = st.sidebar.checkbox("Include FEDVIP Vision", value=False)

if zip_input:
    zips = zip_table[zip_table["ZIP code"].astype(str) == zip_input]
    allowed = zips["Plan Code"].astype(str).unique()
    df = plans_view[plans_view["PlanCode2"].isin(allowed)]
    if df.empty:
        st.warning("No plans matched that ZIP code; showing all nationwide plans instead.")
        df = plans_view.copy()
else:
    df = plans_view.copy()

addon_total = 0
if include_dental:
    addon_total += dental_rates["Dental /mo"].mean(skipna=True)
if include_vision:
    addon_total += vision_rates["Vision /mo"].mean(skipna=True)

if addon_total > 0:
    df["Employee /mo"] = df["Employee /mo"].fillna(0) + addon_total
    df["Annual (employee)"] = df["Employee /mo"] * 12

df = df.sort_values(by="Annual (employee)", ascending=True)
best_name = df.iloc[0]["Plan (Full Name)"] if not df.empty else "N/A"
best_cost = df.iloc[0]["Annual (employee)"] if not df.empty else 0

st.markdown(f"### 💰 Best Value Plan: **{best_name}** — est. ${best_cost:,.0f}/yr")

search = st.text_input("Search plans (name, network, option):","").lower()
if search:
    df = df[df.apply(lambda r: search in ' '.join(map(str,r.values)).lower(), axis=1)]

cols_show = ["Plan (Full Name)","Network","Option Type","Enrl_Code","Employee /mo","Annual (employee)","Website"]
st.dataframe(df[cols_show].head(30), use_container_width=True)

with st.expander("📄 Benefit Links (SBC / Provider / Formulary)"):
    st.dataframe(df[["Plan (Full Name)","SBC URL","Provider Directory URL","Plan Formulary URL"]].head(30),
                 use_container_width=True)

st.markdown("---")
st.subheader("📊 Summary")
c1,c2,c3 = st.columns(3)
c1.metric("Plans Displayed", len(df))
c2.metric("Average Monthly Cost", f"${df['Employee /mo'].mean(skipna=True):,.0f}")
c3.metric("ZIP Entered", zip_input if zip_input else "—")
st.caption("© 2025 Mason Magle | FEHB + FEDVIP 2026 Plan Finder v2.0 | Data: OPM Public Use Files")
