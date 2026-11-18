#!/usr/bin/env python3
"""
Synthetic Dataset Generator for Track B (Patient-Reported Data: Store, Manage & Chart)
Pipeline Securities Inc. Assessment Context

Enforces:
1. Ground-truth latent facts generated FIRST.
2. Check-in text and questionnaire drafted from latent facts SECOND.
3. Expected extraction labels generated THIRD (faithful to text/questionnaire, zero latent leakage).
4. Exactly 3 patients x 28 days = 84 slots (78 submitted, 6 missing).
5. Dev / Eval split with Eval-only held-out symptom classes (tinnitus, singultus, peripheral neuropathy).
"""

import json
from datetime import date, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
START_DATE = date(2026, 10, 5)  # Monday, Oct 5, 2026

# ==============================================================================
# 1. PATIENT MASTER DEFINITIONS
# ==============================================================================
PATIENTS = [
    {
        "patient_id": "SYN-PT-101",
        "split": "dev",
        "pseudonym": "David Chen",
        "age": 58,
        "sex": "M",
        "diagnosis": "Squamous cell carcinoma of right tonsil (cT2N1M0, HPV+)",
        "protocol": "Head & Neck: 33 fractions IMRT (66 Gy) + Weekly Cisplatin (40 mg/m²)",
        "chemo_day_of_week": "Thursday",
        "chemo_days": [4, 11, 18, 25],
        "missing_days": [12, 20],  # 2 missing slots
        "baseline_weight_lb": 178.0,
        "alert_weight_lb": 169.0,
        "medication_regimen": [
            {"drug": "Ondansetron", "dose": "8mg", "schedule": "Every 8 hours PRN nausea"},
            {"drug": "Dexamethasone", "dose": "4mg", "schedule": "Once daily on chemo day + 2 days post-chemo"},
            {"drug": "Salt and Soda Oral Rinse", "dose": "1 rinse", "schedule": "4 times daily"}
        ],
        "clinical_summary": "Tonsillar carcinoma undergoing chemoradiation. Compliant with antiemetics, experiences classic delayed CINV 2-4 days post-chemo, mild oral mucositis, moderate dehydration headache."
    },
    {
        "patient_id": "SYN-PT-102",
        "split": "dev",
        "pseudonym": "Maria Santos",
        "age": 49,
        "sex": "F",
        "diagnosis": "Squamous cell carcinoma of base of tongue (cT3N2bM0)",
        "protocol": "Head & Neck: 33 fractions IMRT (70 Gy) + Weekly Cisplatin (40 mg/m²)",
        "chemo_day_of_week": "Tuesday",
        "chemo_days": [2, 9, 16, 23],
        "missing_days": [7, 25],   # 2 missing slots
        "baseline_weight_lb": 142.0,
        "alert_weight_lb": 135.0,
        "medication_regimen": [
            {"drug": "Prochlorperazine", "dose": "10mg", "schedule": "Every 8 hours PRN nausea (discontinued Day 17)"},
            {"drug": "Aprepitant", "dose": "125mg D1, 80mg D2-3", "schedule": "Added Day 17 for refractory CINV"},
            {"drug": "Ondansetron", "dose": "8mg", "schedule": "Every 8 hours PRN added Day 17"},
            {"drug": "Lorazepam", "dose": "0.5mg", "schedule": "PRN anticipatory nausea"},
            {"drug": "Magic Mouthwash", "dose": "10mL", "schedule": "Swish and spit before meals"}
        ],
        "clinical_summary": "Base of tongue cancer with severe acute CINV, anticipatory nausea, and orthostatic dizziness. Regimen escalated on Day 17 with addition of NK1 receptor antagonist (aprepitant). Weight crosses 5% alert threshold by Week 4."
    },
    {
        "patient_id": "SYN-PT-103",
        "split": "eval",
        "pseudonym": "Robert Kowalski",
        "age": 64,
        "sex": "M",
        "diagnosis": "Squamous cell carcinoma of hypopharynx (cT3N1M0)",
        "protocol": "Head & Neck: 33 fractions IMRT (70 Gy) + Weekly Cisplatin (40 mg/m²)",
        "chemo_day_of_week": "Wednesday",
        "chemo_days": [3, 10, 17, 24],
        "missing_days": [15, 27],  # 2 missing slots
        "baseline_weight_lb": 195.0,
        "alert_weight_lb": 185.0,
        "medication_regimen": [
            {"drug": "Ondansetron ODT", "dose": "8mg", "schedule": "Every 8 hours PRN nausea"},
            {"drug": "Metoclopramide", "dose": "10mg", "schedule": "Before meals PRN nausea/delayed gastric emptying"}
        ],
        "clinical_summary": "Hypopharyngeal cancer in eval split. Stoic patient using colloquial terminology. Manifests held-out symptom classes: cisplatin ototoxicity (tinnitus), steroid-induced singultus (hiccups), cumulative peripheral neuropathy, along with syncope."
    }
]

# Helper to format dates
def get_date(day_num: int) -> str:
    return (START_DATE + timedelta(days=day_num - 1)).isoformat()

# ==============================================================================
# 2. RAW CLINICAL AUTHORING DATA (LATENT FACTS, TEXT, AND EXPECTED LABELS)
# ==============================================================================
# We define raw slot specs for all 84 slots.

RAW_SLOTS = []

