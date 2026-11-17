from trackb.parser import parse_text, parse_report
import pytest


def test_text_negation_vague_and_correction():
    rows = parse_text('No nausea. Vomited a couple times. Later I vomited twice, actually three times.', '2026-10-10')
    assert next(r for r in rows if r['symptom'] == 'nausea')['presence'] == 'absent'
    vomiting = [r for r in rows if r['symptom'] == 'vomiting']
    assert vomiting[0]['episode_count'] is None
    assert vomiting[-1]['episode_count'] == 3


def test_relative_date_is_sentence_scoped_and_sources_are_separate():
    report = {'submission_timestamp': '2026-10-10T08:00:00', 'free_text_report': 'Yesterday I vomited twice. Today I have nausea.', 'questionnaire_responses': {'reported_vomiting_episodes': 0}}
    rows = parse_report(report)
    assert next(r for r in rows if r['source'] == 'text' and r['symptom'] == 'vomiting')['observed_date'] == '2026-10-09'
    assert next(r for r in rows if r['symptom'] == 'nausea')['observed_date'] == '2026-10-10'
    assert next(r for r in rows if r['source'] == 'questionnaire')['episode_count'] == 0


def test_ambiguous_multiday_counts_are_not_daily_totals():
    row = parse_text('I vomited three times over the last two days.', '2026-10-10')[0]
    assert row['episode_count'] == 3
    assert row['observed_date'] is None
    assert not row['count_eligible']


def test_combined_negation():
    rows = parse_text('No nausea, vomiting or pain today.', '2026-10-10')
    assert {r['symptom']: r['presence'] for r in rows} == {'nausea': 'absent', 'vomiting': 'absent', 'pain': 'absent'}


@pytest.mark.parametrize('phrase', ['2-3 times', '2 to 3 times', 'two or three times'])
def test_count_ranges_are_not_exact(phrase):
    row = parse_text(f'Vomited {phrase} today.', '2026-10-17')[0]
    assert row['episode_count'] is None
    assert phrase in row['evidence']


def test_since_weekday_is_not_a_daily_total():
    row = parse_text('Vomited three times since Monday.', '2026-10-17')[0]
    assert row['observed_date'] is None
    assert row['episode_count'] == 3
    assert not row['count_eligible']


def test_vague_vomiting_is_flagged_without_inventing_count():
    row = parse_text('I vomited a couple of times.', '2026-10-17')[0]
    assert row['episode_count'] is None
    assert 'unquantified_count' in row['issues_json']


def test_daywide_vomiting_absence_is_zero_but_partial_absence_is_not():
    full = parse_text('No vomiting today.', '2026-10-17')[0]
    partial = parse_text('No vomiting tonight.', '2026-10-17')[0]
    assert full['episode_count'] == 0 and full['is_full_day']
    assert partial['episode_count'] is None and not partial['is_full_day']


def test_mixed_explicit_dates_are_not_backdated():
    rows = parse_text('Felt nauseous yesterday, but today I vomited.', '2026-10-17')
    vomiting = next(r for r in rows if r['symptom'] == 'vomiting')
    assert vomiting['observed_date'] in (None, '2026-10-17')
def test_positive_symptom_clause_does_not_inherit_negation():
    from trackb.parser import parse_text

    rows = parse_text(
        "Much calmer today. No vomiting today, nausea down to a 2, managed tea and toast.",
        "2026-10-08",
    )
    assert next(row for row in rows if row['symptom'] == 'vomiting')['presence'] == 'absent'
    assert next(row for row in rows if row['symptom'] == 'nausea')['presence'] == 'present'

