# FEHB + FEDVIP 2026 – Decision Edition (v2.2)
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path as _Path

st.set_page_config(page_title="FEHB + FEDVIP 2026 – Decision Edition", page_icon="💼", layout="wide")
st.markdown("<h1 style='text-align:center;'>💼 FEHB + FEDVIP 2026 – Decision Edition (v2.2)</h1>", unsafe_allow_html=True)
st.caption("Top 10 ranked by total annual cost. Includes utilization scaling, confidence flags, CSV export, and visuals.")

def _to_float(x, default=0.0):
    if pd.isna(x): return float(default)
    if isinstance(x, (int, float, np.number)): return float(x)
    s = str(x).replace('$','').replace(',','').strip()
    try:
        if s.lower().startswith('no'): return 0.0
        if 'not covered' in s.lower(): return float(9999)
        if s.endswith('%'): return float(s[:-1]) / 100.0
        return float(s)
    except Exception:
        return float(default)

def pct_or_copay(value, fallback_copay):
    if pd.isna(value): return (False, _to_float(fallback_copay))
    s = str(value).strip()
    if s.endswith('%'): return (True, _to_float(s))
    return (False, _to_float(s, fallback_copay))

def safe_mean_col(df, col):
    try:
        s = pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series([], dtype=float)
        m = s.mean(skipna=True)
        return float(m) if pd.notna(m) else 0.0
    except Exception:
        return 0.0

def round10(x):
    try: return float(np.round(float(x)/10.0)*10.0)
    except Exception: return x