# --- PATIENT 101 (Dev) ---
pt101_days = [
    # Day 1: Baseline
    (1, True, 178.0, 0, 0, "Solids",
     "First radiation session today. Everything went smoothly. No nausea, no pain, ate normal meals.",
     {"nausea": 0, "vomit": 0, "pain": 0, "fatigue": 1},
     [("symptom", "nausea", "No nausea", "present", None, 0, None, "No nausea, no pain, ate normal meals.", "absent"),
      ("symptom", "pain", "no pain", "present", None, None, None, "No nausea, no pain, ate normal meals.", "absent")],
     [("Salt and Soda Oral Rinse", "1 rinse", "taken", "Routine aftercare")]),
    
    # Day 2: Mild fatigue
    (2, True, 177.8, 0, 0, "Solids",
     "Day 2 done. Feeling slightly tired this afternoon, but throat is fine and appetite is good. No nausea.",
     {"nausea": 0, "vomit": 0, "pain": 1, "fatigue": 2},
     [("symptom", "fatigue", "slightly tired", "present", {"value": 2, "scale": "0-10"}, None, None, "Feeling slightly tired this afternoon", "present"),
      ("symptom", "nausea", "No nausea", "present", None, 0, None, "No nausea.", "absent")],
     [("Salt and Soda Oral Rinse", "1 rinse", "taken", "Routine aftercare")]),
    
    # Day 3: Pre-chemo anxiety
    (3, True, 177.6, 0, 0, "Solids",
     "A bit nervous about tomorrow's chemo infusion. My throat feels a little scratchy, but no sickness or stomach upset.",
     {"nausea": 0, "vomit": 0, "pain": 1, "fatigue": 2},
     [("symptom", "mucositis", "throat feels a little scratchy", "present", {"value": 1, "scale": "0-4"}, None, None, "throat feels a little scratchy", "present"),
      ("symptom", "nausea", "no sickness or stomach upset", "present", None, 0, None, "no sickness or stomach upset.", "absent")],
     []),
    
    # Day 4: Chemo 1 - Acute nausea
    (4, True, 177.2, 3, 0, "Soft food",
     "Finished first cisplatin dose this morning. Around dinner I started feeling queasy, nausea maybe a 3 out of 10. Took my ondansetron 8mg.",
     {"nausea": 3, "vomit": 0, "pain": 2, "fatigue": 4},
     [("symptom", "nausea", "feeling queasy, nausea maybe a 3 out of 10", "today_earlier", {"value": 3, "scale": "0-10"}, None, None, "Around dinner I started feeling queasy, nausea maybe a 3 out of 10.", "present"),
      ("medication_event", "Ondansetron", "Took my ondansetron 8mg", "today_earlier", None, None, None, "Took my ondansetron 8mg.", "taken")],
     [("Cisplatin", "40mg/m2", "taken", "Infusion completed in clinic"),
      ("Dexamethasone", "4mg", "taken", "Pre-medication and evening dose"),
      ("Ondansetron", "8mg", "taken", "Taken for acute post-infusion nausea")]),
    
    # Day 5: Delayed nausea begins
    (5, True, 176.5, 5, 0, "Soft food",
     "Woke up with lingering nausea, roughly 5 out of 10. Cooking smells really bothered me. Managed oatmeal and took my morning steroid and anti-nausea pill.",
     {"nausea": 5, "vomit": 0, "pain": 2, "fatigue": 5},
     [("symptom", "nausea", "lingering nausea, roughly 5 out of 10", "current", {"value": 5, "scale": "0-10"}, None, None, "Woke up with lingering nausea, roughly 5 out of 10.", "present"),
      ("medication_event", "Dexamethasone", "took my morning steroid", "current", None, None, None, "took my morning steroid and anti-nausea pill.", "taken"),
      ("medication_event", "Ondansetron", "anti-nausea pill", "current", None, None, None, "took my morning steroid and anti-nausea pill.", "taken")],
     [("Dexamethasone", "4mg", "taken", "Day 1 post-chemo"),
      ("Ondansetron", "8mg", "taken", "Morning dose for delayed nausea")]),
    
    # Day 6: Peak delayed nausea with single vomit
    (6, True, 175.9, 6, 1, "Liquids only",
     "Toughest day so far. Threw up once around 2pm after trying to drink a protein shake. Nausea was at a 6. Throat is tender.",
     {"nausea": 6, "vomit": 1, "pain": 3, "fatigue": 6},
     [("symptom", "vomiting", "Threw up once around 2pm", "today_earlier", None, 1, None, "Threw up once around 2pm after trying to drink a protein shake.", "present"),
      ("symptom", "nausea", "Nausea was at a 6", "today_earlier", {"value": 6, "scale": "0-10"}, None, None, "Nausea was at a 6.", "present"),
      ("symptom", "mucositis", "Throat is tender", "current", {"value": 1, "scale": "0-4"}, None, None, "Throat is tender.", "present")],
     [("Dexamethasone", "4mg", "taken", "Day 2 post-chemo"),
      ("Ondansetron", "8mg", "taken", "Taken following emesis episode")]),
    
    # Day 7: Easing
    (7, True, 176.0, 3, 0, "Soft food",
     "Feeling much better today. Nausea is down to a 3 and haven't vomited. Still quite exhausted, rested on couch most of the day.",
     {"nausea": 3, "vomit": 0, "pain": 2, "fatigue": 5},
     [("symptom", "nausea", "Nausea is down to a 3", "current", {"value": 3, "scale": "0-10"}, None, None, "Nausea is down to a 3 and haven't vomited.", "present"),
      ("symptom", "vomiting", "haven't vomited", "current", None, 0, None, "haven't vomited.", "absent"),
      ("symptom", "fatigue", "quite exhausted", "current", {"value": 5, "scale": "0-10"}, None, None, "Still quite exhausted", "present")],
     [("Ondansetron", "8mg", "taken", "PRN dose midday")]),
    
    # Day 8: Nausea resolved
    (8, True, 176.4, 1, 0, "Soft food",
     "Nausea has basically cleared up. Mouth feels dry though, and throat has some mild burning when swallowing eggs.",
     {"nausea": 1, "vomit": 0, "pain": 3, "fatigue": 4},
     [("symptom", "nausea", "Nausea has basically cleared up", "current", {"value": 1, "scale": "0-10"}, None, None, "Nausea has basically cleared up.", "present"),
      ("symptom", "dry_mouth", "Mouth feels dry", "current", None, None, None, "Mouth feels dry though", "present"),
      ("symptom", "mucositis", "mild burning when swallowing", "current", {"value": 1, "scale": "0-4"}, None, None, "throat has some mild burning when swallowing eggs.", "present")],
     [("Salt and Soda Oral Rinse", "1 rinse", "taken", "4 rinses completed")]),
    
    # Day 9: Explicit negation
    (9, True, 176.5, 0, 0, "Soft food",
     "Radiation session 7 done. No nausea or vomiting today. Just tired and my throat is a little raw.",
     {"nausea": 0, "vomit": 0, "pain": 3, "fatigue": 3},
     [("symptom", "nausea", "No nausea", "current", None, 0, None, "No nausea or vomiting today.", "absent"),
      ("symptom", "vomiting", "or vomiting", "current", None, 0, None, "No nausea or vomiting today.", "absent"),
      ("symptom", "fatigue", "tired", "current", None, None, None, "Just tired", "present"),
      ("symptom", "mucositis", "throat is a little raw", "current", {"value": 1, "scale": "0-4"}, None, None, "throat is a little raw.", "present")],
     []),
    
    # Day 10: Pre-chemo hydration
    (10, True, 176.2, 0, 0, "Soft food",
     "Drank 2.5 liters of water to prep for tomorrow's chemo. Stomach feels fine, throat discomfort is manageable at 2/10.",
     {"nausea": 0, "vomit": 0, "pain": 2, "fatigue": 3},
     [("symptom", "nausea", "Stomach feels fine", "current", None, 0, None, "Stomach feels fine", "absent"),
      ("symptom", "pain", "throat discomfort is manageable at 2/10", "current", {"value": 2, "scale": "0-10"}, None, None, "throat discomfort is manageable at 2/10.", "present")],
     []),
    
    # Day 11: Chemo 2
    (11, True, 175.5, 4, 0, "Soft food",
     "Second cisplatin infusion completed. Started feeling nauseous during the drive home, about a 4. Also got a dull headache.",
     {"nausea": 4, "vomit": 0, "pain": 3, "fatigue": 5},
     [("symptom", "nausea", "feeling nauseous during the drive home, about a 4", "today_earlier", {"value": 4, "scale": "0-10"}, None, None, "Started feeling nauseous during the drive home, about a 4.", "present"),
      ("symptom", "headache", "dull headache", "today_earlier", None, None, None, "Also got a dull headache.", "present")],
     [("Cisplatin", "40mg/m2", "taken", "Second infusion"),
      ("Dexamethasone", "4mg", "taken", "Chemo day steroid"),
      ("Ondansetron", "8mg", "taken", "Post-infusion dose")]),
    
    # Day 12: MISSING
    (12, False, 174.5, 7, 2, "Liquids only", "", {}, [], []),
    
    # Day 13: Retrospective mixed time window
    (13, True, 174.2, 4, 0, "Liquids only",
     "Sorry I missed logging yesterday. Yesterday was brutal, threw up twice in the evening. Today the nausea is somewhat better, down to a 4, but swallowing hurts.",
     {"nausea": 4, "vomit": 0, "pain": 4, "fatigue": 6},
     [("symptom", "vomiting", "threw up twice in the evening", "yesterday", None, 2, None, "Yesterday was brutal, threw up twice in the evening.", "present"),
      ("symptom", "nausea", "nausea is somewhat better, down to a 4", "current", {"value": 4, "scale": "0-10"}, None, None, "Today the nausea is somewhat better, down to a 4", "present"),
      ("symptom", "dysphagia", "swallowing hurts", "current", {"value": 2, "scale": "0-4"}, None, None, "but swallowing hurts.", "present")],
     [("Dexamethasone", "4mg", "taken", "Post-chemo day 2"),
      ("Ondansetron", "8mg", "taken", "Taken twice today")]),
    
    # Day 14: Vague count & orthostatic dizziness
    (14, True, 173.8, 5, 2, "Liquids only",
     "Felt queasy all morning and threw up a couple times after taking my pills. Got really dizzy when I stood up from the bed.",
     {"nausea": 5, "vomit": 2, "pain": 4, "fatigue": 6},
     [("symptom", "nausea", "Felt queasy all morning", "today_earlier", {"value": 5, "scale": "0-10"}, None, None, "Felt queasy all morning", "present"),
      ("symptom", "vomiting", "threw up a couple times", "today_earlier", None, None, None, "threw up a couple times after taking my pills.", "present"),
      ("symptom", "dizziness", "really dizzy when I stood up from the bed", "today_earlier", None, None, None, "Got really dizzy when I stood up from the bed.", "present")],
     [("Ondansetron", "8mg", "taken", "Morning dose regurgitated, retaken 1 hr later")]),
    
    # Day 15: Throat worsens
    (15, True, 173.5, 2, 0, "Soft food",
     "Nausea has mostly settled, only about 2/10. But my throat has actual mouth sores now, looks like white patches. Pain is 5/10 when swallowing.",
     {"nausea": 2, "vomit": 0, "pain": 5, "fatigue": 5},
     [("symptom", "nausea", "Nausea has mostly settled, only about 2/10", "current", {"value": 2, "scale": "0-10"}, None, None, "Nausea has mostly settled, only about 2/10.", "present"),
      ("symptom", "mucositis", "actual mouth sores now, looks like white patches", "current", {"value": 2, "scale": "0-4"}, None, None, "throat has actual mouth sores now, looks like white patches.", "present"),
      ("symptom", "pain", "Pain is 5/10 when swallowing", "current", {"value": 5, "scale": "0-10"}, None, None, "Pain is 5/10 when swallowing.", "present")],
     [("Salt and Soda Oral Rinse", "1 rinse", "taken", "Rinsing 5 times today")]),
    
    # Day 16: Breathlessness on exertion
    (16, True, 173.0, 1, 0, "Soft food",
     "No nausea today. Felt noticeably short of breath when walking up the flight of stairs to my bedroom. Had to stop and catch my breath.",
     {"nausea": 1, "vomit": 0, "pain": 5, "fatigue": 6},
     [("symptom", "nausea", "No nausea today", "current", None, 0, None, "No nausea today.", "absent"),
      ("symptom", "breathlessness", "noticeably short of breath when walking up the flight of stairs", "today_earlier", None, None, None, "Felt noticeably short of breath when walking up the flight of stairs to my bedroom.", "present")],
     []),
    
    # Day 17: Pre-chemo check
    (17, True, 172.6, 2, 0, "Soft food",
     "Radiation session 13 complete. A little anticipatory queasiness thinking about chemo tomorrow. Mouth sores are uncomfortable, using the rinse constantly.",
     {"nausea": 2, "vomit": 0, "pain": 5, "fatigue": 5},
     [("symptom", "nausea", "anticipatory queasiness", "current", {"value": 2, "scale": "0-10"}, None, None, "A little anticipatory queasiness thinking about chemo tomorrow.", "present"),
      ("symptom", "mucositis", "Mouth sores are uncomfortable", "current", {"value": 2, "scale": "0-4"}, None, None, "Mouth sores are uncomfortable", "present")],
     []),
    
    # Day 18: Chemo 3 - Severe acute vomiting
    (18, True, 172.0, 7, 3, "Liquids only",
     "Third chemo session today. Very rough afternoon. Vomited 3 times between 3pm and 7pm, pure bile. Nausea is at least a 7. Took 2 doses of ondansetron.",
     {"nausea": 7, "vomit": 3, "pain": 5, "fatigue": 7},
     [("symptom", "vomiting", "Vomited 3 times between 3pm and 7pm", "today_earlier", None, 3, None, "Vomited 3 times between 3pm and 7pm, pure bile.", "present"),
      ("symptom", "nausea", "Nausea is at least a 7", "current", {"value": 7, "scale": "0-10"}, None, None, "Nausea is at least a 7.", "present"),
      ("medication_event", "Ondansetron", "Took 2 doses of ondansetron", "today_earlier", None, None, None, "Took 2 doses of ondansetron.", "taken")],
     [("Cisplatin", "40mg/m2", "taken", "Third infusion completed"),
      ("Dexamethasone", "4mg", "taken", "Chemo premedication"),
      ("Ondansetron", "16mg", "taken", "8mg at 3:30pm and 8mg at 8:00pm")]),
    
    # Day 19: Severe fatigue and headache
    (19, True, 171.2, 6, 2, "Liquids only",
     "Struggling today. Threw up twice this morning. Blinding headache from dehydration, and fatigue is an 8 out of 10. Could barely get out of bed.",
     {"nausea": 6, "vomit": 2, "pain": 6, "fatigue": 8},
     [("symptom", "vomiting", "Threw up twice this morning", "today_earlier", None, 2, None, "Threw up twice this morning.", "present"),
      ("symptom", "headache", "Blinding headache from dehydration", "current", {"value": 7, "scale": "0-10"}, None, None, "Blinding headache from dehydration", "present"),
      ("symptom", "fatigue", "fatigue is an 8 out of 10", "current", {"value": 8, "scale": "0-10"}, None, None, "fatigue is an 8 out of 10.", "present")],
     [("Dexamethasone", "4mg", "taken", "Post-chemo Day 1"),
      ("Ondansetron", "8mg", "taken", "Morning and afternoon doses")]),
    
    # Day 20: MISSING
    (20, False, 170.8, 5, 1, "Liquids only", "", {}, [], []),
    
    # Day 21: Text vs Questionnaire Conflict
    (21, True, 170.5, 3, 0, "Liquids only",
     "Still feeling slightly queasy in the morning, but forced down some lukewarm broth. Throat is raw, pain 6/10.",
     {"nausea": 0, "vomit": 0, "pain": 6, "fatigue": 6},  # Questionnaire says Nausea 0!
     [("symptom", "nausea", "Still feeling slightly queasy in the morning", "current", {"value": 3, "scale": "0-10"}, None, None, "Still feeling slightly queasy in the morning", "present"),
      ("symptom", "pain", "Throat is raw, pain 6/10", "current", {"value": 6, "scale": "0-10"}, None, None, "Throat is raw, pain 6/10.", "present")],
     [("Salt and Soda Oral Rinse", "1 rinse", "taken", "Oral hygiene maintained")]),
    
    # Day 22: Persistent throat soreness
    (22, True, 170.8, 2, 0, "Soft food",
     "Nausea is down to 2 today. Mouth sores are painful, especially on the right side of tongue. Taking small sips of nutritional shakes.",
     {"nausea": 2, "vomit": 0, "pain": 6, "fatigue": 5},
     [("symptom", "nausea", "Nausea is down to 2 today", "current", {"value": 2, "scale": "0-10"}, None, None, "Nausea is down to 2 today.", "present"),
      ("symptom", "mucositis", "Mouth sores are painful, especially on the right side of tongue", "current", {"value": 2, "scale": "0-4"}, None, None, "Mouth sores are painful, especially on the right side of tongue.", "present")],
     []),
    
    # Day 23: Mild dizziness
    (23, True, 170.4, 1, 0, "Soft food",
     "Felt slightly lightheaded when showering. No vomiting, nausea is almost gone. Throat continues to burn.",
     {"nausea": 1, "vomit": 0, "pain": 6, "fatigue": 5},
     [("symptom", "dizziness", "slightly lightheaded when showering", "today_earlier", None, None, None, "Felt slightly lightheaded when showering.", "present"),
      ("symptom", "vomiting", "No vomiting", "current", None, 0, None, "No vomiting, nausea is almost gone.", "absent"),
      ("symptom", "nausea", "nausea is almost gone", "current", {"value": 1, "scale": "0-10"}, None, None, "nausea is almost gone.", "present")],
     []),
    
    # Day 24: Pre-chemo
    (24, True, 170.2, 2, 0, "Soft food",
     "Pre-chemo appointment today. Throat pain at 5/10. Drank 2 liters of fluid. No throwing up.",
     {"nausea": 2, "vomit": 0, "pain": 5, "fatigue": 4},
     [("symptom", "pain", "Throat pain at 5/10", "current", {"value": 5, "scale": "0-10"}, None, None, "Throat pain at 5/10.", "present"),
      ("symptom", "vomiting", "No throwing up", "current", None, 0, None, "No throwing up.", "absent")],
     []),
    
    # Day 25: Chemo 4 - Uncertain medication name
    (25, True, 169.8, 5, 0, "Liquids only",
     "Chemo #4 completed. Took the little white nausea tablet with breakfast and the steroid. Felt moderate waves of nausea around 4pm, about a 5.",
     {"nausea": 5, "vomit": 0, "pain": 5, "fatigue": 6},
     [("medication_event", "Ondansetron", "little white nausea tablet", "today_earlier", None, None, None, "Took the little white nausea tablet with breakfast", "taken"),
      ("medication_event", "Dexamethasone", "the steroid", "today_earlier", None, None, None, "and the steroid.", "taken"),
      ("symptom", "nausea", "moderate waves of nausea around 4pm, about a 5", "today_earlier", {"value": 5, "scale": "0-10"}, None, None, "Felt moderate waves of nausea around 4pm, about a 5.", "present")],
     [("Cisplatin", "40mg/m2", "taken", "Fourth infusion"),
      ("Dexamethasone", "4mg", "taken", "Chemo day dose"),
      ("Ondansetron", "8mg", "taken", "Morning premedication")]),
    
    # Day 26: Correction / overlap example
    (26, True, 169.2, 6, 3, "Liquids only",
     "Rough morning. Threw up twice this morning... wait, actually three times if you count the dry heaves right after breakfast. Nausea at 6.",
     {"nausea": 6, "vomit": 3, "pain": 6, "fatigue": 7},
     [("symptom", "vomiting", "actually three times if you count the dry heaves", "today_earlier", None, 3, None, "Threw up twice this morning... wait, actually three times if you count the dry heaves right after breakfast.", "present"),
      ("symptom", "nausea", "Nausea at 6", "current", {"value": 6, "scale": "0-10"}, None, None, "Nausea at 6.", "present")],
     [("Dexamethasone", "4mg", "taken", "Post-chemo Day 1"),
      ("Ondansetron", "8mg", "taken", "Morning dose")]),
    
    # Day 27: Persistent delayed nausea
    (27, True, 169.0, 4, 0, "Liquids only",
     "No vomiting today, but constant low-grade nausea at 4/10. Throat pain is intense when trying to swallow saliva. Fatigue at 7.",
     {"nausea": 4, "vomit": 0, "pain": 7, "fatigue": 7},
     [("symptom", "vomiting", "No vomiting today", "current", None, 0, None, "No vomiting today", "absent"),
      ("symptom", "nausea", "constant low-grade nausea at 4/10", "current", {"value": 4, "scale": "0-10"}, None, None, "constant low-grade nausea at 4/10.", "present"),
      ("symptom", "pain", "Throat pain is intense when trying to swallow saliva", "current", {"value": 7, "scale": "0-10"}, None, None, "Throat pain is intense when trying to swallow saliva.", "present"),
      ("symptom", "fatigue", "Fatigue at 7", "current", {"value": 7, "scale": "0-10"}, None, None, "Fatigue at 7.", "present")],
     [("Dexamethasone", "4mg", "taken", "Post-chemo Day 2")]),
    
    # Day 28: Easing, weight near alert line
    (28, True, 168.8, 2, 0, "Soft food",
     "Week 4 finished. Nausea down to 2. Weight is 168.8 lbs, so down about 9 lbs since start. Clinic told me to monitor closely. No vomiting.",
     {"nausea": 2, "vomit": 0, "pain": 6, "fatigue": 6},
     [("symptom", "nausea", "Nausea down to 2", "current", {"value": 2, "scale": "0-10"}, None, None, "Nausea down to 2.", "present"),
      ("vital", "weight", "Weight is 168.8 lbs", "current", {"value": 168.8, "unit": "lbs"}, None, None, "Weight is 168.8 lbs", "present"),
      ("symptom", "vomiting", "No vomiting", "current", None, 0, None, "No vomiting.", "absent")],
     [])
]
RAW_SLOTS.append(("SYN-PT-101", pt101_days))

