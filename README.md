# FEHB + FEDVIP 2026 – Decision Edition (v2.2)

Streamlit app ranking FEHB and FEDVIP 2026 plans by estimated total annual cost.

## Features
- Top 10 ranked plans (premiums + OOP − tax savings − HSA seed)
- Utilization scaling (Low 0.6×, Moderate 1.0×, High 1.5×)
- Confidence flags and validation dashboard
- CSV export, bar chart, rounded currency
- Optional "Nationwide only" filter
- HSA seed credit detection (if present)

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

© 2025 Mason Magle | Heuristic model. Verify benefits with official SBCs.