def file_mtime(path):
    try: return datetime.fromtimestamp(_Path(path).stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except Exception: return "n/a"

@st.cache_data
def load_core():
    plans_base = pd.read_excel("FEHB_2026_General_Use_Calculator_PRO_v1.7_Failsafe.xlsx", sheet_name="Plans")
    key = pd.read_excel("2026-fehb-plan-key_100525.xlsx", sheet_name="2026 FEHB Plan Key")
    rates = pd.read_excel("2026-fehb-rates_100525.xlsx", sheet_name="2026 FEHB Rates")
    svc = pd.read_excel("2026-fehb-service-area_100525.xlsx", sheet_name="2026 FEHB Service Area")

    def find_hsa_seed(df):
        for c in df.columns:
            cl = str(c).lower()
            if ("hsa" in cl) and ("seed" in cl or "contribution" in cl or "deposit" in cl):
                return c
        return None

    hsa_col_key = find_hsa_seed(key)
    hsa_col_plans = find_hsa_seed(plans_base)

    plans_base["Plan Option Display"] = (
        plans_base["Plan Option Name"].fillna('') + ' ' + plans_base["Plan Option Type"].fillna('')
    ).str.replace(r'\s+', ' ', regex=True).str.strip()

    rates["Enrollment Code"] = rates["Plan Code"].astype(str) + rates["Enrollment Code"].astype(str)
    sel = (rates["Rate Type"].eq("NP Active") & rates["Enrollment Type"].eq("Self & Family") & rates["Biweekly/Monthly"].eq("Monthly"))
    rates_fam = rates.loc[sel, ["Enrollment Code","Employee Pays","Government Pays"]].rename(columns={"Employee Pays":"Employee /mo","Government Pays":"Govt /mo"})
    rates_fam["Annual (employee)"] = rates_fam["Employee /mo"] * 12

    keep_cols = ["Enrollment Code","Carrier Name","Plan Option Name","Plan Option Type","Plan Code","Network Type","Carrier URL","SBC URL","Provider Directory URL","Plan Formulary URL"]
    if hsa_col_key: keep_cols.append(hsa_col_key)

    merged = plans_base.merge(key[keep_cols], left_on="Enrl_Code", right_on="Enrollment Code", how="left").merge(rates_fam, on="Enrollment Code", how="left")

    if hsa_col_plans and hsa_col_plans not in merged.columns:
        try:
            merged[hsa_col_plans] = plans_base.set_index("Enrl_Code")[hsa_col_plans].reindex(merged["Enrl_Code"]).values
        except Exception:
            merged[hsa_col_plans] = 0.0

    merged["HSA Seed"] = 0.0
    if hsa_col_key and hsa_col_key in merged.columns:
        merged["HSA Seed"] = pd.to_numeric(merged[hsa_col_key], errors="coerce").fillna(0.0)
    if hsa_col_plans and hsa_col_plans in merged.columns:
        merged["HSA Seed"] = merged["HSA Seed"].fillna(0.0) + pd.to_numeric(merged[hsa_col_plans], errors="coerce").fillna(0.0)

    merged["Plan (Full Name)"] = (merged["Carrier Name"].fillna('') + ' ' + merged["Plan Option Name_y"].fillna('')).str.strip()
    merged.loc[merged["Plan (Full Name)"].eq(""), "Plan (Full Name)"] = merged["Plan Option Display"]
    merged["PlanCode2"] = merged["Enrl_Code"].str[:2]
    merged["Website"] = merged["Carrier URL"].apply(lambda x: f"[Visit site]({x})" if isinstance(x,str) and x.startswith("http") else "")

    plans_view = merged[["Plan (Full Name)","Plan Option Type_x","Network Type_x","Enrl_Code","PlanCode2","Employee /mo","Annual (employee)","Govt /mo","HSA Seed","Website","SBC URL","Provider Directory URL","Plan Formulary URL"]].rename(columns={"Plan Option Type_x":"Option Type","Network Type_x":"Network"})
    return plans_view, svc

@st.cache_data
def load_benefits():
    try:
        ben = pd.read_excel("2026-fehb-plan-benefits_100525.xlsx", sheet_name=0)
    except Exception:
        ben = pd.DataFrame()
    if not ben.empty:
        colmap = {}
        for c in ben.columns:
            cl = str(c).strip().lower()
            if "enrollment code" in cl or cl == "enrl_code": colmap[c] = "Enrl_Code"
            elif "pcp" in cl and ("copay" in cl or "visit" in cl): colmap[c] = "PCP"
            elif ("specialist" in cl or "pt" in cl) and ("copay" in cl or "visit" in cl): colmap[c] = "Specialist"
            elif ("urgent" in cl or "uc" in cl) and ("copay" in cl or "visit" in cl): colmap[c] = "Urgent"
            elif ("generic" in cl) and ("rx" in cl or "drug" in cl or "tier 1" in cl): colmap[c] = "Rx_Generic"
            elif (("brand" in cl) or ("preferred" in cl)) and ("rx" in cl or "drug" in cl or "tier 2" in cl): colmap[c] = "Rx_Brand"
            elif "deductible" in cl and ("family" in cl or "in-network" in cl or "inn" in cl): colmap[c] = "Deductible"
            elif "out-of-pocket" in cl or "oop max" in cl or "out of pocket" in cl: colmap[c] = "OOP_Max"
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

with st.expander("🧪 Data validation"):
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("FEHB plans", len(plans_view))
    c2.metric("Service-area rows", len(svc_table))
    c3.metric("Benefit rows", len(benefits) if not benefits.empty else 0)
    c4.metric("Dental rows", len(dental_tbl))
    if not benefits.empty:
        needed = ["PCP","Specialist","Urgent","Rx_Generic","Rx_Brand","Deductible","OOP_Max"]
        covered = {k: round(benefits[k].notna().mean()*100,1) if k in benefits.columns else 0.0 for k in needed}
        st.write("Coverage (% non-null):", covered)
        low = [k for k,v in covered.items() if v < 80.0]
        if low: st.warning("Some benefit fields have <80% coverage: " + ", ".join(low))

with st.sidebar:
    st.header("Filters")
    zip_input = st.text_input("ZIP Code", "58104").strip()
    nationwide_only = st.checkbox("Nationwide plans only", value=False)
    include_dental = st.checkbox("Include FEDVIP Dental", value=False)
    include_vision = st.checkbox("Include FEDVIP Vision", value=False)

    st.header("Utilization & Household")
    util_level = st.selectbox("Utilization level", ["Low","Moderate","High"], index=1)
    rx_count = st.number_input("Monthly Rx count", min_value=0, value=3, step=1)
    pcp_visits = st.number_input("PCP visits", min_value=0, value=6, step=1)
    spec_visits = st.number_input("Specialist/PT visits", min_value=0, value=6, step=1)
    urgent_visits = st.number_input("Urgent care visits", min_value=0, value=1, step=1)

    st.markdown("#### Major events")
    major_surgery = st.checkbox("Major surgery this year", value=False)
    therapy_program = st.checkbox("Therapy program", value=False)
    maternity = st.checkbox("Maternity", value=False)

    st.markdown("#### Dental / Vision premiums")
    dent_default = safe_mean_col(dental_tbl, "Dental /mo")
    vis_default = safe_mean_col(vision_tbl, "Vision /mo")
    dent_prem = st.number_input("Dental monthly premium ($)", min_value=0.0, value=dent_default if include_dental else 0.0, step=1.0, format="%.0f")
    vis_prem = st.number_input("Vision monthly premium ($)", min_value=0.0, value=vis_default if include_vision else 0.0, step=1.0, format="%.0f")

    st.markdown("#### Tax-shelter")
    use_hsa_fsa = st.checkbox("Use HSA/FSA", value=True)
    hsa_fsa_contrib = st.number_input("HSA/FSA annual contribution ($)", min_value=0, value=3000, step=100)
    tax_bracket = st.slider("Tax bracket % (for HSA/FSA savings)", 0, 37, 24)

    st.markdown("#### Sorting")
    sort_by = st.selectbox("Sort by", ["Total", "Premiums", "OOP"])

util_factor = {"Low":0.6, "Moderate":1.0, "High":1.5}[util_level]
preset_map = {"Low": dict(rx=1, pcp=2, spec=2, urgent=0), "Moderate": dict(rx=3, pcp=6, spec=6, urgent=1), "High": dict(rx=6, pcp=10, spec=10, urgent=3)}
p = preset_map[util_level]
rx_count = max(rx_count, p["rx"]); pcp_visits = max(pcp_visits, p["pcp"]); spec_visits = max(spec_visits, p["spec"]); urgent_visits = max(urgent_visits, p["urgent"])

if zip_input:
    zips = svc_table[svc_table["ZIP code"].astype(str) == zip_input]
    allowed = zips["Plan Code"].astype(str).unique()
    df = plans_view[plans_view["PlanCode2"].isin(allowed)].copy()
    if df.empty:
        st.warning("No plans matched that ZIP code; showing all nationwide plans instead.")
        df = plans_view.copy()
else:
    df = plans_view.copy()

if nationwide_only:
    df = df[df["Network"].str.contains("nationwide", case=False, na=False)]

DEFAULTS = {"PCP":30.0,"Specialist":60.0,"Urgent":75.0,"Rx_Generic":10.0,"Rx_Brand":40.0,"Deductible":3000.0,"OOP_Max":12000.0}

def expected_oop_row(enrl_code):
    used_defaults = False
    row = {}
    if not benefits.empty and "Enrl_Code" in benefits.columns:
        recs = benefits[benefits["Enrl_Code"].astype(str).str.upper() == str(enrl_code).upper()]
        if not recs.empty:
            rec = recs.iloc[0].to_dict()
            for k in DEFAULTS.keys():
                row[k] = rec.get(k, np.nan)
    for k, v in DEFAULTS.items():
        if k not in row or pd.isna(row[k]):
            row[k] = v; used_defaults = True

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
    if major_surgery: extras += min(ANCHOR["SURGERY"], oop_max)
    if therapy_program: extras += ANCHOR["THERAPY_BLOCK"]
    if maternity: extras += min(ANCHOR["MATERNITY"], oop_max/2)

    ded_exposure = 0.25 * deductible
    raw_oop = (pcp_cost + spc_cost + urg_cost + rx_gen_cost + rx_brd_cost + extras + ded_exposure) * util_factor
    return min(raw_oop, oop_max), (not used_defaults)

records = []
for _, r in df.iterrows():
    enrl = r["Enrl_Code"]
    premium = _to_float(r["Annual (employee)"])
    oop_est, high_conf = expected_oop_row(enrl)
    add_on = 0.0
    if include_dental: add_on += float(dent_prem) * 12.0
    if include_vision: add_on += float(vis_prem) * 12.0
    total_before_tax = premium + oop_est + add_on
    tax_savings = (tax_bracket/100.0) * min(hsa_fsa_contrib, total_before_tax) if (use_hsa_fsa and hsa_fsa_contrib > 0) else 0.0
    hsa_seed = _to_float(r.get("HSA Seed", 0.0))
    est_total = total_before_tax - tax_savings - hsa_seed
    records.append({
        "Plan (Full Name)": r["Plan (Full Name)"], "Network": r["Network"], "Option Type": r["Option Type"], "Enrl_Code": enrl,
        "Employee Premium /yr": round10(premium), "Est OOP /yr": round10(oop_est), "Add-ons /yr": round10(add_on),
        "Tax savings": round10(tax_savings), "HSA Seed": round10(hsa_seed), "Est Total /yr": round10(est_total),
        "Confidence": "High" if high_conf else "Low", "Website": r["Website"],
        "SBC URL": r["SBC URL"], "Provider Directory URL": r["Provider Directory URL"], "Plan Formulary URL": r["Plan Formulary URL"],
    })

out = pd.DataFrame.from_records(records)
if not out.empty:
    sort_key = {"Total": "Est Total /yr", "Premiums": "Employee Premium /yr", "OOP": "Est OOP /yr"}[sort_by]
    out["Score"] = out["Est Total /yr"] + 0.1*out["Est OOP /yr"] - 0.05*out["Tax savings"]
    out = out.sort_values(by=["Score", sort_key], ascending=[True, True])

if not out.empty:
    top_n = out.head(10).reset_index(drop=True); best = top_n.iloc[0]
    st.markdown(f"### 💰 Top Value Plans for ZIP {zip_input or '—'}")
    st.caption("Ranked by lowest estimated total annual cost (premiums + OOP − tax savings − HSA seed).")
    display = top_n[["Plan (Full Name)","Network","Option Type","Employee Premium /yr","Est OOP /yr","Add-ons /yr","Tax savings","HSA Seed","Est Total /yr","Confidence"]]\
        .rename(columns={"Employee Premium /yr":"Premiums","Est OOP /yr":"OOP","Add-ons /yr":"Add-ons","Tax savings":"Tax Benefit","HSA Seed":"HSA Credit","Est Total /yr":"Total Est. Cost"})
    st.dataframe(display.style.format({"Premiums":"${:,.0f}","OOP":"${:,.0f}","Add-ons":"${:,.0f}","Tax Benefit":"${:,.0f}","HSA Credit":"${:,.0f}","Total Est. Cost":"${:,.0f}"}),
                 use_container_width=True, hide_index=True)
    st.markdown(f"**🏆 Best Overall:** {best['Plan (Full Name)']} — est. ${best['Est Total /yr']:,.0f}/yr • Confidence: {best['Confidence']}")
    colA, colB, colC = st.columns(3)
    cheap_prem = out.nsmallest(1, "Employee Premium /yr").iloc[0]
    low_oop = out.nsmallest(1, "Est OOP /yr").iloc[0]
    best_tax = out.nlargest(1, "Tax savings").iloc[0]
    colA.metric("Cheapest premiums", cheap_prem["Plan (Full Name)"], f"${cheap_prem['Employee Premium /yr']:,.0f}/yr")
    colB.metric("Lowest OOP", low_oop["Plan (Full Name)"], f"${low_oop['Est OOP /yr']:,.0f}/yr")
    colC.metric("Best tax benefit", best_tax["Plan (Full Name)"], f"${best_tax['Tax savings']:,.0f}/yr")
    try:
        st.bar_chart(top_n.set_index("Plan (Full Name)")["Est Total /yr"])
    except Exception:
        pass
    csv_bytes = display.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download Top 10 as CSV", data=csv_bytes, file_name="fehb_top10_estimates.csv", mime="text/csv")
else:
    st.warning("No plans available to estimate.")

q = st.text_input("Search plans (name, network, option):", "").lower().strip()
view = out
if q and not out.empty:
    view = out[out.apply(lambda r: q in ' '.join(map(str, r.values)).lower(), axis=1)]

cols_main = ["Plan (Full Name)","Network","Option Type","Enrl_Code","Employee Premium /yr","Est OOP /yr","Add-ons /yr","Tax savings","HSA Seed","Est Total /yr","Confidence","Website"]
if not view.empty:
    st.dataframe(view[cols_main].head(50).style.format({"Employee Premium /yr":"${:,.0f}","Est OOP /yr":"${:,.0f}","Add-ons /yr":"${:,.0f}","Tax savings":"${:,.0f}","HSA Seed":"${:,.0f}","Est Total /yr":"${:,.0f}"}),
                 use_container_width=True)
else:
    st.info("No rows to display after filtering.")

st.markdown('---')
c1,c2,c3,c4 = st.columns(4)
c1.metric("Plans Displayed", len(view))
c2.metric("Avg Total (Top 10)", f"${out.head(10)['Est Total /yr'].mean():,.0f}" if not out.empty else "$0")
c3.metric("Nationwide filter", "On" if ('nationwide_only' in locals() and nationwide_only) else "Off")
c4.metric("Data last updated", max(file_mtime('2026-fehb-rates_100525.xlsx'), file_mtime('2026-fehb-plan-key_100525.xlsx'), file_mtime('FEHB_2026_General_Use_Calculator_PRO_v1.7_Failsafe.xlsx')))
st.caption("© 2025 Mason Magle | Decision logic is heuristic. Verify key benefits in SBCs before enrollment.")
