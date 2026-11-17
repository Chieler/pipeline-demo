# Extraction checks and known limitations

These examples document the prototype's checks, not clinical accuracy. The local parser is a medspaCy/rules pipeline; optional API feedback is advisory.

Latest check: 28 tests pass (18 parser/database, seven verifier, three patient-view checks). Dependency consistency and Python compilation checks pass. The localhost health endpoint returns `ok`, and the grid/count chart were visually inspected in Chrome. No paid-model request was made. A follow-up regression fixes negation leaking from “No vomiting today” into the affirmative clause “nausea down to a 2”; coordinated negatives remain supported.

## Behavioral checks

Automated tests cover explicit negation, vague counts, ranges, numerical corrections, retrospective dates, questionnaire/text source separation, repeated imports, calendar coverage, and the two SQL analyses. API tests use mocked HTTP, including missing credentials, unsupported evidence, invalid JSON/schema, and API failure. A database check confirms that stored verification feedback does not change query results. Streamlit AppTest runs all three patient selections.

Manual probes caught two errors after the initial tests: “2–3 times” was interpreted as an exact 3, and “three times since Monday” was assigned to the submission day. Both received failing regression tests before correction. The range now stays non-exact; the multi-day count is retained but excluded from daily totals.

## Small held-out text-only check

The following patient SYN-PT-103 reports were inspected after implementation. No rules were added to recognize these held-out phrases. Questionnaire values were not credited as text extraction successes.

| Report | Visible text | Local extraction | Assessment |
|---|---|---|---|
| Day 1 | “Feeling fine, no pain, no nausea.” | Pain absent, nausea absent | Correct explicit negation in this example |
| Day 11 | Persistent ringing in both ears; “Vomited once this morning. Nausea at 5.” | Vomiting present, count 1; nausea present | Misses tinnitus and the unscaled nausea number; retains original text |
| Day 22 | Fingertips numb and prickly; “Nausea is down to 2.” | Nausea present | Misses neuropathy-like symptom phrase and unscaled nausea number; retains original text |

These failures show the vocabulary/attribute limits of the local baseline. They are not repaired by copying expected annotations or questionnaire answers into the text result. The optional verifier may identify missed claims when configured, but its benefit has not been established by a live paid-model evaluation.

The source dataset's annotations are agent-generated and independently agent-reviewed, not human-audited clinical ground truth. Evidence matching does not by itself establish that a symptom, count, time, or severity was interpreted correctly.

## Independent implementation review

### Text-only reference-label comparison (16 November 2026)

Re-ran the current local parser on each report's raw text, anchored to its submission date. Compared unique `(symptom, presence)` pairs within each report against symptom entities in `expected_annotations.json`. Repeated mentions of the same symptom/status within a report count once. Normalized reference `mucositis` to `mouth_sores` and `syncope` to `fainting`. Questionnaire values were not included. All reference symptoms were included, including those outside the parser vocabulary.

| Reports | Matched pairs | Extra pairs | Missed pairs | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| All 78 | 137 | 7 | 49 | 95.1% | 73.7% |
| Designated evaluation patient, SYN-PT-103 (26) | 39 | 2 | 27 | 95.1% | 59.1% |

These are symptom/status agreement figures, not end-to-end extraction accuracy: they do not score dates, counts, severity, evidence spans, or medication extraction. Extra pairs are disagreements with the reference, not adjudicated clinical errors. Reference labels are synthetic, agent-generated and agent-reviewed, not clinician-verified ground truth. The evaluation split is a small fixture, not an independent clinical validation cohort.

The evaluation patient's misses include 10 tinnitus, four peripheral-neuropathy, and three hiccup (`singultus`) pairs. In-vocabulary misses also remain. Local rules handle explicit dates such as “yesterday,” but this does not establish general language understanding. No live API comparison has established a verifier benefit.

An AGY agent reviewed the code and the runnable demonstration. Range-count precision and source conflicts were corrected during review. Its additional absence-zero and mixed-date examples received targeted regression checks. The review's claim that the default model name does not exist was rejected after checking the provider's official model documentation; no live API call was used to establish that claim. Exact case-sensitive evidence matching is intentional. Dynamic per-patient symptom lists are an accepted simplification. Compact formats such as “Vomiting: 0” remain outside the tested local language patterns.
