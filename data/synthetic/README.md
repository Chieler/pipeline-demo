# Synthetic Clinical Dataset: Oncology Chemoradiation & CINV
**Pipeline Securities Inc. - Track B: Patient-Reported Data: Store, Manage & Chart**  
**Dataset Version**: 1.1.0 (Fixed reproducible dates, refined vague counts & regimen change fixture)  
**Date Range**: 2026-10-05 to 2026-11-01 (28 scheduled days)  
**Authorship**: `antigravity-client-19`

> **Notice**: Model-expected annotations are synthetic agent-reviewed evaluation labels designed for parser benchmarking, not human-verified clinical ground truth.

---

## 1. Dataset Overview & Slot Accounting

| Metric | Target | Actual | Verification |
| :--- | :--- | :--- | :--- |
| **Total Synthetic Patients** | 3 patients | **3 patients** | `SYN-PT-101`, `SYN-PT-102`, `SYN-PT-103` |
| **Scheduled Days per Patient** | 28 days | **28 days** | Continuous 4-week window |
| **Total Calendar Slots** | 3 × 28 = 84 slots | **84 slots** | Verified in `schedule_slots.json` |
| **Intentionally Missing Check-Ins** | Exactly 6 slots | **6 slots** | PT-101 (Days 12, 20), PT-102 (Days 7, 25), PT-103 (Days 15, 27) |
| **Total Submitted Reports** | Exactly 78 reports | **78 reports** | Verified in `check_ins.json` and `check_ins.jsonl` |

### Accounting Note on Correction Records
Intra-report corrections (e.g., PT-101 Day 26: *"Threw up twice... wait, actually three times"*) occur **within** an existing scheduled check-in. They do not spawn separate slots or alter the 78 submitted / 6 missing slot boundary.

### Dev / Eval Split Partitioning
* **Development Split (`dev`)**: Patients `SYN-PT-101` and `SYN-PT-102` (52 submitted reports, 4 missing slots). Used for rule design, prompt engineering, and database validation.
* **Evaluation Split (`eval`)**: Patient `SYN-PT-103` (26 submitted reports, 2 missing slots). Held-out evaluation set containing clinical symptom classes **completely absent** from the development split.

---

## 2. Generation Methodology & Prevention of Latent Leakage

The dataset was generated in strict chronological and causal order:
1. **Ground Truth Events FIRST (`ground_truth_events.json`)**: Authoring latent clinical reality (actual emesis counts, physiological severity, medication compliance) prior to any text generation.
2. **Patient Free-Text Check-Ins SECOND (`check_ins.json` / `check_ins.jsonl`)**: Rendering natural, messy, colloquial patient check-in entries and structured questionnaire responses based on the latent reality.
3. **Expected Extraction Annotations THIRD (`expected_annotations.json` / `expected_annotations.jsonl`)**: Creating faithful gold-standard extraction targets **strictly bounded by what the patient text and questionnaire actually reveal**. Latent facts do **not** leak into expected labels. For colloquial unquantified counts (e.g., *"a couple times"*), the annotation retains the verbatim phrase with `exact_count: null`, `count_bounds: null`, and `is_unquantified_count: true`, intentionally avoiding unsupported numeric precision.

### Counting & Aggregation Semantics (Consensus Policy)
* **Sole Explicit Single-Day Count Rule**: A sole explicit single-day count (e.g., *"Vomited 3 times between 3pm and 7pm"*) contributes its documented count (3) to documented episodes for that observation period. It is preserved with its source evidence and timing, rather than claimed as an exhaustive whole-day census.
* **Partial-Day Temporal Scoping**: A partial-day negative statement (e.g., *"no nausea tonight"*) represents absence for that time window and does not conflict with earlier daytime presence.
* **Multiple Claims & Disambiguation**: Multiple same-day claims are deduplicated only when explicit identical full-day totals are stated; discordant partial and full reports flag clinical review.
* **Unquantified Phrases**: Colloquial expressions (*"a couple times"*, *"multiple times"*) retain original phrasing with `exact_count: null` to avoid false precision.

---

## 3. Linguistic & Clinical Phenomena Included

