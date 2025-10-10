# FEHB + FEDVIP 2026 Custom Estimator (v2.1b)
# Mason Magle | Streamlit Web App (bugfixed)
# ------------------------------------------------
# Run with: streamlit run app.py

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="FEHB + FEDVIP 2026 – Custom Estimator", page_icon="💼", layout="wide")

st.markdown("<h1 style='text-align:center;'>💼 FEHB + FEDVIP 2026 – Custom Estimator (v2.1b)</h1>", unsafe_allow_html=True)
st.caption("ZIP filter + full utilization inputs. Estimates annual total cost: premiums + expected OOP − tax-shelter savings.")

def _to_float(x, default=0.0):
    if pd.isna(x):
        return float(default)
    if isinstance(x, (int, float, np.number)):
        return float(x)
    s = str(x).replace('$','').replace(',','').strip()
    try:
        if s.lower().startswith('no'):
            return 0.0
        if 'not covered' in s.lower():
            return float(9999)
        if s.endswith('%'):
            return float(s[:-1]) / 100.0
        return float(s)
    except:
        return float(default)

def pct_or_copay(value, fallback_copay):
    if pd.isna(value):
        return (False, _to_float(fallback_copay))
    s = str(value).strip()
    if s.endswith('%'):
        return (True, _to_float(s))
    return (False, _to_float(s, fallback_copay))

@st.cache_data
def load_core():
    plans_base = pd.read_excel("FEHB_2026_General_Use_Calculator_PRO_v1.7_Failsafe.xlsx", sheet_name="Plans")
    key = pd.read_excel("2026-fehb-plan-key_100525.xlsx", sheet_name="2026 FEHB Plan Key")
    rates = pd.read_excel("2026-fehb-rates_100525.xlsx", sheet_name="2026 FEHB Rates")
    svc = pd.read_excel("2026-fehb-service-area_100525.xlsx", sheet_name="2026 FEHB Service Area")

    plans_base["Plan Option Display"] = (
        plans_base["Plan Option Name"].fillna('') + ' ' + plans_base["Plan Option Type"].fillna('')
    ).str.replace(r'\s+', ' ', regex=True).str.strip()

    rates["Enrollment Code"] = rates["Plan Code"].astype(str) + rates["Enrollment Code"].astype(str)
    sel = (rates["Rate Type"].eq("NP Active") &
           rates["Enrollment Type"].eq("Self & Family") &
           rates["Biweekly/Monthly"].eq("Monthly"))
    rates_fam = rates.loc[sel, ["Enrollment Code","Employee Pays","Government Pays"]].rename(
        columns={"Employee Pays":"Employee /mo","Government Pays":"Govt /mo"}
    )
    rates_fam["Annual (employee)"] = rates_fam["Employee /mo"] * 12

    merged = plans_base.merge(
        key[["Enrollment Code","Carrier Name","Plan Option Name","Plan Option Type","Plan Code",
              "Network Type","Carrier URL","SBC URL","Provider Directory URL","Plan Formulary URL"]],
        left_on="Enrl_Code", right_on="Enrollment Code", how="left"
    ).merge(rates_fam, on="Enrollment Code", how="left")

    merged["Plan (Full Name)"] = (merged["Carrier Name"].fillna('') + ' ' + merged["Plan Option Name_y"].fillna('')).str.strip()
    merged.loc[merged["Plan (Full Name)"].eq(""), "Plan (Full Name)"] = merged["Plan Option Display"]
    merged["PlanCode2"] = merged["Enrl_Code"].str[:2]
    merged["Website"] = merged["Carrier URL"].apply(lambda x: f"[Visit site]({x})" if isinstance(x,str) and x.startswith("http") else "")

    plans_view = merged[["Plan (Full Name)","Plan Option Type_x","Network Type_x","Enrl_Code","PlanCode2",
                         "Employee /mo","Annual (employee)","Website","SBC URL","Provider Directory URL","Plan Formulary URL"]].rename(
        columns={"Plan Option Type_x":"Option Type","Network Type_x":"Network"}
    )
    return plans_view, svc

@st.cache_data
def load_fedvip_rates():
    try:
        dental = pd.read_excel("2026-fedvip-rates_100525.xlsx", sheet_name="Dental", header=2)
        vision = pd.read_excel("2026-fedvip-rates_100525.xlsx", sheet_name="Vision", header=2)
        d_mon = dental[["Plan - Option","Self & Family."]].rename(columns={"Plan - Option":"Plan","Self & Family.":"Dental /mo"})
        v_mon = vision[["Plan - Option","Self & Family."]].rename(columns={"Plan - Option":"Plan","Self & Family.":"Vision /mo"})
    except Exception:
        d_mon = pd.DataFrame(columns=["Plan","Dental /mo"])
        v_mon = pd.DataFrame(columns=["Plan","Vision /mo"])
    return d_mon, v_mon

plans_view, svc_table = load_core()
dental_tbl, vision_tbl = load_fedvip_rates()

def safe_mean(series):
    try:
        s = pd.to_numeric(series, errors="coerce")
        return float(s.mean(skipna=True)) if not s.empty else 0.0
    except Exception:
        return 0.0

# Sidebar
with st.sidebar:
    st.header("Filters")
    zip_input = st.text_input("ZIP Code", "58104").strip()
    include_dental = st.checkbox("Include FEDVIP Dental", value=False)
    include_vision = st.checkbox("Include FEDVIP Vision", value=False)

    st.header("Dental / Vision Premiums")
    dent_val = safe_mean(dental_tbl["Dental /mo"]) if "Dental /mo" in dental_tbl.columns else 0.0
    vis_val = safe_mean(vision_tbl["Vision /mo"]) if "Vision /mo" in vision_tbl.columns else 0.0

    dent_prem = st.number_input("Dental monthly premium ($)", min_value=0.0,
                                value=dent_val if include_dental else 0.0, step=1.0, format="%.0f")
    vis_prem = st.number_input("Vision monthly premium ($)", min_value=0.0,
                                value=vis_val if include_vision else 0.0, step=1.0, format="%.0f")

st.write("✅ Safe numeric conversion fix applied. App ready to re-run.")

