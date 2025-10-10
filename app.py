# FEHB + FEDVIP 2026 Custom Estimator (v2.1)
# Mason Magle | Streamlit Web App
# ------------------------------------------------
# Run with: streamlit run app.py

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="FEHB + FEDVIP 2026 – Custom Estimator", page_icon="💼", layout="wide")

st.markdown("<h1 style='text-align:center;'>💼 FEHB + FEDVIP 2026 – Custom Estimator (v2.1)</h1>", unsafe_allow_html=True)
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
def load_benefits():
    try:
        ben = pd.read_excel("2026-fehb-plan-benefits_100525.xlsx", sheet_name=0)
    except Exception as e:
        ben = pd.DataFrame()
    if not ben.empty:
        colmap = {}
        for c in ben.columns:
            cl = str(c).strip().lower()
            if "enrollment code" in cl or cl == "enrl_code":
                colmap[c] = "Enrl_Code"
            elif "pcp" in cl and ("copay" in cl or "visit" in cl):
                colmap[c] = "PCP"
            elif ("specialist" in cl or "pt" in cl) and ("copay" in cl or "visit" in cl):
                colmap[c] = "Specialist"
            elif ("urgent" in cl or "uc" in cl) and ("copay" in cl or "visit" in cl):
                colmap[c] = "Urgent"
            elif ("generic" in cl) and ("rx" in cl or "drug" in cl or "tier 1" in cl):
                colmap[c] = "Rx_Generic"
            elif (("brand" in cl) or ("preferred" in cl)) and ("rx" in cl or "drug" in cl or "tier 2" in cl):
                colmap[c] = "Rx_Brand"
            elif "deductible" in cl and ("family" in cl or "in-network" in cl or "inn" in cl):
                colmap[c] = "Deductible"
            elif "out-of-pocket" in cl or "oop max" in cl or "out of pocket" in cl:
                colmap[c] = "OOP_Max"
            elif cl in ("enrl_code","enrollment code"):
                colmap[c] = "Enrl_Code"
        ben = ben.rename(columns=colmap)
    return ben

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
benefits = load_benefits()
dental_tbl, vision_tbl = load_fedvip_rates()

with st.sidebar:
    st.header("Filters")
    zip_input = st.text_input("ZIP Code", "58104").strip()
    include_dental = st.checkbox("Include FEDVIP Dental", value=False)
    include_vision = st.checkbox("Include FEDVIP Vision", value=False)

    st.header("Utilization & Household")
    family_size = st.number_input("Family size", min_value=1, max_value=10, value=5, step=1)
    income = st.number_input("Annual income ($)", min_value=0, value=200000, step=1000)
    util_level = st.selectbox("Utilization level", ["Low","Moderate","High"], index=1)

    st.markdown("#### Visit counts")
    rx_count = st.number_input("Monthly Rx count", min_value=0, value=3, step=1)
    pcp_visits = st.number_input("PCP visits", min_value=0, value=6, step=1)
    spec_visits = st.number_input("Specialist/PT visits", min_value=0, value=6, step=1)
    urgent_visits = st.number_input("Urgent care visits", min_value=0, value=1, step=1)

    st.markdown("#### Events")
    major_surgery = st.checkbox("Major surgery this year", value=False)
    therapy_program = st.checkbox("Therapy program", value=False)
    maternity = st.checkbox("Maternity", value=False)

    st.markdown("#### Dental / Vision")
    major_dental = st.checkbox("Major dental work", value=False)
    crowns = st.number_input("# of crowns/implants", min_value=0, value=0, step=1)
    dent_prem = st.number_input("Dental monthly premium ($)", min_value=0.0, value=float(dental_tbl.get("Dental /mo", pd.Series([0])).mean(skipna=True) if include_dental else 0), step=1.0, format="%.0f")
    vis_prem = st.number_input("Vision monthly premium ($)", min_value=0.0, value=float(vision_tbl.get("Vision /mo", pd.Series([0])).mean(skipna=True) if include_vision else 0), step=1.0, format="%.0f")

    st.markdown("#### Tax-shelter")
    use_hsa_fsa = st.checkbox("Use HSA/FSA", value=True)
    hsa_fsa_contrib = st.number_input("HSA/FSA annual contribution ($)", min_value=0, value=3000, step=100)
    tax_bracket = st.slider("Tax bracket % (for HSA/FSA savings)", 0, 37, 24)

    st.markdown("#### Sorting")
    sort_by = st.selectbox("Sort by", ["Total", "Premiums", "OOP"])
    presets = st.checkbox("Utilization presets apply", value=True)
    state_2 = st.text_input("Home state (2-letter)", "ND").strip().upper()

