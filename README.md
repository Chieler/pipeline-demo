# Track B: Patient-Reported Symptom Trends

An oncology prototype that ingests patient-reported check-ins (messy free text + questionnaires), extracts structured clinical observations, stores them in SQLite, and visualizes longitudinal trends in Streamlit for a 30-second pre-encounter clinician review.

---

## Quickstart

Requires **Python 3.12**. No API keys, model downloads, or paid services are required.

```sh
# 1. Create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Import dataset into SQLite (data/trackb.sqlite)
python -m trackb import --local-only

# 4. Launch the Streamlit dashboard
streamlit run app.py
```
Open the printed URL (typically `http://localhost:8501`). If the database is empty, the app imports the synthetic dataset automatically.

---

## CLI Commands

### 1. Parse Free-Text Report
Test the medspaCy TargetMatcher and ConText extraction rules on arbitrary text:
```sh
python -m trackb parse "Threw up twice after dinner, felt nauseous all morning." --date 2026-10-17
```

### 2. Analytical SQL Queries
Run the two clinical analytical queries:
```sh
# Weekly symptom summary (present days, vomiting counts, coverage)
python -m trackb query weekly --patient SYN-PT-101

# 7-day before/after medication change comparison (Maria Santos, Day 17 antiemetic switch)
python -m trackb query medication --patient SYN-PT-102
```

### 3. Run Automated Tests
Execute the full test suite (35 passing tests):
```sh
pytest
```

---

## Ingestion & Review Modes

- **Fast local import (`--local-only`):** Ingests reports using the local deterministic medspaCy rule engine in ~1 second:
  ```sh
  python -m trackb import --local-only
  ```
- **Full import with automatic review:** Runs secondary semantic review through the active local AGY CLI session (Gemini 3.8 Flash High) without cloud API costs:
  ```sh
  python -m trackb import
  ```

---

## What to Explore in the Dashboard

1. **Top Metrics & Adherence:** Review reporting coverage (e.g., 26/28 check-ins submitted), documented vomiting counts, and excluded unclear days.
2. **28-Day Presence Heatmap:** Color-coded clinical states across all 4 weeks (*Present*, *Absent*, *Uncertain*, *Conflict*, *Unassessed*, *Missing*). Missing days and unmentioned symptoms are never zeroed out.
3. **Daily Vomiting Trend:** Documented episodes with dashed line marking the Day 17 medication change. Days with missing or ambiguous counts are plotted with distinct red `x` indicators rather than 0.
4. **Before vs. After Regimen Switch:** Balanced 7-day pre/post comparison for Maria Santos (prochlorperazine $\to$ aprepitant + ondansetron), excluding the transition day.
5. **Check-In Detail Inspector:** Side-by-side inspection of structured questionnaire answers and raw patient messages with exact-substring evidence quotes.