| Phenomenon | Example from Dataset | Expected Handling |
| :--- | :--- | :--- |
| **Exact Counts** | *"Vomited 3 times between 3pm and 7pm, pure bile."* (PT-101 D18) | `exact_count: 3`, `bounds: null` |
| **Vague / Colloquial Counts** | *"threw up a couple times after taking my pills."* (PT-101 D14) | `exact_count: null`, `count_bounds: null`, `is_unquantified_count: true`, `review_needed: true` |
| **Explicit Negation** | *"No nausea or vomiting today. Just tired"* (PT-101 D09) | `status: "absent"`, `exact_count: 0` |
| **Uncertain Symptoms** | *"Might have had a slight headache earlier, hard to tell with neck pain"* (PT-102 D27) | `status: "uncertain"`, `review_needed: true` |
| **Mixed Time Windows** | *"Yesterday was brutal, threw up twice in the evening. Today nausea is down to a 4"* (PT-101 D13) | Anchors: Vomiting -> `yesterday`; Nausea -> `current` |
| **Text/Questionnaire Conflict** | Questionnaire: `Nausea: 0`; Text: *"Still feeling slightly queasy in the morning"* (PT-101 D21) | `conflict_with_questionnaire: true`, `review_needed: true` |
| **Correction / Overlap** | *"Threw up twice this morning... wait, actually three times counting dry heaves"* (PT-101 D26) | Total count: 3 (guards against double counting 2 + 3 = 5) |
| **Uncertain Medication Names** | *"Took the little white nausea tablet with breakfast"* (PT-101 D25) | Extracts phrase, flags for clinical concept mapping |
| **Medication Switch** | Discontinued prochlorperazine, started aprepitant + ondansetron (PT-102 D17) | Tracked in `medication_events.json` with explicit clinical rationale |
| **Weight Alert Threshold** | Patient drops below 5% baseline weight threshold (PT-102 D23, crosses 135 lb) | Optional dataset metric; triggers alert flag in clinical data |

---

## 4. Regimen Change Fixture (For SQL Before/After Query)

The dataset includes an explicit clinical medication change fixture designed for before/after query testing:
* **Patient**: `SYN-PT-102` (Maria Santos)
* **Change Transition Day**: `2026-10-21` (Day 17) - *Excluded from comparison windows as transition day*
* **Pre-Change Window (7 Days: `2026-10-14` to `2026-10-20`, Days 10-16)**:
  * Baseline antiemetic: Prochlorperazine 10mg TID PRN.
  * Reporting coverage: 7 scheduled calendar days, 7 submitted reports (100% coverage).
  * Descriptive observation: 8 documented vomiting episodes across the 7-day period (questionnaire counts: Day 10 = 3, Day 11 = 1, Day 12 = 1, Day 16 = 3). Day 10's free-text count remains unquantified; its structured questionnaire supplies the number. Text and questionnaire counts are not added together.
* **Change Event (Day 17, `2026-10-21`)**:
  * Simulated clinical event: Provider discontinued Prochlorperazine; initiated triple antiemetic therapy (Aprepitant 125mg/80mg + Ondansetron 8mg TID).
* **Post-Change Window (7 Days: `2026-10-22` to `2026-10-28`, Days 18-24)**:
  * New regimen: Aprepitant 125mg/80mg + Ondansetron 8mg TID.
  * Reporting coverage: 7 scheduled calendar days, 7 submitted reports (100% coverage).
  * Descriptive observation: 1 vomiting episode reported across the 7-day period (Day 23 chemo day, 0 on Days 18, 19, 20, 21, 22, 24).
* **Analytical Framing**:
  * Evaluates descriptive association and reporting coverage across balanced 7-day pre/post observation windows.
  * Documents synthetic scenario progression only; makes **no medical efficacy or causal claims**.

---

## 5. Held-Out Symptom Classes (Eval Split Only: `SYN-PT-103`)

The evaluation split (`SYN-PT-103`, Robert Kowalski) introduces three clinically authentic symptom classes resulting from chemoradiation that are **entirely absent** from the development split:
1. **Tinnitus / Ototoxicity (`tinnitus`)**: Induced by cumulative cisplatin toxicity. Appears on Day 11 and persists (*"persistent high-pitched ringing in both ears that won't go away"*).
2. **Intractable Singultus / Hiccups (`singultus`)**: Induced by high-dose dexamethasone and cisplatin neuro-gastric irritation. Appears on Days 5-6 (*"violent hiccups around noon that wouldn't stop for four hours straight"*).
3. **Peripheral Neuropathy (`peripheral_neuropathy`)**: Cisplatin stocking-glove neurotoxicity. Manifests on Days 22-24 (*"fingertips feel numb and prickly like pins and needles, dropped my coffee mug"*).

---

## 6. File Manifest

* [`patients.json`](patients.json): Demographics, cancer staging, protocol details, baseline and alert weights.
* [`schedule_slots.json`](schedule_slots.json): All 84 calendar slots with submission vs. missing status.
* [`ground_truth_events.json`](ground_truth_events.json): Source clinical reality authored before text generation.
* [`check_ins.json`](check_ins.json) & [`check_ins.jsonl`](check_ins.jsonl): 78 submitted patient reports with free-text and questionnaires.
* [`expected_annotations.json`](expected_annotations.json) & [`expected_annotations.jsonl`](expected_annotations.jsonl): Faithful gold-standard annotations with evidence quotes.
* [`medication_events.json`](medication_events.json): All medication starts, switches, administrations, and missed doses.