# --- PATIENT 102 (Dev - Maria Santos, severe CINV, regimen switch Day 17) ---
pt102_days = [
    # Day 1: Baseline anticipatory nausea
    (1, True, 142.0, 3, 0, "Solids",
     "Starting radiation today. Feeling butterflies and a bit sick to my stomach just thinking about chemo tomorrow. No vomiting.",
     {"nausea": 3, "vomit": 0, "pain": 0, "fatigue": 2},
     [("symptom", "nausea", "bit sick to my stomach", "current", {"value": 3, "scale": "0-10"}, None, None, "Feeling butterflies and a bit sick to my stomach", "present"),
      ("symptom", "vomiting", "No vomiting", "current", None, 0, None, "No vomiting.", "absent")],
     []),
    
    # Day 2: Chemo 1 - Acute vomiting
    (2, True, 141.2, 6, 2, "Soft food",
     "First cisplatin infusion. Threw up twice in the clinic parking lot after discharge. Took prochlorperazine 10mg when I got home.",
     {"nausea": 6, "vomit": 2, "pain": 1, "fatigue": 5},
     [("symptom", "vomiting", "Threw up twice in the clinic parking lot", "today_earlier", None, 2, None, "Threw up twice in the clinic parking lot after discharge.", "present"),
      ("medication_event", "Prochlorperazine", "Took prochlorperazine 10mg", "today_earlier", None, None, None, "Took prochlorperazine 10mg when I got home.", "taken")],
     [("Cisplatin", "40mg/m2", "taken", "First infusion"),
      ("Prochlorperazine", "10mg", "taken", "Post-discharge dose")]),
    
    # Day 3: Delayed nausea
    (3, True, 140.5, 7, 3, "Liquids only",
     "Nausea was relentless today, rating it a 7. Vomited 3 times, couldn't keep dinner down. Extreme fatigue.",
     {"nausea": 7, "vomit": 3, "pain": 2, "fatigue": 7},
     [("symptom", "nausea", "Nausea was relentless today, rating it a 7", "current", {"value": 7, "scale": "0-10"}, None, None, "Nausea was relentless today, rating it a 7.", "present"),
      ("symptom", "vomiting", "Vomited 3 times", "today_earlier", None, 3, None, "Vomited 3 times, couldn't keep dinner down.", "present"),
      ("symptom", "fatigue", "Extreme fatigue", "current", {"value": 7, "scale": "0-10"}, None, None, "Extreme fatigue.", "present")],
     [("Prochlorperazine", "10mg", "taken", "Three doses taken")]),
    
    # Day 4: Explicit negation
    (4, True, 140.8, 2, 0, "Soft food",
     "Much calmer today. No vomiting today, nausea down to a 2, managed tea and toast without issues.",
     {"nausea": 2, "vomit": 0, "pain": 2, "fatigue": 4},
     [("symptom", "vomiting", "No vomiting today", "current", None, 0, None, "No vomiting today", "absent"),
      ("symptom", "nausea", "nausea down to a 2", "current", {"value": 2, "scale": "0-10"}, None, None, "nausea down to a 2", "present")],
     []),
    
    # Day 5: Dizziness / orthostasis
    (5, True, 140.6, 2, 0, "Soft food",
     "Got dizzy when getting out of bed this morning, the whole room swayed for a minute. Sat back down and it passed. No sickness.",
     {"nausea": 2, "vomit": 0, "pain": 2, "fatigue": 5},
     [("symptom", "dizziness", "Got dizzy when getting out of bed this morning, the whole room swayed", "today_earlier", None, None, None, "Got dizzy when getting out of bed this morning, the whole room swayed for a minute.", "present"),
      ("symptom", "nausea", "No sickness", "current", None, 0, None, "No sickness.", "absent")],
     []),
    
    # Day 6: Mild dryness
    (6, True, 140.2, 1, 0, "Soft food",
     "Mouth is getting sticky and dry. Mild sore throat. No nausea or vomiting today.",
     {"nausea": 1, "vomit": 0, "pain": 3, "fatigue": 4},
     [("symptom", "dry_mouth", "Mouth is getting sticky and dry", "current", None, None, None, "Mouth is getting sticky and dry.", "present"),
      ("symptom", "mucositis", "Mild sore throat", "current", {"value": 1, "scale": "0-4"}, None, None, "Mild sore throat.", "present"),
      ("symptom", "nausea", "No nausea or vomiting today", "current", None, 0, None, "No nausea or vomiting today.", "absent"),
      ("symptom", "vomiting", "or vomiting", "current", None, 0, None, "No nausea or vomiting today.", "absent")],
     []),
    
    # Day 7: MISSING
    (7, False, 139.8, 4, 0, "Soft food", "", {}, [], []),
    
    # Day 8: Anticipatory nausea
    (8, True, 139.5, 5, 0, "Soft food",
     "Severe stomach churning anticipating tomorrow's chemo. Took lorazepam 0.5mg to calm the anticipatory nausea. No throwing up yet.",
     {"nausea": 5, "vomit": 0, "pain": 3, "fatigue": 5},
     [("symptom", "nausea", "Severe stomach churning anticipating tomorrow's chemo", "current", {"value": 5, "scale": "0-10"}, None, None, "Severe stomach churning anticipating tomorrow's chemo.", "present"),
      ("medication_event", "Lorazepam", "Took lorazepam 0.5mg", "current", None, None, None, "Took lorazepam 0.5mg to calm the anticipatory nausea.", "taken"),
      ("symptom", "vomiting", "No throwing up yet", "current", None, 0, None, "No throwing up yet.", "absent")],
     [("Lorazepam", "0.5mg", "taken", "Anticipatory nausea PRN")]),
    
    # Day 9: Chemo 2 - Severe emesis
    (9, True, 138.8, 8, 4, "Liquids only",
     "Horrible day with chemo #2. Vomited 4 times between clinic and home. Even water comes back up. Nausea is an 8. Prochlorperazine is not touching this.",
     {"nausea": 8, "vomit": 4, "pain": 3, "fatigue": 8},
     [("symptom", "vomiting", "Vomited 4 times between clinic and home", "today_earlier", None, 4, None, "Vomited 4 times between clinic and home.", "present"),
      ("symptom", "nausea", "Nausea is an 8", "current", {"value": 8, "scale": "0-10"}, None, None, "Nausea is an 8.", "present")],
     [("Cisplatin", "40mg/m2", "taken", "Infusion #2"),
      ("Prochlorperazine", "10mg", "taken", "Ineffective for breakthrough emesis")]),
    
    # Day 10: Vague count
    (10, True, 138.0, 7, 3, "Liquids only",
     "Still retching. Heaved multiple times throughout the night. Feel completely depleted and dizzy.",
     {"nausea": 7, "vomit": 3, "pain": 4, "fatigue": 8},
     [("symptom", "vomiting", "Heaved multiple times throughout the night", "today_earlier", None, None, None, "Heaved multiple times throughout the night.", "present"),
      ("symptom", "dizziness", "Feel completely depleted and dizzy", "current", None, None, None, "Feel completely depleted and dizzy.", "present")],
     [("Prochlorperazine", "10mg", "taken", "Every 8 hours")]),
    
    # Day 11: Text vs Questionnaire Conflict
    (11, True, 137.5, 5, 1, "Liquids only",
     "My mouth and tongue feel like they're on fire today, can barely swallow water without screaming. Pain is 8/10 in reality.",
     {"nausea": 5, "vomit": 1, "pain": 2, "fatigue": 7},  # Questionnaire says pain 2!
     [("symptom", "mucositis", "mouth and tongue feel like they're on fire today", "current", {"value": 3, "scale": "0-4"}, None, None, "My mouth and tongue feel like they're on fire today", "present"),
      ("symptom", "dysphagia", "can barely swallow water", "current", {"value": 3, "scale": "0-4"}, None, None, "can barely swallow water without screaming.", "present"),
      ("symptom", "pain", "Pain is 8/10 in reality", "current", {"value": 8, "scale": "0-10"}, None, None, "Pain is 8/10 in reality.", "present")],
     [("Magic Mouthwash", "10mL", "taken", "Before attempting liquids")]),
    
    # Day 12: Dehydration headache
    (12, True, 137.0, 4, 1, "Liquids only",
     "Pounding dehydration headache all morning. Vomited once after drinking apple juice. Nausea is around a 4.",
     {"nausea": 4, "vomit": 1, "pain": 6, "fatigue": 7},
     [("symptom", "headache", "Pounding dehydration headache all morning", "today_earlier", {"value": 7, "scale": "0-10"}, None, None, "Pounding dehydration headache all morning.", "present"),
      ("symptom", "vomiting", "Vomited once after drinking apple juice", "today_earlier", None, 1, None, "Vomited once after drinking apple juice.", "present"),
      ("symptom", "nausea", "Nausea is around a 4", "current", {"value": 4, "scale": "0-10"}, None, None, "Nausea is around a 4.", "present")],
     []),
    
    # Day 13: Improving
    (13, True, 136.8, 3, 0, "Soft food",
     "Nausea easing down to a 3. No vomiting today. Used magic mouthwash 4 times and managed some lukewarm pudding.",
     {"nausea": 3, "vomit": 0, "pain": 5, "fatigue": 6},
     [("symptom", "nausea", "Nausea easing down to a 3", "current", {"value": 3, "scale": "0-10"}, None, None, "Nausea easing down to a 3.", "present"),
      ("symptom", "vomiting", "No vomiting today", "current", None, 0, None, "No vomiting today.", "absent"),
      ("medication_event", "Magic Mouthwash", "Used magic mouthwash 4 times", "current", None, None, None, "Used magic mouthwash 4 times", "taken")],
     []),
    
    # Day 14: Rest day
    (14, True, 136.5, 2, 0, "Soft food",
     "Resting. Throat is quite raw. Nausea is mild at 2, no vomiting. Feeling weak.",
     {"nausea": 2, "vomit": 0, "pain": 5, "fatigue": 5},
     [("symptom", "nausea", "Nausea is mild at 2", "current", {"value": 2, "scale": "0-10"}, None, None, "Nausea is mild at 2, no vomiting.", "present"),
      ("symptom", "vomiting", "no vomiting", "current", None, 0, None, "no vomiting.", "absent")],
     []),
    
    # Day 15: Missed dose event
    (15, True, 136.2, 4, 0, "Soft food",
     "Anxious about tomorrow. Fell asleep early and missed my evening mouth rinse dose. Woke up with severe mouth dryness.",
     {"nausea": 4, "vomit": 0, "pain": 5, "fatigue": 5},
     [("symptom", "nausea", "Anxious about tomorrow", "current", {"value": 4, "scale": "0-10"}, None, None, "Anxious about tomorrow.", "present"),
      ("medication_event", "Magic Mouthwash", "missed my evening mouth rinse dose", "today_earlier", None, None, None, "Fell asleep early and missed my evening mouth rinse dose.", "missed"),
      ("symptom", "dry_mouth", "severe mouth dryness", "current", None, None, None, "Woke up with severe mouth dryness.", "present")],
     [("Magic Mouthwash", "10mL", "missed", "Evening dose missed due to falling asleep")]),
    
    # Day 16: Chemo 3 - Near syncope / fainting
    (16, True, 135.5, 8, 3, "Liquids only",
     "Chemo #3 was disastrous. Vomited 3 times. When standing up in clinic, blackness closed in around my eyes and I nearly fainted, had to sit on the floor.",
     {"nausea": 8, "vomit": 3, "pain": 5, "fatigue": 8},
     [("symptom", "vomiting", "Vomited 3 times", "today_earlier", None, 3, None, "Vomited 3 times.", "present"),
      ("symptom", "syncope", "blackness closed in around my eyes and I nearly fainted", "today_earlier", None, None, None, "blackness closed in around my eyes and I nearly fainted, had to sit on the floor.", "present"),
      ("symptom", "nausea", "Chemo #3 was disastrous", "current", {"value": 8, "scale": "0-10"}, None, None, "Chemo #3 was disastrous.", "present")],
     [("Cisplatin", "40mg/m2", "taken", "Third infusion")]),
    
    # Day 17: MEDICATION SWITCH EVENT
    (17, True, 135.2, 5, 1, "Liquids only",
     "Doctor saw how much I was throwing up and switched my medicines today. Stopped prochlorperazine and started Emend (aprepitant) plus ondansetron 8mg. Vomited once earlier.",
     {"nausea": 5, "vomit": 1, "pain": 6, "fatigue": 7},
     [("medication_event", "Prochlorperazine", "Stopped prochlorperazine", "today_earlier", None, None, None, "Stopped prochlorperazine", "discontinued"),
      ("medication_event", "Aprepitant", "started Emend (aprepitant)", "today_earlier", None, None, None, "started Emend (aprepitant) plus ondansetron 8mg.", "started"),
      ("medication_event", "Ondansetron", "ondansetron 8mg", "today_earlier", None, None, None, "started Emend (aprepitant) plus ondansetron 8mg.", "started"),
      ("symptom", "vomiting", "Vomited once earlier", "today_earlier", None, 1, None, "Vomited once earlier.", "present")],
     [("Aprepitant", "125mg", "started", "New NK1 receptor antagonist started for refractory CINV"),
      ("Ondansetron", "8mg", "started", "New 5-HT3 antagonist added"),
      ("Prochlorperazine", "10mg", "discontinued", "Discontinued due to lack of efficacy")]),
    
    # Day 18: Response to new regimen
    (18, True, 135.0, 3, 0, "Soft food",
     "The new Emend regimen is working so much better! Nausea dropped down to a 3 and no vomiting at all today. First day I could eat soup peacefully.",
     {"nausea": 3, "vomit": 0, "pain": 5, "fatigue": 6},
     [("symptom", "nausea", "Nausea dropped down to a 3", "current", {"value": 3, "scale": "0-10"}, None, None, "Nausea dropped down to a 3", "present"),
      ("symptom", "vomiting", "no vomiting at all today", "current", None, 0, None, "no vomiting at all today.", "absent")],
     [("Aprepitant", "80mg", "taken", "Day 2 of 3-day aprepitant pack"),
      ("Ondansetron", "8mg", "taken", "Morning and evening doses")]),
    
    # Day 19: Missed dose event
    (19, True, 134.8, 4, 0, "Soft food",
     "Forgot my midday anti-nausea pill because I fell asleep for 4 hours. Felt some breakthrough nausea around 5pm, about a 4. Took it right away.",
     {"nausea": 4, "vomit": 0, "pain": 5, "fatigue": 6},
     [("medication_event", "Ondansetron", "Forgot my midday anti-nausea pill", "today_earlier", None, None, None, "Forgot my midday anti-nausea pill because I fell asleep for 4 hours.", "missed"),
      ("symptom", "nausea", "breakthrough nausea around 5pm, about a 4", "today_earlier", {"value": 4, "scale": "0-10"}, None, None, "Felt some breakthrough nausea around 5pm, about a 4.", "present")],
     [("Aprepitant", "80mg", "taken", "Day 3 of pack completed"),
      ("Ondansetron", "8mg", "missed", "Midday dose missed due to 4-hour nap")]),
    
    # Day 20: Stable
    (20, True, 134.8, 2, 0, "Soft food",
     "Nausea under control at 2. Mouth sores remain uncomfortable, using magic mouthwash before every meal. No sickness.",
     {"nausea": 2, "vomit": 0, "pain": 6, "fatigue": 5},
     [("symptom", "nausea", "Nausea under control at 2", "current", {"value": 2, "scale": "0-10"}, None, None, "Nausea under control at 2.", "present"),
      ("symptom", "mucositis", "Mouth sores remain uncomfortable", "current", {"value": 2, "scale": "0-4"}, None, None, "Mouth sores remain uncomfortable", "present"),
      ("symptom", "vomiting", "No sickness", "current", None, 0, None, "No sickness.", "absent")],
     []),
    
    # Day 21: Weight check
    (21, True, 134.6, 2, 0, "Soft food",
     "Weighed myself: 134.6 lbs. That's below 135 so I know the clinic flagged it. Swallowing is difficult but managing protein drinks. No vomiting.",
     {"nausea": 2, "vomit": 0, "pain": 6, "fatigue": 5},
     [("vital", "weight", "Weighed myself: 134.6 lbs", "current", {"value": 134.6, "unit": "lbs"}, None, None, "Weighed myself: 134.6 lbs.", "present"),
      ("symptom", "dysphagia", "Swallowing is difficult", "current", {"value": 2, "scale": "0-4"}, None, None, "Swallowing is difficult but managing protein drinks.", "present"),
      ("symptom", "vomiting", "No vomiting", "current", None, 0, None, "No vomiting.", "absent")],
     []),
    
    # Day 22: High mouth pain
    (22, True, 134.4, 3, 0, "Liquids only",
     "Throat pain is a 7 today, very hard to swallow. Nausea is mild at 3, took ondansetron. No throwing up.",
     {"nausea": 3, "vomit": 0, "pain": 7, "fatigue": 6},
     [("symptom", "pain", "Throat pain is a 7 today", "current", {"value": 7, "scale": "0-10"}, None, None, "Throat pain is a 7 today, very hard to swallow.", "present"),
      ("symptom", "nausea", "Nausea is mild at 3", "current", {"value": 3, "scale": "0-10"}, None, None, "Nausea is mild at 3", "present"),
      ("symptom", "vomiting", "No throwing up", "current", None, 0, None, "No throwing up.", "absent")],
     [("Ondansetron", "8mg", "taken", "Morning dose")]),
    
    # Day 23: Chemo 4 - Weight alert triggered!
    (23, True, 134.2, 5, 1, "Liquids only",
     "Chemo #4. Took Emend before treatment. Threw up once in the evening, but so much better than chemo 2. Weight is 134.2 lbs, clinic nutritionist talked to me.",
     {"nausea": 5, "vomit": 1, "pain": 6, "fatigue": 7},
     [("medication_event", "Aprepitant", "Took Emend before treatment", "today_earlier", None, None, None, "Took Emend before treatment.", "taken"),
      ("symptom", "vomiting", "Threw up once in the evening", "today_earlier", None, 1, None, "Threw up once in the evening", "present"),
      ("vital", "weight", "Weight is 134.2 lbs", "current", {"value": 134.2, "unit": "lbs"}, None, None, "Weight is 134.2 lbs", "present")],
     [("Cisplatin", "40mg/m2", "taken", "Infusion #4"),
      ("Aprepitant", "125mg", "taken", "Day 1 dose before chemo"),
      ("Ondansetron", "8mg", "taken", "Routine antiemetic")]),
    
    # Day 24: Post chemo
    (24, True, 134.0, 4, 0, "Liquids only",
     "Delayed nausea around a 4, no vomiting. Taking my Day 2 Emend capsule and ondansetron. Weak and lightheaded when standing.",
     {"nausea": 4, "vomit": 0, "pain": 6, "fatigue": 7},
     [("symptom", "nausea", "Delayed nausea around a 4", "current", {"value": 4, "scale": "0-10"}, None, None, "Delayed nausea around a 4, no vomiting.", "present"),
      ("symptom", "vomiting", "no vomiting", "current", None, 0, None, "no vomiting.", "absent"),
      ("symptom", "dizziness", "lightheaded when standing", "current", None, None, None, "Weak and lightheaded when standing.", "present")],
     [("Aprepitant", "80mg", "taken", "Day 2 dose")]),
    
    # Day 25: MISSING
    (25, False, 133.8, 4, 0, "Liquids only", "", {}, [], []),
    
    # Day 26: Retrospective
    (26, True, 133.7, 3, 0, "Liquids only",
     "Missed yesterday's check-in because I slept nearly all day. Nausea is at 3 today, throat is raw and painful. No vomiting.",
     {"nausea": 3, "vomit": 0, "pain": 7, "fatigue": 7},
     [("symptom", "nausea", "Nausea is at 3 today", "current", {"value": 3, "scale": "0-10"}, None, None, "Nausea is at 3 today", "present"),
      ("symptom", "pain", "throat is raw and painful", "current", {"value": 7, "scale": "0-10"}, None, None, "throat is raw and painful.", "present"),
      ("symptom", "vomiting", "No vomiting", "current", None, 0, None, "No vomiting.", "absent")],
     []),
    
    # Day 27: Explicit negation & uncertain headache
    (27, True, 133.5, 2, 0, "Liquids only",
     "No throwing up today. Nausea is down to a 2. Might have had a slight headache earlier, hard to tell with the neck pain.",
     {"nausea": 2, "vomit": 0, "pain": 6, "fatigue": 6},
     [("symptom", "vomiting", "No throwing up today", "current", None, 0, None, "No throwing up today.", "absent"),
      ("symptom", "nausea", "Nausea is down to a 2", "current", {"value": 2, "scale": "0-10"}, None, None, "Nausea is down to a 2.", "present"),
      ("symptom", "headache", "Might have had a slight headache earlier", "today_earlier", None, None, None, "Might have had a slight headache earlier, hard to tell", "uncertain")],
     []),
    
    # Day 28: Close of week 4
    (28, True, 133.6, 2, 0, "Liquids only",
     "End of week 4. Weight holding at 133.6 lbs. No vomiting. Throat pain is the main issue now, swallowing liquids only.",
     {"nausea": 2, "vomit": 0, "pain": 7, "fatigue": 6},
     [("vital", "weight", "Weight holding at 133.6 lbs", "current", {"value": 133.6, "unit": "lbs"}, None, None, "Weight holding at 133.6 lbs.", "present"),
      ("symptom", "vomiting", "No vomiting", "current", None, 0, None, "No vomiting.", "absent"),
      ("symptom", "pain", "Throat pain is the main issue now", "current", {"value": 7, "scale": "0-10"}, None, None, "Throat pain is the main issue now, swallowing liquids only.", "present")],
     [])
]
RAW_SLOTS.append(("SYN-PT-102", pt102_days))

