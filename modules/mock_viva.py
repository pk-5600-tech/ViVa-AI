import re

import streamlit as st
from llm.client import LLMError, chat

PERSONAS = ["Professor", "Industry Expert", "Interviewer", "Skeptic", "Student"]


def extract_viva_score(evaluation):
    match = re.search(
        r"(?:score\s*[:\-]?\s*)?(\d+(?:\.\d+)?)\s*(?:/\s*10|out\s+of\s+10)",
        evaluation or "",
        re.IGNORECASE,
    )
    if not match:
        return None
    score = float(match.group(1))
    return score if 0 <= score <= 10 else None


def show_mock_viva():
    paper = st.session_state.get("paper_context")
    if not paper:
        st.warning("Upload a paper first.")
        return

    st.session_state.setdefault("viva_history", [])
    st.session_state.setdefault("viva_question", None)
    st.session_state.setdefault("viva_question_persona", None)
    st.session_state.setdefault("answer_transcript", "")

    st.header("🎓 Mock Viva")
    persona = st.selectbox("Choose Examiner Persona", PERSONAS)

    if st.button("Generate Viva Question"):
        prompt = f"""
You are acting as a {persona}.

Based on the following research paper, ask ONE realistic viva question.

Paper:
{paper['full_text'][:10000]}

Return only the question.
"""
        try:
            question = chat(
                system_prompt="You are an experienced viva examiner.",
                messages=[{"role": "user", "content": prompt}],
            )
        except LLMError as exc:
            st.error(str(exc))
        else:
            st.session_state.viva_question = question.strip()
            st.session_state.viva_question_persona = persona
            st.session_state.answer_transcript = ""

    question = st.session_state.viva_question
    if question:
        st.markdown("### 🎤 Viva Question")
        st.info(question)
        answer = st.text_area(
            "📝 Your answer",
            height=150,
            key="answer_transcript",
        )
        if st.button("Evaluate Answer"):
            if not answer.strip():
                st.warning("Enter an answer before requesting feedback.")
            else:
                evaluation_prompt = f"""
Question:
{question}

Student Answer:
{answer}

Evaluate the answer. Provide a score out of 10, strengths, weaknesses,
and a suggested better answer. Use markdown.
"""
                try:
                    evaluation = chat(
                        system_prompt="You are a strict academic evaluator.",
                        messages=[{"role": "user", "content": evaluation_prompt}],
                    )
                except LLMError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.viva_history.append({
                        "persona": st.session_state.viva_question_persona or persona,
                        "question": question,
                        "answer": answer,
                        "evaluation": evaluation,
                        "score": extract_viva_score(evaluation),
                    })

    history = st.session_state.viva_history
    if history:
        latest = history[-1]
        st.markdown("### Latest feedback")
        if latest.get("score") is not None:
            st.metric("Viva score", f"{latest['score']}/10")
        else:
            st.caption("No numeric score was found in this evaluation.")
        st.markdown(latest["evaluation"])
        with st.expander("Previous Viva Attempts"):
            for attempt in reversed(history[:-1]):
                score = attempt.get("score")
                st.markdown(f"**{score}/10**" if score is not None else "**Score unavailable**")
                st.markdown(attempt["evaluation"])
                st.divider()
