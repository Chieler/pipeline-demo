# Track B: patient-reported symptom trends

A small oncology prototype: patient text → medspaCy/rules extraction → SQLite → Streamlit. Three synthetic patients have 78 check-ins over four weeks. Optional API verification checks the local extraction without changing chart data.

## Run

Use **Python 3.12**. No spaCy model download, API key, or paid service is required.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m trackb import
streamlit run app.py
```

Open the URL printed by Streamlit (normally http://localhost:8501). If the SQLite database is empty, the app imports the supplied dataset automatically. Imports use stable source IDs and can be repeated.

```sh
python -m trackb parse "Threw up twice after dinner, felt nauseous all morning." --date 2026-10-17
python -m trackb query weekly --patient SYN-PT-101
python -m trackb query medication --patient SYN-PT-102
python -m pytest
```

SQLite defaults to `data/trackb.sqlite`. Set `TRACKB_DB_PATH` or use `python -m trackb --db path.sqlite import` for a separate database. Existing report IDs are skipped on repeat imports, preserving verification feedback. After changing parser rules, import into a fresh database path to re-extract the data.

## What to show in the presentation

1. Select a patient and review symptom patterns, reporting gaps, and documented vomiting counts.
2. Select Maria Santos for the seven-day before/after medication-change comparison. Show coverage; describe association, not efficacy.
3. Inspect an original report beside its extracted fields and questionnaire. Sources stay separate.
4. Run the text-only parser on an example. Explain supported counts, unknown values, and vocabulary limits.
5. If configured, verify one synthetic report with the API and inspect advisory feedback. Chart values stay unchanged.

## Extraction and storage

The local parser uses **medspaCy TargetMatcher/ConText and explicit extraction rules**. It is primarily rule-based, not a pretrained medical language model. It recognizes a documented symptom vocabulary and common phrasing; arbitrary unseen symptoms are not guaranteed to be detected. No training on this small dataset is implied.

Questionnaire values are read directly in code. Text observations are separately extracted, stored, and inspected. Questionnaire counts are the daily default; partial text counts are never added to them. Eligible retrospective text can contribute on a day without a questionnaire. Unsupported counts and conflicting evidence are flagged rather than guessed. Missing reports and unmentioned symptoms do not become zeroes.

SQLite has four tables: `patients`, `reports`, `symptom_observations`, and `medication_events`. The two analytical SQL queries summarize weekly symptoms and compare symptoms around the explicit synthetic regimen change. Only regimen fixture records are imported from medication events; generated administration facts and latent source facts are not patient reports.

The dashboard labels counts as documented episodes: it does not claim complete clinical observation. Medication associations are patient-stated or descriptive, not diagnoses or causal conclusions.

## Optional API verification

The adapter supports an **OpenAI-compatible Chat Completions endpoint**. Export configuration in the shell before running the app; `.env.example` documents the variables but is not loaded automatically.

```sh
export VERIFIER_API_KEY="your-key"
export VERIFIER_BASE_URL="https://api.openai.com/v1"
export VERIFIER_MODEL="gpt-4.1-mini"
streamlit run app.py
```

`OPENAI_API_KEY` is also accepted. Choose a model supporting JSON-object responses. Other providers may need a different base URL/model; this is not a universal API adapter.

With a key configured, the report drilldown offers **Verify this report with API**. It sends only that synthetic report, its questionnaire, and the local observations. Verification is explicit to avoid background calls or surprise charges. Alternatively:

```sh
python -m trackb verify CHK-SYN-PT-101-D01
```

Feedback is stored as JSON on the report. Evidence quotes/field references are checked; malformed or unsupported feedback is marked invalid. API disagreement is visibly separate from local parsing issues and never modifies analytical observations. API failure leaves the local pipeline usable. Agreement is advisory, not proof of accuracy. Never put keys in the database or repository. No live paid API calls are needed for the test suite.

## Checks and limitations

Focused tests cover text extraction, negation, vague counts, dates, source separation, import idempotency, SQL results, verifier failure handling, and rendering all three patients. Expected annotations are used for checking only, never for creating application observations.

The dataset was generated facts-first and independently reviewed by another AGY agent. Its labels are **agent-reviewed synthetic labels**, not human-verified clinical ground truth. Patient SYN-PT-103 is held out from rule/prompt tuning. The prototype does not establish general medical extraction accuracy or clinical readiness.

The [design](docs/superpowers/specs/2026-11-16-track-b-design.md), [validation examples and known misses](docs/validation-examples.md), [implementation plan](docs/superpowers/plans/2026-11-16-track-b-implementation.md), [dataset manifest](data/synthetic/README.md), and [dataset review](data/synthetic/review.md) document decisions and trade-offs. The original public demo extracts are retained in `extracted_demo_data/`.
