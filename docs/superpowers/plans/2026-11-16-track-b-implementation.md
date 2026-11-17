# Track B Implementation Plan

> Execute inline with scoped Codex implementation help and independent AGY review. The user has approved implementation; do not reopen design or require another approval.

**Goal:** Run the 78 synthetic reports through local NLP into SQLite and show trends in one Streamlit page, with optional advisory API verification.

**Architecture:** medspaCy plus readable rules extracts text separately from deterministic questionnaire observations. Four SQLite tables retain source evidence; two queries power the dashboard. Verification feedback never changes local chart data.

**Tech stack:** Python 3.12, medspaCy 1.3.1, SQLite, Streamlit, Plotly, pytest. No paid calls needed to run the app.

**Spec:** `docs/superpowers/specs/2026-11-16-track-b-design.md`.

## Global constraints

- Keep existing synthetic data unchanged: three patients, 84 scheduled days, 78 reports.
- Never import latent ground-truth events or expected annotations as application observations. Import only regimen fixtures from medication events.
- Questionnaire and text are separate sources; text counts never add to questionnaire totals. Disagreements exclude affected counts, not every observation.
- Retrospective observations use observed_date. Missing submissions remain distinguishable from explicit absence.
- Four tables, two useful SQL queries, one Streamlit page. No extra models, correction chains, submission forms, or benchmark framework.
- Optional API feedback is advisory JSON; without a key or on API failure local functionality remains available.
- Working directory is not a Git repository. Work in the authorized project folder; do not initialize Git or create commits/worktrees.

## Files and interfaces

- `trackb/parser.py`: `parse_text(text: str, report_date: str) -> list[dict]`; `parse_report(report: dict) -> list[dict]`. Source observations carry symptom, presence, evidence, observed_date, episode_count, optional severity and timing, source, and issues. `parse_text` never receives questionnaire or expected annotations.
- `trackb/db.py`: `connect(path)`, `initialize(conn)`, `import_dataset(conn, data_dir)`, `weekly_symptoms(conn, patient_id)`, `medication_comparison(conn, patient_id)`, `daily_symptoms(conn, patient_id)`. Query functions return lists of dictionaries. Stable imports are idempotent.
- `trackb/schema.sql`: exactly four tables, basic constraints, useful indexes.
- `trackb/verify.py`: optional OpenAI-compatible chat-completion verifier using standard-library HTTP; validates returned evidence and preserves local observations.
- `trackb/__main__.py`: import, inspect/query, and verify commands using argparse.
- `app.py`: patient selector, coverage, charts, before/after, report drilldown and verification feedback.
- `tests/`: focused behavioral parser/query/verifier tests plus Streamlit smoke check.
- `README.md`, `requirements.txt`, `.env.example`, `.gitignore`: reproducible setup, limitations, optional API configuration.

## Review focus

1. Vague counts and negation must not create precise symptom events; parser tests cover both.
2. Retrospective text must not conflict with the next day's questionnaire; query test covers the fixture.
3. Repeated imports must not double counts; importer test covers idempotency and four-table/source restrictions.
4. Invalid API output/timeouts must not mutate chart values; verifier tests use mocked HTTP and a database snapshot.
5. Missing data and patient switches must render correctly; run Streamlit AppTest for all three patients.

## Task 1: Local extraction and SQLite analytics

- [x] Write failing tests for negation, vague versus exact count, final stated correction, retrospective dates, source separation, import counts/idempotency, and both queries.
- [x] Implement medspaCy/rules parser, deterministic questionnaire conversion, four-table schema, importer and SQL queries. Text-parser limitations remain explicit.
- [x] Run focused tests and import all 78 reports. Inspect actual query results, do not copy narrative totals from dataset README.
- [x] Obtain independent AGY review and fix substantive findings.

## Task 2: Optional verification and one-page demonstration

- [x] Write failing tests for no-key behavior, evidence-checked advisory output, invalid output, and HTTP failure.
- [x] Implement the verifier, CLI, Streamlit page, dependency pins and README. Select a configurable OpenAI-compatible endpoint; do not read secrets into outputs or make paid calls during tests.
- [x] Run all tests, Streamlit AppTest for all patients, dependency checks and a local server smoke check. Evaluate a few text-only held-out examples honestly without tuning on them.
- [x] Obtain independent review of the integrated application, fix substantive defects, and record commands/results below.

## Progress and rulings

- Preflight: Python 3.14 was the default; `.venv` uses existing Python 3.12 for medspaCy compatibility. No existing application or Git baseline.
- Execution ownership: Codex worker owns parser/database/schema/core tests; root owns verifier/UI/CLI/setup/docs; AGY independently reviews after integration. No concurrent writers to the same file.
- Ruling: use ordinary Streamlit controls and Plotly charts, not a new design system; the user explicitly requested a small functional prototype.
- Ruling: API verification is an explicit selected-report action or CLI command when configured, avoiding paid background calls on Streamlit reruns. Feedback never changes local observations.
- Ruling: compound yesterday/today clauses that the small parser cannot safely resolve retain evidence and receive ambiguous_mixed_dates instead of fabricated observation dates. A general temporal engine remains out of scope.
- Task 1 complete: 17 focused parser/database tests pass; actual import and repeat import both yield three patients, 78 reports, 84 calendar slots, three regimen events. Seven-day vomiting comparison computes eight documented episodes before and one after, with seven submitted days per window.
- Task 2 complete: seven verifier tests and three patient AppTest checks pass. Combined final suite: 27 tests pass. `python -m compileall -q app.py trackb` passes; `uv pip check` finds no dependency conflicts.
- Independent AGY review is in `trackb-implementation-review.md`. Range coercion, source contradictions, explicit negative counts and mixed-date attribution were fixed through failing regression tests. The review's invalid-default-model claim was retracted against official provider documentation. Intentional evidence matching and vocabulary limitations remain documented.
- Final local server: `streamlit run app.py` at http://127.0.0.1:8501, health endpoint returns `ok`; rendered grid and count chart inspected in Chrome. No live paid API calls were made; verification success/failure paths were tested with mocked HTTP.
