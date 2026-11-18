"""Small medspaCy TargetMatcher/ConText baseline, supplemented by explicit rules.

This is a bounded rule vocabulary, not a model of arbitrary clinical language.
"""
import re
import warnings
from datetime import date, timedelta
from functools import lru_cache

import medspacy
import spacy
from spacy.language import Language
from medspacy.ner import TargetRule

TERMS = {
    'nausea': ['nausea', 'nauseous', 'queasy', 'sick to my stomach'],
    'vomiting': ['vomiting', 'vomited', 'vomit', 'threw up', 'throwing up', 'throw up', 'puked', 'puking'],
    'pain': ['pain', 'painful', 'sore throat', 'throat hurts', 'hurts'],
    'fatigue': ['fatigue', 'fatigued', 'tired', 'exhausted', 'exhaustion'],
    'dizziness': ['dizziness', 'dizzy', 'lightheaded', 'light-headed'],
    'breathlessness': ['shortness of breath', 'short of breath', 'breathless', 'breathlessness'],
    'fainting': ['fainted', 'fainting', 'passed out'],
    'diarrhea': ['diarrhea', 'diarrhoea'], 'constipation': ['constipation', 'constipated'],
    'headache': ['headache', 'headaches'], 'mouth_sores': ['mouth sores', 'mouth sore'],
}
NUMBERS = {'once': 1, 'twice': 2, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
COUNT = re.compile(r'\b(once|twice|\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:times?|episodes?)?\b', re.I)
COUNT_RANGE = re.compile(r'\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:-|–|—|to|or)\s*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:times?|episodes?)\b', re.I)
MEDICATION = re.compile(r'\b(ondansetron|zofran|aprepitant|prochlorperazine|dexamethasone|lorazepam|cisplatin|antiemetic|medication|medicine|meds)\b', re.I)


@Language.component('trackb_clause_boundaries')
def _clause_boundaries(doc):
    # A new affirmative symptom clause ends the preceding negation scope.
    # Keep coordinated negatives such as "no nausea, vomiting or pain" together.
    terms = '|'.join(re.escape(term) for phrases in TERMS.values() for term in phrases)
    pattern = rf',\s*(?=(?:{terms})\s+(?:down|up|at|is|was|still|mild|moderate|severe|remains|feels)\b)'
    starts = {match.end() for match in re.finditer(pattern, doc.text, re.I)}
    for token in doc:
        if token.idx in starts:
            token.is_sent_start = True
    return doc


@lru_cache(maxsize=1)
def _pipeline():
    # spaCy's sentence splitter avoids PyRuSH's verbose debug logger.
    nlp = spacy.blank('en')
    nlp.add_pipe('sentencizer')
    nlp = medspacy.load(model=nlp, medspacy_enable=['medspacy_target_matcher', 'medspacy_context'])
    matcher = nlp.get_pipe('medspacy_target_matcher')
    nlp.add_pipe('trackb_clause_boundaries', before='medspacy_context')
    matcher.add([TargetRule(term, symptom) for symptom, terms in TERMS.items() for term in terms])
    return nlp


def _base(symptom, phrase, presence, evidence, observed_date, source):
    return dict(symptom=symptom, original_phrase=phrase, presence=presence, severity_value=None,
                severity_scale=None, severity_text=None, episode_count=None, observed_date=observed_date,
                timing_text=None, medication_mentioned=None, evidence=evidence, source=source,
                issues_json=[], is_full_day=False, count_eligible=True)


def parse_text(text: str, report_date: str) -> list[dict]:
    report_day = date.fromisoformat(report_date)
    # medspaCy invokes both token and phrase matchers even when one is empty.
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message=r'\[W036\].*', category=UserWarning, module=r'medspacy\.common\.medspacy_matcher')
        doc = _pipeline()(text or '')
    rows = []
    for ent in doc.ents:
        sentence = ent.sent.text.strip()
        lower = sentence.lower()
        relative = re.search(r'\b(yesterday|today|last night|this morning|this afternoon|tonight|after dinner|all day|all night)\b', lower)
        day = report_day - timedelta(days=1) if re.search(r'\byesterday\b', lower) else report_day
        presence = 'absent' if ent._.is_negated else ('uncertain' if ent._.is_uncertain else 'present')
        row = _base(ent.label_, ent.text, presence, sentence, day.isoformat(), 'text')
        row['timing_text'] = relative.group(0) if relative else None
        if re.search(r'\byesterday\b', lower) and re.search(r'\btoday\b', lower):
            row['observed_date'] = None
            row['count_eligible'] = False
            row['issues_json'].append('ambiguous_mixed_dates')
        multi_day = re.search(r'\b(?:(?:over|for|in|past|last)\s+(?:the\s+)?(?:last\s+|past\s+)?(?:several|multiple|few|\d+|two|three|four|five|six|seven)\s+days?|since\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b', lower)
        if multi_day:
            row['observed_date'] = None
            row['timing_text'] = multi_day.group(0)
            row['count_eligible'] = False
            row['issues_json'].append('ambiguous_multiday')
        row['is_full_day'] = bool(re.search(r'\b(all day|entire day|whole day|in total|total today)\b', lower))
        if ent.label_ == 'vomiting' and presence == 'absent' and re.search(r'\btoday\b', lower) and not re.search(r'\b(tonight|this morning|this afternoon|this evening|after dinner)\b', lower):
            row['is_full_day'] = True
            row['episode_count'] = 0
        med = MEDICATION.search(sentence)
        row['medication_mentioned'] = med.group(0) if med else None
        severity = re.search(r'\b(mild|moderate|severe|slight(?:ly)?|terrible|intense)\b', lower)
        if severity:
            row['severity_text'] = severity.group(0)
        rating = re.search(r'\b(10|[0-9])\s*(?:/|out of)\s*10\b', lower)
        if rating:
            row['severity_value'], row['severity_scale'] = int(rating.group(1)), '0-10'
        if ent.label_ == 'vomiting' and presence == 'present':
            # Only explicit frequency phrases; numeric severity and calendar days are not counts.
            counts = [m for m in COUNT.finditer(lower) if m.group(1).lower() in ('once', 'twice') or re.search(r'(?:times?|episodes?)', m.group(0))]
            if COUNT_RANGE.search(lower):
                row['issues_json'].append('imprecise_count_range')
                row['count_eligible'] = False
            elif counts:
                chosen = counts[-1] if re.search(r'\b(actually|rather|correction|i mean)\b', lower) else counts[0]
                value = chosen.group(1).lower()
                row['episode_count'] = int(value) if value.isdigit() else NUMBERS[value]
                if len(counts) > 1 and not re.search(r'\b(actually|rather|correction|i mean)\b', lower):
                    row['issues_json'].append('overlapping_counts')
                    row['count_eligible'] = False
            elif re.search(r'\b(?:a couple|a few|several|multiple|many|numerous)\b', lower):
                row['issues_json'].append('unquantified_count')
                row['count_eligible'] = False
        rows.append(row)
    return rows


