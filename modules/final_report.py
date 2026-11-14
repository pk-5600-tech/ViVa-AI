import streamlit as st
import plotly.graph_objects as go
import re
import json
import math
from utils.paths import PRACTICE_RESULTS_PATH


def _valid_percentage(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and 0 <= number <= 100 else None

def show_final_report():

    if st.button("🔄 Refresh Report"):
        st.rerun()

    st.header("📈 Final Performance Report")


    viva_history = st.session_state.get(
            "viva_history",
            []
        )


    presentation_metrics = {}
    if PRACTICE_RESULTS_PATH.exists():
        try:
            with PRACTICE_RESULTS_PATH.open("r", encoding="utf-8") as f:
                presentation_metrics = json.load(f)
            if not isinstance(presentation_metrics, dict):
                presentation_metrics = {}
        except (OSError, json.JSONDecodeError) as exc:
            st.warning(f"Practice results could not be read: {exc}")

    viva_score = None
    if viva_history:

        scores = []

        for item in viva_history:
            score = item.get("score")
            if isinstance(score, (int, float)) and not isinstance(score, bool) and 0 <= float(score) <= 10:
                scores.append(float(score))
                continue
            evaluation = item.get("evaluation", "")
            match = re.search(
                r'(?:score\s*[:\-]?\s*)?(\d+(?:\.\d+)?)\s*(?:/\s*10|out\s+of\s+10)',
                evaluation if isinstance(evaluation, str) else "",
                re.IGNORECASE,
            )
            if match:
                parsed_score = float(match.group(1))
                if 0 <= parsed_score <= 10:
                    scores.append(parsed_score)

        if scores:
            viva_score = (
                sum(scores)
                / len(scores)
            ) * 10


    # ----------------------------
    # Presentation Score
    # ----------------------------

    presentation_score = _valid_percentage(presentation_metrics.get("confidence_score"))

    # ----------------------------
    # Research Understanding
    # ----------------------------

    research_score = None

    # ----------------------------
    # Communication
    # ----------------------------

    communication_score = _valid_percentage(presentation_metrics.get("engagement_score"))

    available_scores = {
        "Viva": (viva_score, 0.25),
        "Presentation": (presentation_score, 0.25),
        "Communication": (communication_score, 0.15),
    }
    available_scores = {
        label: (float(score), weight)
        for label, (score, weight) in available_scores.items()
        if isinstance(score, (int, float)) and 0 <= float(score) <= 100
    }

    # ----------------------------
    # Overall
    # ----------------------------

    if available_scores:
        weight_total = sum(weight for _, weight in available_scores.values())
        overall_score = sum(score * weight for score, weight in available_scores.values()) / weight_total
    else:
        overall_score = None

    # ----------------------------
    # Overall Assessment
    # ----------------------------

    if overall_score is None:
        st.info("Readiness is unavailable until you complete a scored viva attempt or a presentation practice session.")
    elif overall_score >= 85:
        st.success(
            "🏆 Excellent Presentation Readiness"
        )

    elif overall_score >= 70:
        st.info(
            "✅ Good Presentation Readiness"
        )

    elif overall_score >= 50:
        st.warning(
            "⚠ Moderate Preparation"
        )

    else:
        st.error(
            "❌ More Practice Recommended"
        )

    # ----------------------------
    # Metrics
    # ----------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Research Understanding",
            "Not measured"
        )

    with col2:

        if not viva_history:

            st.metric(
                "Viva Score",
                "Not Attempted"
            )
        elif viva_score is None:
            st.metric("Viva Score", "Unavailable")

        else:

            st.metric(
                "Viva Score",
            f"{round(viva_score,1)}/100"
            )

    with col3:
        st.metric(
            "Overall Score",
            f"{round(overall_score,1)}/100" if overall_score is not None else "Unavailable"
        )

    with col4:
        st.metric(
            "Presentation Score",
            f"{round(presentation_score,1)}/100" if presentation_score is not None else "Unavailable"
        )

    st.markdown("---")

    # ----------------------------
    # Radar Chart
    # ----------------------------

    chart_scores = {}
    if viva_score is not None:
        chart_scores["Viva"] = viva_score
    if presentation_score is not None:
        chart_scores["Presentation"] = presentation_score
    if communication_score is not None:
        chart_scores["Communication"] = communication_score
    if chart_scores:
        fig = go.Figure(go.Scatterpolar(
            r=list(chart_scores.values()),
            theta=list(chart_scores.keys()),
            fill="toself",
            connectgaps=False,
        ))
        fig.update_layout(height=400, polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No measured scores are available for the readiness chart yet.")


    st.subheader(
    "📋 Performance Breakdown"
    )

    if viva_score is not None:
        st.progress(viva_score / 100)
        st.caption(f"Viva Performance: {round(viva_score,1)}%")
    if presentation_score is not None:
        st.progress(presentation_score / 100)
        st.caption(f"Presentation Confidence: {round(presentation_score,1)}%")
    if communication_score is not None:
        st.progress(communication_score / 100)
        st.caption(f"Communication Engagement: {round(communication_score,1)}%")
    st.caption("Research understanding: not measured by the current feature set.")

    # ----------------------------
    # Feedback
    # ----------------------------