# --- PATIENT 103 (Eval - Robert Kowalski, held-out symptoms: tinnitus, singultus, neuropathy) ---
pt103_days = [
    # Day 1: Baseline
    (1, True, 195.0, 0, 0, "Solids",
     "First radiation session down. Feeling fine, no pain, no nausea. Had my usual roast beef sandwich for lunch.",
     {"nausea": 0, "vomit": 0, "pain": 0, "fatigue": 1},
     [("symptom", "nausea", "no nausea", "current", None, 0, None, "Feeling fine, no pain, no nausea.", "absent"),
      ("symptom", "pain", "no pain", "current", None, None, None, "no pain", "absent")],
     []),
    
    # Day 2: Baseline
    (2, True, 194.8, 0, 0, "Solids",
     "Radiation #2 done. Throat feels a touch dry, otherwise 100%. No stomach trouble.",
     {"nausea": 0, "vomit": 0, "pain": 1, "fatigue": 1},
     [("symptom", "dry_mouth", "Throat feels a touch dry", "current", None, None, None, "Throat feels a touch dry", "present"),
      ("symptom", "nausea", "No stomach trouble", "current", None, 0, None, "No stomach trouble.", "absent")],
     []),
    
    # Day 3: Chemo 1 - Colloquial reporting
    (3, True, 194.2, 4, 1, "Soft food",
     "Got my first bag of cisplatin today. Felt green around the gills on the drive home, threw up once in the driveway. Took the melt-in-mouth nausea tablet.",
     {"nausea": 4, "vomit": 1, "pain": 1, "fatigue": 4},
     [("symptom", "nausea", "Felt green around the gills", "today_earlier", {"value": 4, "scale": "0-10"}, None, None, "Felt green around the gills on the drive home", "present"),
      ("symptom", "vomiting", "threw up once in the driveway", "today_earlier", None, 1, None, "threw up once in the driveway.", "present"),
      ("medication_event", "Ondansetron ODT", "melt-in-mouth nausea tablet", "today_earlier", None, None, None, "Took the melt-in-mouth nausea tablet.", "taken")],
     [("Cisplatin", "40mg/m2", "taken", "First infusion completed"),
      ("Ondansetron ODT", "8mg", "taken", "Post-chemo emesis")]),
    
    # Day 4: Delayed nausea
    (4, True, 193.5, 5, 2, "Soft food",
     "Stomach was churning all morning. Heaved twice after breakfast. Nausea is about a 5 out of 10. Took ondansetron.",
     {"nausea": 5, "vomit": 2, "pain": 2, "fatigue": 5},
     [("symptom", "nausea", "Stomach was churning all morning", "today_earlier", {"value": 5, "scale": "0-10"}, None, None, "Stomach was churning all morning.", "present"),
      ("symptom", "vomiting", "Heaved twice after breakfast", "today_earlier", None, 2, None, "Heaved twice after breakfast.", "present"),
      ("medication_event", "Ondansetron ODT", "Took ondansetron", "today_earlier", None, None, None, "Took ondansetron.", "taken")],
     [("Ondansetron ODT", "8mg", "taken", "Morning dose")]),
    
    # Day 5: HELD-OUT SYMPTOM 1: Hiccups / Singultus
    (5, True, 193.0, 3, 0, "Soft food",
     "Started getting violent hiccups around noon that wouldn't stop for four hours straight. Chest muscles ache from it. Nausea is down to 3, no throwing up today.",
     {"nausea": 3, "vomit": 0, "pain": 3, "fatigue": 5},
     [("symptom", "singultus", "violent hiccups around noon that wouldn't stop for four hours straight", "today_earlier", None, None, None, "Started getting violent hiccups around noon that wouldn't stop for four hours straight.", "present"),
      ("symptom", "nausea", "Nausea is down to 3", "current", {"value": 3, "scale": "0-10"}, None, None, "Nausea is down to 3", "present"),
      ("symptom", "vomiting", "no throwing up today", "current", None, 0, None, "no throwing up today.", "absent")],
     []),
    
    # Day 6: Hiccups resolving
    (6, True, 192.6, 2, 0, "Soft food",
     "Hiccups finally eased off this morning, just a few stray ones. Stomach is settling down, nausea 2/10. No vomiting.",
     {"nausea": 2, "vomit": 0, "pain": 2, "fatigue": 4},
     [("symptom", "singultus", "just a few stray ones", "current", None, None, None, "Hiccups finally eased off this morning, just a few stray ones.", "present"),
      ("symptom", "nausea", "nausea 2/10", "current", {"value": 2, "scale": "0-10"}, None, None, "nausea 2/10.", "present"),
      ("symptom", "vomiting", "No vomiting", "current", None, 0, None, "No vomiting.", "absent")],
     []),
    
    # Day 7: Fatigue
    (7, True, 192.4, 1, 0, "Soft food",
     "Felt worn out today, rested on the recliner. Throat feels scratchy, but no nausea and no throwing up.",
     {"nausea": 1, "vomit": 0, "pain": 2, "fatigue": 4},
     [("symptom", "fatigue", "Felt worn out today", "current", None, None, None, "Felt worn out today", "present"),
      ("symptom", "nausea", "no nausea", "current", None, 0, None, "no nausea and no throwing up.", "absent"),
      ("symptom", "vomiting", "no throwing up", "current", None, 0, None, "no throwing up.", "absent")],
     []),
    
    # Day 8: Stable
    (8, True, 192.0, 0, 0, "Soft food",
     "Good day. Radiation session 6 done. Ate beef stew cut up small. No stomach upset whatsoever.",
     {"nausea": 0, "vomit": 0, "pain": 2, "fatigue": 3},
     [("symptom", "nausea", "No stomach upset whatsoever", "current", None, 0, None, "No stomach upset whatsoever.", "absent")],
     []),
    
    # Day 9: Pre-chemo
    (9, True, 191.5, 1, 0, "Soft food",
     "Pre-chemo labs done. Hydrating with water. Throat is mildly sore, pain at 2/10. Denies nausea.",
     {"nausea": 1, "vomit": 0, "pain": 2, "fatigue": 3},
     [("symptom", "pain", "Throat is mildly sore, pain at 2/10", "current", {"value": 2, "scale": "0-10"}, None, None, "Throat is mildly sore, pain at 2/10.", "present"),
      ("symptom", "nausea", "Denies nausea", "current", None, 0, None, "Denies nausea.", "absent")],
     []),
    
    # Day 10: Chemo 2 - Acute emesis
    (10, True, 190.8, 6, 2, "Soft food",
     "Chemo #2 today. Chucked up my lunch twice right after getting home. Nausea was a solid 6. Took the dissolvable ondansetron.",
     {"nausea": 6, "vomit": 2, "pain": 3, "fatigue": 6},
     [("symptom", "vomiting", "Chucked up my lunch twice right after getting home", "today_earlier", None, 2, None, "Chucked up my lunch twice right after getting home.", "present"),
      ("symptom", "nausea", "Nausea was a solid 6", "current", {"value": 6, "scale": "0-10"}, None, None, "Nausea was a solid 6.", "present"),
      ("medication_event", "Ondansetron ODT", "dissolvable ondansetron", "today_earlier", None, None, None, "Took the dissolvable ondansetron.", "taken")],
     [("Cisplatin", "40mg/m2", "taken", "Second infusion"),
      ("Ondansetron ODT", "8mg", "taken", "Post-emesis dose")]),
    
    # Day 11: HELD-OUT SYMPTOM 2: Tinnitus (Ototoxicity)
    (11, True, 190.2, 5, 1, "Soft food",
     "There is a persistent high-pitched ringing in both ears that started last night and won't go away. Vomited once this morning. Nausea at 5.",
     {"nausea": 5, "vomit": 1, "pain": 3, "fatigue": 6},
     [("symptom", "tinnitus", "persistent high-pitched ringing in both ears that started last night and won't go away", "current", None, None, None, "There is a persistent high-pitched ringing in both ears that started last night and won't go away.", "present"),
      ("symptom", "vomiting", "Vomited once this morning", "today_earlier", None, 1, None, "Vomited once this morning.", "present"),
      ("symptom", "nausea", "Nausea at 5", "current", {"value": 5, "scale": "0-10"}, None, None, "Nausea at 5.", "present")],
     [("Ondansetron ODT", "8mg", "taken", "Morning dose")]),
    
    # Day 12: Tinnitus steady
    (12, True, 189.6, 4, 1, "Liquids only",
     "Constant ringing like a tea kettle in my ears all day. Nausea is a 4, threw up breakfast. Swallowing is getting tricky.",
     {"nausea": 4, "vomit": 1, "pain": 4, "fatigue": 6},
     [("symptom", "tinnitus", "Constant ringing like a tea kettle in my ears all day", "current", None, None, None, "Constant ringing like a tea kettle in my ears all day.", "present"),
      ("symptom", "nausea", "Nausea is a 4", "current", {"value": 4, "scale": "0-10"}, None, None, "Nausea is a 4", "present"),
      ("symptom", "vomiting", "threw up breakfast", "today_earlier", None, 1, None, "threw up breakfast.", "present")],
     []),
    
    # Day 13: Vague count
    (13, True, 189.0, 5, 3, "Liquids only",
     "Felt pretty rotten today. Threw up a few times yesterday and this morning, mostly dry heaves. Ears are still buzzing.",
     {"nausea": 5, "vomit": 3, "pain": 5, "fatigue": 7},
     [("symptom", "vomiting", "Threw up a few times yesterday and this morning", "mixed", None, None, None, "Threw up a few times yesterday and this morning, mostly dry heaves.", "present"),
      ("symptom", "tinnitus", "Ears are still buzzing", "current", None, None, None, "Ears are still buzzing.", "present")],
     []),
    
    # Day 14: Easing
    (14, True, 188.5, 3, 0, "Soft food",
     "Nausea is down to a 3. No vomiting today. Throat is sore (pain 5/10), ears still ringing. Managed scrambled eggs.",
     {"nausea": 3, "vomit": 0, "pain": 5, "fatigue": 5},
     [("symptom", "nausea", "Nausea is down to a 3", "current", {"value": 3, "scale": "0-10"}, None, None, "Nausea is down to a 3.", "present"),
      ("symptom", "vomiting", "No vomiting today", "current", None, 0, None, "No vomiting today.", "absent"),
      ("symptom", "tinnitus", "ears still ringing", "current", None, None, None, "ears still ringing.", "present")],
     []),
    
    # Day 15: MISSING
    (15, False, 188.0, 4, 0, "Soft food", "", {}, [], []),
    
    # Day 16: Retrospective
    (16, True, 187.5, 3, 0, "Soft food",
     "Forgot to log yesterday, was sleeping off fatigue. Feeling somewhat steadier today, nausea at 3, but the ear ringing is definitely here to stay.",
     {"nausea": 3, "vomit": 0, "pain": 5, "fatigue": 6},
     [("symptom", "nausea", "nausea at 3", "current", {"value": 3, "scale": "0-10"}, None, None, "Feeling somewhat steadier today, nausea at 3", "present"),
      ("symptom", "tinnitus", "ear ringing is definitely here to stay", "current", None, None, None, "the ear ringing is definitely here to stay.", "present")],
     []),
    
    # Day 17: Chemo 3 - Acute vomiting
    (17, True, 187.0, 7, 3, "Liquids only",
     "Third chemo session. Heaved my guts out 3 times this afternoon. Nausea is a 7. Took metoclopramide before dinner.",
     {"nausea": 7, "vomit": 3, "pain": 5, "fatigue": 7},
     [("symptom", "vomiting", "Heaved my guts out 3 times this afternoon", "today_earlier", None, 3, None, "Heaved my guts out 3 times this afternoon.", "present"),
      ("symptom", "nausea", "Nausea is a 7", "current", {"value": 7, "scale": "0-10"}, None, None, "Nausea is a 7.", "present"),
      ("medication_event", "Metoclopramide", "Took metoclopramide", "today_earlier", None, None, None, "Took metoclopramide before dinner.", "taken")],
     [("Cisplatin", "40mg/m2", "taken", "Third infusion"),
      ("Metoclopramide", "10mg", "taken", "Taken for delayed gastric emptying")]),
    
    # Day 18: Tinnitus worsens + Breathlessness
    (18, True, 186.2, 6, 2, "Liquids only",
     "Ear ringing got louder after yesterday's chemo. Vomited twice today. Also felt strangely winded just walking from bedroom to kitchen.",
     {"nausea": 6, "vomit": 2, "pain": 6, "fatigue": 8},
     [("symptom", "tinnitus", "Ear ringing got louder after yesterday's chemo", "current", None, None, None, "Ear ringing got louder after yesterday's chemo.", "present"),
      ("symptom", "vomiting", "Vomited twice today", "today_earlier", None, 2, None, "Vomited twice today.", "present"),
      ("symptom", "breathlessness", "strangely winded just walking from bedroom to kitchen", "today_earlier", None, None, None, "Also felt strangely winded just walking from bedroom to kitchen.", "present")],
     []),
    
    # Day 19: SYNCOPE / FAINTING EPISODE
    (19, True, 185.8, 5, 1, "Liquids only",
     "Scary moment: stood up from the sofa and actually passed out for a few seconds on the rug. My wife had to help me back up. Vomited once earlier. Nausea 5.",
     {"nausea": 5, "vomit": 1, "pain": 6, "fatigue": 8},
     [("symptom", "syncope", "actually passed out for a few seconds on the rug", "today_earlier", None, None, None, "stood up from the sofa and actually passed out for a few seconds on the rug.", "present"),
      ("symptom", "vomiting", "Vomited once earlier", "today_earlier", None, 1, None, "Vomited once earlier.", "present"),
      ("symptom", "nausea", "Nausea 5", "current", {"value": 5, "scale": "0-10"}, None, None, "Nausea 5.", "present")],
     []),
    
    # Day 20: Recovery from syncope
    (20, True, 185.5, 4, 0, "Liquids only",
     "Staying horizontal today on doctor's orders. Drank electrolyte drinks. No throwing up today. Nausea is at 4.",
     {"nausea": 4, "vomit": 0, "pain": 6, "fatigue": 7},
     [("symptom", "vomiting", "No throwing up today", "current", None, 0, None, "No throwing up today.", "absent"),
      ("symptom", "nausea", "Nausea is at 4", "current", {"value": 4, "scale": "0-10"}, None, None, "Nausea is at 4.", "present")],
     []),
    
    # Day 21: Text vs Questionnaire Conflict
    (21, True, 185.0, 3, 0, "Liquids only",
     "Can only get down lukewarm soup, throat hurts too much for bread. Pain is easily a 7 when trying to swallow.",
     {"nausea": 3, "vomit": 0, "pain": 3, "fatigue": 6},  # Questionnaire says pain 3!
     [("symptom", "dysphagia", "Can only get down lukewarm soup, throat hurts too much for bread", "current", {"value": 2, "scale": "0-4"}, None, None, "Can only get down lukewarm soup, throat hurts too much for bread.", "present"),
      ("symptom", "pain", "Pain is easily a 7 when trying to swallow", "current", {"value": 7, "scale": "0-10"}, None, None, "Pain is easily a 7 when trying to swallow.", "present")],
     []),
    
    # Day 22: HELD-OUT SYMPTOM 3: Peripheral Neuropathy
    (22, True, 184.5, 2, 0, "Liquids only",
     "My fingertips feel numb and prickly like pins and needles. Dropped my coffee mug this morning because I couldn't feel it properly. Nausea is down to 2.",
     {"nausea": 2, "vomit": 0, "pain": 6, "fatigue": 6},
     [("symptom", "peripheral_neuropathy", "fingertips feel numb and prickly like pins and needles", "current", None, None, None, "My fingertips feel numb and prickly like pins and needles.", "present"),
      ("symptom", "nausea", "Nausea is down to 2", "current", {"value": 2, "scale": "0-10"}, None, None, "Nausea is down to 2.", "present")],
     []),
    
    # Day 23: Neuropathy in toes
    (23, True, 184.2, 2, 0, "Liquids only",
     "Tingling spread to my toes today. Walking feels like walking on bubble wrap. Ear ringing constant. No vomiting.",
     {"nausea": 2, "vomit": 0, "pain": 6, "fatigue": 6},
     [("symptom", "peripheral_neuropathy", "Tingling spread to my toes today", "current", None, None, None, "Tingling spread to my toes today. Walking feels like walking on bubble wrap.", "present"),
      ("symptom", "tinnitus", "Ear ringing constant", "current", None, None, None, "Ear ringing constant.", "present"),
      ("symptom", "vomiting", "No vomiting", "current", None, 0, None, "No vomiting.", "absent")],
     []),
    
    # Day 24: Chemo 4 - Neuropathy + Nausea
    (24, True, 183.8, 6, 2, "Liquids only",
     "Chemo #4. Told doctor about the ringing and numb fingers. Threw up twice after getting home. Nausea is at a 6.",
     {"nausea": 6, "vomit": 2, "pain": 6, "fatigue": 7},
     [("symptom", "tinnitus", "ringing", "today_earlier", None, None, None, "Told doctor about the ringing and numb fingers.", "present"),
      ("symptom", "peripheral_neuropathy", "numb fingers", "today_earlier", None, None, None, "Told doctor about the ringing and numb fingers.", "present"),
      ("symptom", "vomiting", "Threw up twice after getting home", "today_earlier", None, 2, None, "Threw up twice after getting home.", "present"),
      ("symptom", "nausea", "Nausea is at a 6", "current", {"value": 6, "scale": "0-10"}, None, None, "Nausea is at a 6.", "present")],
     [("Cisplatin", "40mg/m2", "taken", "Fourth infusion")]),
    
    # Day 25: Recurrent hiccups + nausea
    (25, True, 183.4, 5, 1, "Liquids only",
     "The hiccups came back after the steroid infusion yesterday, along with ear ringing. Vomited once around lunch. Nausea at 5.",
     {"nausea": 5, "vomit": 1, "pain": 6, "fatigue": 7},
     [("symptom", "singultus", "hiccups came back after the steroid infusion", "today_earlier", None, None, None, "The hiccups came back after the steroid infusion yesterday", "present"),
      ("symptom", "tinnitus", "ear ringing", "current", None, None, None, "along with ear ringing.", "present"),
      ("symptom", "vomiting", "Vomited once around lunch", "today_earlier", None, 1, None, "Vomited once around lunch.", "present"),
      ("symptom", "nausea", "Nausea at 5", "current", {"value": 5, "scale": "0-10"}, None, None, "Nausea at 5.", "present")],
     []),
    
    # Day 26: Correction / count nuance
    (26, True, 183.0, 6, 3, "Liquids only",
     "Heaved once before noon and once after... wait, actually vomited three times total today if counting the morning bile. Nausea at 6.",
     {"nausea": 6, "vomit": 3, "pain": 6, "fatigue": 7},
     [("symptom", "vomiting", "actually vomited three times total today", "today_earlier", None, 3, None, "Heaved once before noon and once after... wait, actually vomited three times total today if counting the morning bile.", "present"),
      ("symptom", "nausea", "Nausea at 6", "current", {"value": 6, "scale": "0-10"}, None, None, "Nausea at 6.", "present")],
     []),
    
    # Day 27: MISSING
    (27, False, 182.6, 4, 0, "Liquids only", "", {}, [], []),
    
    # Day 28: Close of study
    (28, True, 182.4, 2, 0, "Liquids only",
     "End of week 4. Ears are still ringing, fingers still numb and tingling, but stomach has finally settled down. No vomiting today.",
     {"nausea": 2, "vomit": 0, "pain": 6, "fatigue": 6},
     [("symptom", "tinnitus", "Ears are still ringing", "current", None, None, None, "Ears are still ringing", "present"),
      ("symptom", "peripheral_neuropathy", "fingers still numb and tingling", "current", None, None, None, "fingers still numb and tingling", "present"),
      ("symptom", "nausea", "stomach has finally settled down", "current", {"value": 2, "scale": "0-10"}, None, None, "but stomach has finally settled down.", "present"),
      ("symptom", "vomiting", "No vomiting today", "current", None, 0, None, "No vomiting today.", "absent")],
     [])
]
RAW_SLOTS.append(("SYN-PT-103", pt103_days))

