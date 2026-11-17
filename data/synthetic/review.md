# Independent Review: Track B Synthetic Clinical Dataset
**Evaluation & Acceptance Report (Independent Agent QA)**  
**Reviewer**: `trackb-data-review` (Independent Reviewer Agent)  
**Target Artifacts**: `data/synthetic/` (`patients.json`, `schedule_slots.json`, `ground_truth_events.json`, `check_ins.json`, `check_ins.jsonl`, `expected_annotations.json`, `expected_annotations.jsonl`, `medication_events.json`, `README.md`)  
**Context Reference**: `RESEARCH_AND_TRACK_B_FINDINGS.md` and `extracted_demo_data/oncology_radiation.json`  
**Dataset Version**: v1.1.0 (Final Reconciled Release)  
**Date**: 2026-11-16  
**Final Status**: **FULLY ACCEPTED (Ready for Track B Application & Pipeline Development)**

---

## 1. Executive Summary & Verification Matrix

The synthetic clinical dataset authored by `antigravity-client-19` has undergone an exhaustive automated and qualitative QA audit. The dataset models 3 oncology patients undergoing chemoradiation (IMRT + weekly cisplatin) over 28 scheduled calendar days. Note: This assessment constitutes **independent agent QA**, not human-verified gold-standard clinical labels.

The dataset strictly adheres to the scope specifications:
- **3 synthetic patients** (`SYN-PT-101`, `SYN-PT-102` in Dev; `SYN-PT-103` in Eval).
- **84 calendar slots** across 28 days (2026-10-05 to 2026-11-01).
- **Exactly 6 missing check-ins** and **exactly 78 submitted report records** across JSON and JSONL formats.
- **Strict held-out symptom isolation**: 3 held-out symptom classes (`tinnitus`, `singultus`, `peripheral_neuropathy`) are present in Eval (`SYN-PT-103`, 17 occurrences) and **100% absent from Dev** (`SYN-PT-101`, `SYN-PT-102`).
- **Verbatim quote accuracy**: 209 of 209 evidence quotes match patient free text character-for-character.
- **Source demo data preservation**: All 5 original files in `extracted_demo_data/` remain untouched.
- **Full reconciliation in v1.1.0**:
  1. False precision in vague quantifiers eliminated (`count_bounds: null`, `is_unquantified_count: true`).
  2. Spurious count-correction tag removed from syncope colloquial intensifier (`CHK-SYN-PT-103-D19`).
  3. Patient-reported missed doses (`status: "missed"`) populated into `medication_events.json`.
  4. Partial-day episode counts reconciled per architecture consensus.

| Requirement | Target | Verified Value | Compliance Status |
| :--- | :--- | :--- | :--- |
| **Cohort Size** | 3 synthetic patients | 3 patients (`SYN-PT-101`, `SYN-PT-102`, `SYN-PT-103`) | **PASS** |
| **Dev / Eval Partitioning** | 2 Dev, 1 Eval | Dev: `PT-101`, `PT-102` (52 reports); Eval: `PT-103` (26 reports) | **PASS** |
| **Schedule Duration** | 28 days per patient | 28 days (2026-10-05 to 2026-11-01) | **PASS** |
| **Total Calendar Slots** | Exactly 84 slots | 84 slots in `schedule_slots.json` | **PASS** |
| **Intentionally Missing Check-Ins** | Exactly 6 slots | 6 slots (`PT-101` D12/D20, `PT-102` D07/D25, `PT-103` D15/D27) | **PASS** |
| **Submitted Check-Ins** | Exactly 78 reports | Exactly 78 in `check_ins.json` and 78 in `check_ins.jsonl` | **PASS** |
| **Expected Annotations** | Exactly 78 bundles | Exactly 78 in `expected_annotations.json` and `expected_annotations.jsonl` | **PASS** |
| **Ground Truth Latent States** | Exactly 84 slots | 84 slots in `ground_truth_events.json` | **PASS** |
| **Medication Events** | Longitudinal log | 61 records in `medication_events.json` (56 taken, 2 missed, 2 started, 1 discontinued) | **PASS** |
| **Evidence Quote Veracity** | Verbatim matching | 209 / 209 quotes (100.0% exact case-sensitive match) | **PASS** |
| **Latent Leakage Prevention** | Zero latent leakage | 0 leaks detected across all vague and bounded reports | **PASS** |
| **Held-Out Symptom Isolation** | 0 in Dev, present in Eval | 0 in Dev; 17 instances in Eval (`SYN-PT-103`) | **PASS** |
| **Source Data Preservation** | Untouched | All 5 files in `extracted_demo_data/` remain untouched | **PASS** |

---

## 2. Detailed Technical & Clinical Reconciliations

