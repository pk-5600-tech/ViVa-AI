
import sys
import os
import json
import hashlib
from pathlib import Path

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from flask import Flask, render_template, jsonify, request
from llm.client import LLMError, chat
from utils.paths import PAPER_CONTEXT_PATH

current_question = ""
current_paper_fingerprint = None

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("viva.html")


@app.route("/generate_question")
def generate_question():
    global current_question, current_paper_fingerprint

    try:
        if not PAPER_CONTEXT_PATH.is_file():
            return jsonify({"error": "No uploaded paper is available. Upload and index a paper in ViVaMaTe AI first."}), 400
        with open(PAPER_CONTEXT_PATH, "r", encoding="utf-8") as f:
            paper_data = json.load(f)

        full_text = paper_data.get("paper_text", "")
        if not full_text.strip():
            return jsonify({"error": "The latest paper contains no readable text."}), 422
        paper_text = full_text[:10000]

        prompt = f"""
You are an experienced academic viva examiner.

Based on this document, ask ONE realistic viva question.

Document:
{paper_text}

Return ONLY the question.
"""

        question = chat(
            system_prompt="You are a strict academic viva examiner.",
            messages=[{"role": "user", "content": prompt}]
        ).strip()
        if not question:
            return jsonify({"error": "The AI examiner returned an empty question. Please retry."}), 502

        current_question = question
        current_paper_fingerprint = hashlib.sha256(full_text.encode("utf-8")).hexdigest()

        return jsonify({"question": question, "paper_name": paper_data.get("paper_name", "Uploaded paper")})

    except LLMError as exc:
        return jsonify({"error": str(exc)}), 502
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        app.logger.exception("Could not load the current paper for voice viva")
        return jsonify({"error": "The current paper could not be loaded. Re-upload it and try again."}), 500


@app.route("/start")
def start():
    return jsonify({"message": "Voice recognition ready"})


@app.route("/stop", methods=["POST"])
def stop():
    global current_question, current_paper_fingerprint

    try:
        data = request.get_json(silent=True) or {}
        transcript = data.get("transcript", "")
        if not isinstance(transcript, str):
            return jsonify({"error": "Transcript must be plain text."}), 400
        transcript = transcript.strip()

        if not current_question:
            return jsonify({"error": "Generate a question first."}), 400

        try:
            latest_paper = json.loads(PAPER_CONTEXT_PATH.read_text(encoding="utf-8"))
            latest_fingerprint = hashlib.sha256(latest_paper.get("paper_text", "").encode("utf-8")).hexdigest()
        except (OSError, json.JSONDecodeError, AttributeError):
            return jsonify({"error": "The current paper is unavailable. Re-upload it and generate a new question."}), 409
        if latest_fingerprint != current_paper_fingerprint:
            current_question = ""
            current_paper_fingerprint = None
            return jsonify({"error": "The uploaded paper changed. Generate a new viva question before answering."}), 409

        if not transcript:
            return jsonify({"error": "No answer transcript received."}), 400

        evaluation_prompt = f"""
Question:
{current_question}

Student Answer:
{transcript}

Evaluate this viva answer.

Provide:
1. Score out of 10
2. Strengths
3. Weaknesses
4. Better Answer

Use markdown.
"""

        evaluation = chat(
            system_prompt="You are a strict academic viva examiner.",
            messages=[{"role": "user", "content": evaluation_prompt}]
        )

        return jsonify({
            "transcript": transcript,
            "evaluation": evaluation
        })

    except LLMError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception:
        app.logger.exception("Voice viva answer evaluation failed")
        return jsonify({"error": "The viva answer could not be evaluated. Please retry."}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", debug=False, port=5001)