# ==============================================================================
# 3. BUILD ALL JSON / JSONL ARTIFACTS
# ==============================================================================

schedule_slots = []
ground_truth_events = []
check_ins = []
expected_annotations = []
medication_events = []

for pt_id, days in RAW_SLOTS:
    pt_meta = next(p for p in PATIENTS if p["patient_id"] == pt_id)
    split = pt_meta["split"]
    
    for day_num, is_submitted, weight, nausea_val, vomit_count, swallow_val, text, quest, expected_ents, meds in days:
        slot_id = f"SLOT-{pt_id}-D{day_num:02d}"
        cur_date = get_date(day_num)
        
        # 1. Schedule Slot
        slot_record = {
            "slot_id": slot_id,
            "patient_id": pt_id,
            "split": split,
            "day_number": day_num,
            "scheduled_date": cur_date,
            "submission_status": "submitted" if is_submitted else "missing",
            "reason_if_missing": "Patient severe post-chemotherapy exhaustion / missed submission window" if not is_submitted else None
        }
        schedule_slots.append(slot_record)
        
        # 2. Ground Truth Latent Facts (FIRST!)
        gt_record = {
            "slot_id": slot_id,
            "patient_id": pt_id,
            "split": split,
            "day_number": day_num,
            "date": cur_date,
            "is_submitted": is_submitted,
            "latent_clinical_state": {
                "nausea_severity_nrs": nausea_val,
                "vomiting_episodes": vomit_count,
                "swallowing_capability": swallow_val,
                "weight_lb": weight,
                "is_chemo_day": day_num in pt_meta["chemo_days"],
                "active_symptoms_present": [e[1] for e in expected_ents if e[-1] == "present"],
                "active_symptoms_absent": [e[1] for e in expected_ents if e[-1] == "absent"]
            },
            "latent_medications": meds
        }
        ground_truth_events.append(gt_record)
        
        # 3. Check-In Report (SECOND!)
        if is_submitted:
            check_in_record = {
                "checkin_id": f"CHK-{pt_id}-D{day_num:02d}",
                "slot_id": slot_id,
                "patient_id": pt_id,
                "split": split,
                "day_number": day_num,
                "submission_timestamp": f"{cur_date}T08:30:00",
                "free_text_report": text,
                "questionnaire_responses": {
                    "reported_nausea_score_0_to_10": quest.get("nausea"),
                    "reported_vomiting_episodes": quest.get("vomit"),
                    "reported_pain_score_0_to_10": quest.get("pain"),
                    "reported_fatigue_score_0_to_10": quest.get("fatigue"),
                    "reported_swallowing_status": swallow_val,
                    "reported_weight_lb": weight
                }
            }
            check_ins.append(check_in_record)
            
            # 4. Expected Annotations (THIRD! Faithful to text, no latent leakage)
            annotations_for_slot = []
            for ent in expected_ents:
                ent_type, norm_name, orig_phrase, timing, sev, count, bounds, quote, status = ent
                is_unquantified = (norm_name == "vomiting" and status == "present" and count is None and bounds is None and any(w in orig_phrase.lower() for w in ["couple", "multiple", "few", "times"]))
                conflict_quest = (
                    True if norm_name == "nausea" and quest.get("nausea") == 0 and status == "present"
                    else True if norm_name == "pain" and quest.get("pain") == 2 and sev and sev.get("value", 0) >= 7
                    else False
                )
                is_correction = (
                    ("actually" in orig_phrase.lower() or "wait" in orig_phrase.lower()) and
                    any(c in orig_phrase.lower() for c in ["times", "twice", "three", "once", "count", "heaves"])
                )
                
                needs_review = is_unquantified or bounds is not None or status == "uncertain" or conflict_quest
                review_reason = None
                if is_unquantified:
                    review_reason = f"Unquantified colloquial phrase '{orig_phrase}' - retained verbatim without unsupported numeric precision"
                elif conflict_quest:
                    review_reason = f"Text report conflicts with structured questionnaire value"
                elif status == "uncertain":
                    review_reason = f"Patient expressed uncertainty regarding symptom presence"

                ann_item = {
                    "entity_type": ent_type,
                    "normalized_concept": norm_name,
                    "original_phrase": orig_phrase,
                    "evidence_quote": quote,
                    "status": status,
                    "temporal_anchor": timing,
                    "severity": sev,
                    "exact_count": count,
                    "count_bounds": bounds,
                    "is_unquantified_count": is_unquantified,
                    "conflict_with_questionnaire": conflict_quest,
                    "correction_or_clarification": (
                        "Corrected initial count within report to avoid double-counting" if is_correction
                        else None
                    ),
                    "review_needed": needs_review,
                    "review_reason": review_reason
                }
                annotations_for_slot.append(ann_item)
            
            expected_annotations.append({
                "checkin_id": f"CHK-{pt_id}-D{day_num:02d}",
                "slot_id": slot_id,
                "patient_id": pt_id,
                "split": split,
                "day_number": day_num,
                "date": cur_date,
                "extractable_entities": annotations_for_slot
            })
        
        # 5. Medication Events
        for med in meds:
            drug, dose, status, note = med
            medication_events.append({
                "med_event_id": f"MED-{pt_id}-D{day_num:02d}-{len(medication_events):04d}",
                "slot_id": slot_id,
                "patient_id": pt_id,
                "day_number": day_num,
                "date": cur_date,
                "drug_name": drug,
                "dose": dose,
                "status": status,
                "clinical_note": note
            })