def resolve_review_date(text: str, quote: str, report_date: str):
    """Apply the local sentence-level date rules to a newly recognized symptom."""
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message=r'\[W036\].*', category=UserWarning, module=r'medspacy\.common\.medspacy_matcher')
        doc = _pipeline()(text)
    contexts = [sentence.text for sentence in doc.sents if quote in sentence.text]
    if not contexts:
        contexts = [quote]
    days = set()
    for context in contexts:
        lower = context.lower()
        if (re.search(r'\byesterday\b', lower) and re.search(r'\btoday\b', lower)) or re.search(
            r'\b(?:(?:over|for|in|past|last)\s+(?:the\s+)?(?:last\s+|past\s+)?(?:several|multiple|few|\d+|two|three|four|five|six|seven)\s+days?|since\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b', lower
        ):
            return None
        day = date.fromisoformat(report_date)
        if re.search(r'\byesterday\b', lower):
            day -= timedelta(days=1)
        days.add(day.isoformat())
    return next(iter(days)) if len(days) == 1 else None


def parse_report(report: dict) -> list[dict]:
    report_date = report.get('report_date') or report['submission_timestamp'][:10]
    rows = parse_text(report.get('free_text_report', report.get('raw_text', '')), report_date)
    responses = report.get('questionnaire_responses', {}) or {}
    for key, symptom in [('reported_vomiting_episodes', 'vomiting'), ('reported_nausea_score_0_to_10', 'nausea'), ('reported_pain_score_0_to_10', 'pain'), ('reported_fatigue_score_0_to_10', 'fatigue')]:
        value = responses.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0 or (symptom != 'vomiting' and value > 10):
            continue
        row = _base(symptom, key, 'present' if value > 0 else 'absent', f'{key}: {value}', report_date, 'questionnaire')
        if symptom == 'vomiting':
            row['episode_count'] = value
            row['is_full_day'] = True
        else:
            row['severity_value'], row['severity_scale'] = value, '0-10'
        rows.append(row)
    return rows