if presets:
    preset_map = {
        "Low": dict(rx=1, pcp=2, spec=2, urgent=0),
        "Moderate": dict(rx=3, pcp=6, spec=6, urgent=1),
        "High": dict(rx=6, pcp=10, spec=10, urgent=3),
    }
    p = preset_map.get(util_level, preset_map["Moderate"])
    rx_count = max(rx_count, p["rx"])
    pcp_visits = max(pcp_visits, p["pcp"])
    spec_visits = max(spec_visits, p["spec"])
    urgent_visits = max(urgent_visits, p["urgent"])

if zip_input:
    zips = svc_table[svc_table["ZIP code"].astype(str) == zip_input]
    allowed = zips["Plan Code"].astype(str).unique()
    df = plans_view[plans_view["PlanCode2"].isin(allowed)].copy()
    if df.empty:
        st.warning("No plans matched that ZIP code; showing all nationwide plans instead.")
        df = plans_view.copy()
else:
    df = plans_view.copy()

DEFAULTS = {"PCP":30.0,"Specialist":60.0,"Urgent":75.0,"Rx_Generic":10.0,"Rx_Brand":40.0,"Deductible":3000.0,"OOP_Max":12000.0}

def expected_oop_row(enrl_code):
    row = {}
    if not benefits.empty and "Enrl_Code" in benefits.columns:
        recs = benefits[benefits["Enrl_Code"].astype(str).str.upper() == str(enrl_code).upper()]
        if not recs.empty:
            rec = recs.iloc[0].to_dict()
            for k in DEFAULTS.keys():
                row[k] = rec.get(k, np.nan)
    for k, v in DEFAULTS.items():
        if k not in row or pd.isna(row[k]):
            row[k] = v
    PCP_is_pct, PCP_val = pct_or_copay(row["PCP"], DEFAULTS["PCP"])
    SPC_is_pct, SPC_val = pct_or_copay(row["Specialist"], DEFAULTS["Specialist"])
    URG_is_pct, URG_val = pct_or_copay(row["Urgent"], DEFAULTS["Urgent"])
    Gen_is_pct, Gen_val = pct_or_copay(row["Rx_Generic"], DEFAULTS["Rx_Generic"])
    Brd_is_pct, Brd_val = pct_or_copay(row["Rx_Brand"], DEFAULTS["Rx_Brand"])
    deductible = _to_float(row["Deductible"], DEFAULTS["Deductible"])
    oop_max = _to_float(row["OOP_Max"], DEFAULTS["OOP_Max"])
    ANCHOR = dict(PCP=150, SPC=250, URG=300, RX_GEN=15, RX_BRD=80, SURGERY=8000, THERAPY_BLOCK=1000, MATERNITY=9000)
    pcp_cost = (ANCHOR["PCP"]*PCP_val if PCP_is_pct else PCP_val) * pcp_visits
    spc_cost = (ANCHOR["SPC"]*SPC_val if SPC_is_pct else SPC_val) * spec_visits
    urg_cost = (ANCHOR["URG"]*URG_val if URG_is_pct else URG_val) * urgent_visits
    rx_months = 12
    rx_gen_cost = (ANCHOR["RX_GEN"]*Gen_val if Gen_is_pct else Gen_val) * rx_count * rx_months * 0.7
    rx_brd_cost = (ANCHOR["RX_BRD"]*Brd_val if Brd_is_pct else Brd_val) * max(0, rx_count-2) * rx_months * 0.3
    extras = 0.0
    if major_surgery:
        extras += min(ANCHOR["SURGERY"], oop_max)
    if therapy_program:
        extras += ANCHOR["THERAPY_BLOCK"]
    if maternity:
        extras += min(ANCHOR["MATERNITY"], oop_max/2)
    ded_exposure = 0.25 * deductible
    raw_oop = pcp_cost + spc_cost + urg_cost + rx_gen_cost + rx_brd_cost + extras + ded_exposure
    return min(raw_oop, oop_max)