# Write output files
output_files = {
    "patients.json": PATIENTS,
    "schedule_slots.json": schedule_slots,
    "ground_truth_events.json": ground_truth_events,
    "check_ins.json": check_ins,
    "expected_annotations.json": expected_annotations,
    "medication_events.json": medication_events
}

for filename, data in output_files.items():
    file_path = BASE_DIR / filename
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {filename} ({len(data)} items)")

# Write JSONL variants for streaming / NLP pipeline convenience
with open(BASE_DIR / "check_ins.jsonl", "w", encoding="utf-8") as f:
    for item in check_ins:
        f.write(json.dumps(item) + "\n")
print(f"Wrote check_ins.jsonl ({len(check_ins)} lines)")

with open(BASE_DIR / "expected_annotations.jsonl", "w", encoding="utf-8") as f:
    for item in expected_annotations:
        f.write(json.dumps(item) + "\n")
print(f"Wrote expected_annotations.jsonl ({len(expected_annotations)} lines)")

# ==============================================================================
# 4. GENERATE README.MD MANIFEST
# ==============================================================================
total_slots = len(schedule_slots)
submitted_reports = len(check_ins)
missing_slots = total_slots - submitted_reports

readme_content = f"""# Synthetic Clinical Dataset: Oncology Chemoradiation & CINV
**Pipeline Securities Inc. - Track B: Patient-Reported Data: Store, Manage & Chart**  
**Dataset Version**: 1.1.0 (Fixed reproducible dates, refined vague counts & regimen change fixture)  
**Date Range**: 2026-10-05 to 2026-11-01 (28 scheduled days)  

> **Notice**: Expected annotations are synthetic evaluation labels designed for parser benchmarking, not human-verified clinical ground truth.

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
  * Descriptive observation: 9 vomiting episodes reported across the 7-day period (Day 10 unquantified multiple bouts, Day 11 1x, Day 12 1x, Day 16 3x on chemo day).
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
"""

with open(BASE_DIR / "README.md", "w", encoding="utf-8") as f:
    f.write(readme_content)
print("Wrote README.md manifest")
