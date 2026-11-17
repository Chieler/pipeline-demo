"""One-page patient-reported symptom demonstration. Run: streamlit run app.py."""

from contextlib import closing
import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from trackb.db import connect, initialize, import_dataset, daily_symptoms, weekly_symptoms, medication_comparison
from trackb.verify import VerifierConfig, verify_report


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("TRACKB_DB_PATH", str(ROOT / "data" / "trackb.sqlite")))


def decoded(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value) if value else fallback
    except (ValueError, TypeError):
        return fallback


def readable_chart(fig):
    """Keep labels legible when the dashboard is presented on a larger screen."""
    fig.update_layout(
        font=dict(size=16),
        legend=dict(font=dict(size=16)),
        hoverlabel=dict(font_size=16),
    )
    fig.update_xaxes(tickfont=dict(size=16), title_font=dict(size=18), automargin=True)
    fig.update_yaxes(tickfont=dict(size=16), title_font=dict(size=18), automargin=True)
    return fig


st.set_page_config(page_title="Patient symptom trends", layout="wide")
st.title("Patient-reported symptoms")

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
with closing(connect(DB_PATH)) as conn:
    initialize(conn)
    if conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
        with st.spinner("Loading check-ins…"):
            import_dataset(conn, ROOT / "data" / "synthetic")

    patients = [dict(row) for row in conn.execute("SELECT * FROM patients ORDER BY patient_id")]
    by_id = {patient["patient_id"]: patient for patient in patients}
    with st.sidebar:
        st.header("Patient")
        patient_id = st.selectbox(
            "Choose a patient", list(by_id),
            format_func=lambda key: f"{by_id[key]['name']} · {by_id[key]['age']}", key="patient",
        )
        selected_patient = by_id[patient_id]
        period_start = pd.Timestamp(selected_patient["start_date"])
        period_end = pd.Timestamp(selected_patient["end_date"])
        st.markdown(f"### {period_start.strftime('%d %b %Y')} – {period_end.strftime('%d %b %Y')}")
        st.caption("Scheduled check-ins: daily")

    patient = by_id[patient_id]
    reports = [dict(row) for row in conn.execute(
        "SELECT * FROM reports WHERE patient_id=? ORDER BY report_date, report_id", (patient_id,)
    )]
    medication = [dict(row) for row in conn.execute(
        "SELECT * FROM medication_events WHERE patient_id=? ORDER BY effective_date", (patient_id,)
    )]
    daily = pd.DataFrame(daily_symptoms(conn, patient_id))
    weekly = pd.DataFrame(weekly_symptoms(conn, patient_id))
    comparison = pd.DataFrame(medication_comparison(conn, patient_id))
    start = pd.Timestamp(patient["start_date"])
    dates = pd.date_range(start, periods=28)
    date_labels = [date.strftime("%Y-%m-%d") for date in dates]
    submitted_dates = {row["report_date"] for row in reports}
    missing_dates = [date for date in date_labels if date not in submitted_dates]

    st.subheader(f"{patient['name']}, {patient['age']}")
    st.markdown(f"### Reporting period: {start.strftime('%d %b')}–{dates[-1].strftime('%d %b %Y')}")
    st.caption("Radiation with chemotherapy")
    vomiting = daily[daily["symptom"] == "vomiting"].copy() if not daily.empty else pd.DataFrame()
    episode_total = int(vomiting["episode_count"].sum()) if not vomiting.empty else 0
    excluded = int(vomiting["count_excluded"].sum()) if not vomiting.empty else 0
    left, middle, right = st.columns(3)
    left.metric("Check-ins submitted", f"{len(submitted_dates)} / 28")
    middle.metric("Documented vomiting episodes", episode_total)
    right.metric("Days with unclear vomiting counts", excluded, help="Vomiting was reported, but the number of episodes was vague or conflicting. These days are excluded from the episode total.")

    st.subheader("Symptoms over time")
    if not daily.empty:
        statuses = {"missing": 0, "not_assessed": 1, "unassessed": 1, "absent": 2, "present": 3, "uncertain": 4, "conflict": 5}
        colors = ["#8b6db1", "#f8fafc", "#bae6d4", "#246d65", "#f3cf8a", "#a34a45"]
        symptoms = sorted(daily["symptom"].unique())
        grid, hover = [], []
        indexed = {(str(row["date"]), row["symptom"]): row for row in daily.to_dict("records")}
        for symptom in symptoms:
            values, details = [], []
            for date in date_labels:
                row = indexed.get((date, symptom), {})
                presence = row.get("presence") or "not_assessed"
                if date not in submitted_dates and presence in ("not_assessed", "unassessed"):
                    presence = "missing"
                values.append(statuses.get(presence, 1))
                coverage = "Check-in submitted" if date in submitted_dates else "No check-in; retrospective evidence may exist"
                details.append(f"{symptom.replace('_', ' ').title()}: {presence.replace('_', ' ')}<br>{coverage}")
            grid.append(values)
            hover.append(details)
        scale = [[point, color] for index, color in enumerate(colors) for point in (index / 6, (index + 1) / 6)]
        heatmap = go.Figure(go.Heatmap(
            x=date_labels, y=[symptom.replace("_", " ").title() for symptom in symptoms], z=grid,
            zmin=-0.5, zmax=5.5, colorscale=scale, text=hover,
            hovertemplate="%{x}<br>%{text}<extra></extra>", xgap=2, ygap=3,
            colorbar={"tickvals": list(range(6)), "ticktext": ["No check-in", "Unassessed", "Absent", "Present", "Uncertain", "Conflict"]},
        ))
        heatmap.update_layout(height=max(360, 40 * len(symptoms)), margin=dict(l=0, r=0, t=10, b=0), xaxis_title=None, yaxis_title=None)
        heatmap.update_traces(colorbar_tickfont_size=16)
        st.plotly_chart(readable_chart(heatmap), width="stretch")
    st.caption("Missing check-ins: " + ", ".join(pd.Timestamp(date).strftime("%d %b") for date in missing_dates) + ". Unmentioned symptoms stay unassessed. A retrospective report may supply evidence for a missed day.")

    st.subheader("Documented vomiting episodes")
    if medication:
        st.caption("Dashed marker: regimen change. " + "; ".join(f"{event['effective_date']}: {event['event_type']} {event['medication']}" for event in medication))
    counts = {str(row["date"]): row for row in vomiting.to_dict("records")} if not vomiting.empty else {}
    values = [counts.get(date, {}).get("episode_count") for date in date_labels]
    bars = go.Figure(go.Bar(x=date_labels, y=values, marker_color="#246d65", name="Documented episodes"))
    unknown = [date for date, value in zip(date_labels, values) if value is None or pd.isna(value)]
    if unknown:
        bars.add_trace(go.Scatter(x=unknown, y=[0] * len(unknown), mode="markers", marker={"symbol": "x", "size": 10, "color": "#a34a45"}, name="Unknown / excluded, not zero"))
    for date in sorted({event["effective_date"] for event in medication}):
        bars.add_vline(x=date, line_dash="dash", line_color="#a16207")
    bars.update_layout(
        height=380, margin=dict(l=0, r=0, t=10, b=90),
        yaxis_title="Documented episodes", yaxis_rangemode="tozero", xaxis_title=None,
        legend=dict(orientation="h", x=0, y=-0.3, yanchor="top"),
    )
    st.plotly_chart(readable_chart(bars), width="stretch")

    with st.expander("Weekly symptom summary", expanded=True):
        if weekly.empty:
            st.info("No weekly symptom observations are available for this patient.")
        else:
            st.caption("Days with each symptom, by study week. Hover for reporting coverage and count details.")
            weekly_chart = go.Figure()
            week_colors = ["#246d65", "#568f86", "#b0803b", "#8e625d"]
            for index, week in enumerate(sorted(weekly["week"].unique())):
                rows = weekly[weekly["week"] == week].sort_values("symptom")
                labels = rows["symptom"].str.replace("_", " ").str.title()
                details = [
                    [row.reported_days, row.scheduled_days,
                     str(row.documented_episodes) if row.symptom == "vomiting" else "Not tracked",
                     str(row.excluded_count_days) if row.symptom == "vomiting" else "Not tracked"]
                    for row in rows.itertuples()
                ]
                weekly_chart.add_trace(go.Bar(
                    name=f"Week {week}", y=labels, x=rows["present_days"], orientation="h",
                    marker_color=week_colors[index % len(week_colors)], customdata=details,
                    hovertemplate=("%{y}<br>Symptom days: %{x}<br>Check-ins: %{customdata[0]} / %{customdata[1]}"
                                   "<br>Documented episodes: %{customdata[2]}<br>Excluded count days: %{customdata[3]}<extra>%{fullData.name}</extra>"),
                ))
            weekly_chart.update_layout(
                barmode="group", height=max(330, 55 * weekly["symptom"].nunique()),
                margin=dict(l=0, r=10, t=10, b=0), xaxis_title="Days symptom reported present",
                xaxis=dict(range=[0, 7.5], dtick=1), yaxis_title=None, legend_title_text=None,
                legend_orientation="h",
            )
            st.plotly_chart(readable_chart(weekly_chart), width="stretch")
            coverage = weekly.drop_duplicates("week").sort_values("week")
            st.caption("Check-ins submitted: " + " · ".join(
                f"Week {row.week}: {row.reported_days}/{row.scheduled_days}" for row in coverage.itertuples()
            ) + ". Missing, uncertain, and conflicting observations are not counted as symptom-present days.")

    st.subheader("Before and after a medication change")
    if comparison.empty:
        st.info("No regimen change recorded during this reporting period.")
    else:
        st.caption("Days with each symptom in the seven days before and after the change.")
        period_colors = {"before": "#246d65", "after": "#b0803b"}
        comparison_chart = go.Figure()
        period_columns = st.columns(2)
        for column, period in zip(period_columns, ("before", "after")):
            rows = comparison[comparison["period"] == period].sort_values("symptom")
            if rows.empty:
                continue
            first = rows.iloc[0]
            start_label = pd.Timestamp(first["start_date"]).strftime("%d %b")
            end_label = pd.Timestamp(first["end_date"]).strftime("%d %b %Y")
            column.markdown(f"**{period.title()} · {start_label}–{end_label}**")
            column.caption(f"Check-ins: {int(first['reported_days'])} / {int(first['scheduled_days'])}")
            vomiting_rows = rows[rows["symptom"] == "vomiting"]
            if not vomiting_rows.empty:
                column.metric("Documented vomiting episodes", int(vomiting_rows.iloc[0]["documented_episodes"]))
            comparison_chart.add_trace(go.Bar(
                name=period.title(), y=rows["symptom"].str.replace("_", " ").str.title(),
                x=rows["present_days"], orientation="h", marker_color=period_colors[period],
                hovertemplate="%{y}<br>Days present: %{x}<extra>%{fullData.name}</extra>",
            ))
        comparison_chart.update_layout(
            barmode="group", height=max(330, 55 * comparison["symptom"].nunique()),
            margin=dict(l=0, r=10, t=10, b=0), xaxis_title="Days symptom reported present",
            xaxis=dict(range=[0, 7.5], dtick=1), yaxis_title=None,
            legend_title_text=None, legend_orientation="h",
        )
        st.plotly_chart(readable_chart(comparison_chart), width="stretch")
        st.caption("The change day is excluded. Missing, uncertain, and conflicting observations are not counted as symptom-present days. This comparison is descriptive; it does not establish treatment effect.")

    st.subheader("Check-in details")
    selected_date = st.selectbox(
        "Check-in date", date_labels,
        format_func=lambda date: f"{pd.Timestamp(date).strftime('%d %b %Y')}" + (
            " — Not checked in" if date not in submitted_dates else ""
        ),
        key=f"checkin_date_{patient_id}",
    )
    selected = next((report for report in reports if report["report_date"] == selected_date), None)
    if selected is None:
        st.info("Not checked in. No questionnaire or patient message was submitted for this date.")
        st.stop()
    report_id = selected["report_id"]
    st.caption(f"Submitted: {pd.Timestamp(selected['submitted_at']).strftime('%d %b %Y at %H:%M')}")
    st.markdown("#### Questionnaire answers")
    questionnaire = decoded(selected["questionnaire_json"], {})
    questions = [
        ("Nausea severity", "reported_nausea_score_0_to_10", "/10"),
        ("Pain severity", "reported_pain_score_0_to_10", "/10"),
        ("Fatigue severity", "reported_fatigue_score_0_to_10", "/10"),
        ("Vomiting episodes", "reported_vomiting_episodes", ""),
        ("Swallowing", "reported_swallowing_status", ""),
        ("Weight", "reported_weight_lb", " lb"),
    ]
    for offset in (0, 3):
        for column, (label, field, unit) in zip(st.columns(3), questions[offset:offset + 3]):
            answer = questionnaire.get(field)
            rendered = f"{answer:g}" if isinstance(answer, (float, int)) else str(answer)
            column.metric(label, f"{rendered}{unit}" if answer is not None else "Not reported")
    st.markdown("#### Patient message")
    st.write(selected["raw_text"])
    observations = [dict(row) for row in conn.execute(
        "SELECT * FROM symptom_observations WHERE report_id=? ORDER BY source, symptom", (report_id,)
    )]
    display_rows = []
    for observation in observations:
        value = observation.get("severity_value")
        severity = observation.get("severity_text")
        if value is not None:
            severity = f"{value:g}/10" if observation.get("severity_scale") == "0-10" else str(value)
        details = [observation["presence"].capitalize()]
        if observation["episode_count"] is not None:
            count = observation["episode_count"]
            details.append(f"{count:g} {'episode' if count == 1 else 'episodes'}")
        if severity is not None:
            details.append(f"severity {severity}")
        if len(details) == 1 and observation["presence"] == "present":
            details.append("not quantified")
        symptom = observation["symptom"].replace("_", " ").capitalize()
        evidence = observation["evidence"]
        if observation["source"] == "questionnaire":
            evidence = (
                f"Patient entered {severity} for {symptom.lower()}." if severity is not None
                else f"Patient entered {observation['episode_count']:g} episodes."
                if observation["episode_count"] is not None else "Patient's questionnaire answer."
            )
        display_rows.append({
            "Source": "Patient text" if observation["source"] == "text" else "Questionnaire",
            "Symptom": symptom, "Reported value": " · ".join(details),
            "Observed date": observation["observed_date"] or "Date unclear",
            "Evidence": evidence,
            "Review notes": ", ".join(decoded(observation.get("issues_json"), [])),
        })
    display = pd.DataFrame(display_rows)
    if not display.empty and not display["Review notes"].any():
        display = display.drop(columns="Review notes")
    st.dataframe(display, hide_index=True, width="stretch")
    st.caption("Each daily check-in contains a questionnaire and patient text, shown separately. Severity uses a 0–10 scale. ‘Absent’ means the symptom was denied; ‘not quantified’ means it was mentioned without a severity or episode count. The two sources are not added together.")
    local_issues = decoded(selected.get("issues_json"), [])
    if selected.get("review_needed") or local_issues:
        st.warning("Some reported values need review. Check the patient's wording and review notes; unresolved counts are excluded from episode totals.")
    config = VerifierConfig.from_env()
    feedback = decoded(selected.get("verification_json"), {"status": "not_run"})
    if config.api_key:
        if st.button("Check interpretation", help="Send this check-in for automated review."):
            with st.spinner("Checking this report…"):
                feedback = verify_report(selected, observations, config=config)
            conn.execute("UPDATE reports SET verification_json=? WHERE report_id=?", (json.dumps(feedback), report_id))
            conn.commit()
    if feedback.get("status") == "agreed":
        st.info("Automated review found no discrepancies.")
    elif feedback.get("status") == "disagreements":
        st.info("Automated review flagged these items for review. Recorded values have not changed.")
        st.json(feedback["issues"])
    elif feedback.get("status") in ("unavailable", "invalid"):
        st.info("Automated review is unavailable. Recorded values have not changed.")