records = []
for _, r in df.iterrows():
    enrl = r["Enrl_Code"]
    premium = float(_to_float(r["Annual (employee)"]))
    oop_est = expected_oop_row(enrl)
    add_on = 0.0
    if include_dental:
        add_on += float(dent_prem) * 12.0
        if major_dental or crowns > 0:
            crowns_cost = crowns * 1200.0
            plan_pays = min(2000.0, 0.5 * crowns_cost)
            add_on += max(0.0, crowns_cost - plan_pays)
    if include_vision:
        add_on += float(vis_prem) * 12.0
    total_before_tax = premium + oop_est + add_on
    tax_savings = 0.0
    if use_hsa_fsa and hsa_fsa_contrib > 0:
        tax_savings = (tax_bracket/100.0) * min(hsa_fsa_contrib, total_before_tax)
    est_total = total_before_tax - tax_savings
    records.append({
        "Plan (Full Name)": r["Plan (Full Name)"],
        "Network": r["Network"],
        "Option Type": r["Option Type"],
        "Enrl_Code": enrl,
        "Employee Premium /yr": round(premium, 2),
        "Est OOP /yr": round(oop_est, 2),
        "Add-ons /yr": round(add_on, 2),
        "Tax savings": round(tax_savings, 2),
        "Est Total /yr": round(est_total, 2),
        "Website": r["Website"],
        "SBC URL": r["SBC URL"],
        "Provider Directory URL": r["Provider Directory URL"],
        "Plan Formulary URL": r["Plan Formulary URL"],
    })

out = pd.DataFrame.from_records(records)
sort_key = {"Total":"Est Total /yr","Premiums":"Employee Premium /yr","OOP":"Est OOP /yr"}[sort_by]
out = out.sort_values(by=sort_key, ascending=True)

if not out.empty:
    best = out.iloc[0]
    st.markdown(f"### 💰 Best Value Plan: **{best['Plan (Full Name)']}** — est. ${best['Est Total /yr']:,.0f}/yr")
else:
    st.warning("No plans available to estimate.")

q = st.text_input("Search plans (name, network, option):", "").lower().strip()
view = out
if q:
    view = out[out.apply(lambda r: q in ' '.join(map(str, r.values)).lower(), axis=1)]

cols_main = ["Plan (Full Name)","Network","Option Type","Enrl_Code",
             "Employee Premium /yr","Est OOP /yr","Add-ons /yr","Tax savings","Est Total /yr","Website"]
st.dataframe(view[cols_main].head(30), use_container_width=True)

with st.expander("📄 Benefit Links (SBC / Provider / Formulary)"):
    st.dataframe(view[["Plan (Full Name)","SBC URL","Provider Directory URL","Plan Formulary URL"]].head(30),
                 use_container_width=True)

st.markdown('---')
st.subheader('📊 Summary')
c1,c2,c3 = st.columns(3)
c1.metric('Plans Displayed', len(view))
c2.metric('Avg Est Total /yr', f"${view['Est Total /yr'].mean(skipna=True):,.0f}" if len(view)>0 else "$0")
c3.metric('ZIP Entered', zip_input if zip_input else '—')
st.caption('© 2025 Mason Magle | FEHB + FEDVIP 2026 Custom Estimator v2.1 | Data: OPM PUF | Heuristic model; confirm SBC.')
