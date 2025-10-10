# FEHB + FEDVIP 2026 – Custom Estimator (v2.1)

Streamlit app that estimates total annual cost for FEHB medical plans plus FEDVIP add-ons using household and utilization inputs.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notes
- Estimates = premiums + expected OOP − tax-shelter savings.
- OOP model uses plan benefit fields if present; otherwise safe defaults.
- Always verify final benefits in the SBC and plan brochures.

© 2025 Mason Magle