### 2.1 Timeline, Relative Dates & Timezones
* **Fixed Anchor**: 2026-10-05 to 2026-11-01.
* **Relative Date Resolution Policy**: Relative expressions (e.g., *"yesterday was brutal"*, *"threw up twice in the evening"*) resolve against the patient's local `submission_timestamp` offset, rather than an ungrounded `covers_date`.
* **Missing Check-In vs Absence**: Missing days are explicitly represented in `schedule_slots.json` (`submission_status: "missing"`). Check-ins on subsequent days (e.g. Day 13 after missing Day 12) correctly use `temporal_anchor: "yesterday"` to ground past symptoms without attributing them to the current day.

### 2.2 Episode Counting & Partial-Day Policy
Per architecture consensus between Opus and Codex:
1. **Explicit Partial-Day Counts**: A sole explicit single-day episode count (e.g., *"threw up twice after dinner"*) contributes 2 documented episodes to the observation record; it is not claimed as an exhaustive total for the entire calendar day.
2. **Deduplication Policy**: Multiple same-day claims are deduplicated only when they represent equal explicit full-day totals. Heterogeneous claims (e.g., partial + partial, or partial + full) remain separate or flagged as unresolved rather than naively summed.
3. **Multi-Day & Vague Counts**: Expressions spanning multiple days or using colloquial quantifiers are never assigned synthetic sums.
4. **Vague Quantifiers (Resolved in v1.1.0)**: Colloquial phrases (*"a couple times"*, *"multiple times"*, *"a few times"*) carry `exact_count: null`, `count_bounds: null`, and `is_unquantified_count: true`, preventing false precision.

### 2.3 Partial-Day Absence vs Symptom-Day Presence
* **Symptom Presence Rule**: Symptom presence on a calendar day signifies that the symptom occurred at any time during that 24-hour period.
* **Absence Scope Rule**: Partial-day absence statements (e.g., *"no nausea tonight"*) do not negate daytime presence (e.g., nausea experienced earlier in the morning). Gold labels accurately scope partial-day negations without falsely marking the whole day as absent.

### 2.4 Evidence Grounding: Text vs Questionnaire
* Text extractions are grounded in verbatim `evidence_quote` (209/209 verified 100% exact match).
* Questionnaire values (such as numeric scores for pain, nausea, fatigue) are grounded in explicit structured keys (`questionnaire_responses.reported_*`) rather than text quotes.

### 2.5 Medication Regimen & Non-Adherence
* **Regimen Fixture**: Tracks scheduled cisplatin infusions, antiemetics (ondansetron, dexamethasone, prochlorperazine, aprepitant, lorazepam), and mouth rinses.
* **Escalation Event**: `SYN-PT-102` Day 17 discontinuation of prochlorperazine and initiation of aprepitant + ondansetron for refractory CINV.
* **Non-Adherence Events (Resolved in v1.1.0)**: `medication_events.json` now includes both scheduled administrations and patient-reported missed doses (`MED-SYN-PT-102-D15-0060` for mouth rinse; `MED-SYN-PT-102-D19-0061` for ondansetron).

### 2.6 Held-Out Evaluation Set Isolation
* Development Split (`SYN-PT-101`, `SYN-PT-102`): 52 reports, 4 missing slots.
* Evaluation Split (`SYN-PT-103`): 26 reports, 2 missing slots.
* Held-Out Classes: `tinnitus`, `singultus`, `peripheral_neuropathy` occur 17 times in `SYN-PT-103` and **0 times in Dev**.
* Open-world detection is not assumed; unmapped/held-out symptoms are treated as review obligations.

---

## 3. Resolution of QA Observations in v1.1.0

1. **Vague Quantifier Bounds**: Artificial integer bounds (`[2, 3]`, `[3, 6]`, `[3, 5]`) removed. All 3 vague count check-ins now correctly feature `exact_count: null`, `count_bounds: null`, and `is_unquantified_count: true`.
2. **Syncope Tagging**: In `CHK-SYN-PT-103-D19`, the colloquial intensifier *"actually passed out"* no longer carries a spurious double-counting correction flag (`correction_or_clarification: null`).
3. **Missed Medication Log**: `medication_events.json` expanded from 59 to 61 records, incorporating the 2 patient-reported missed doses.

---

## 4. Final Acceptance

**Status: FULLY ACCEPTED (Independent Agent QA Passed - v1.1.0 Final)**  
The dataset satisfies all requirements, provides 84 complete slots, 78 submitted check-in reports with 100% quote fidelity, strict eval-split isolation of held-out symptoms, zero latent truth leakage, and clean handling of medical non-adherence and clinical ambiguity. It is fully ready for Track B schema design, Pydantic parsing, SQLite storage, analytical queries, and clinician dashboard charting.
