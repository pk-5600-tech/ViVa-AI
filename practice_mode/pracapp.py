import json
import sys
from pathlib import Path

from flask import Flask, render_template, jsonify

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from video_analyzer import VideoAnalyzer
from speech_analyzer import SpeechAnalyzer
from metrics import calculate_metrics
from utils.paths import PRACTICE_RESULTS_PATH


app = Flask(__name__)


video = None
speech = None
recording = False

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/health")
def health():
    return jsonify({"status": "ready"})


@app.route("/start", methods=["GET", "POST"])
def start():
    global video, speech, recording
    if recording:
        return jsonify({"error": "A practice session is already running."}), 409
    try:
        video = VideoAnalyzer()
        speech = SpeechAnalyzer()
        video.start()
        speech.start_recording()
        recording = True
        return jsonify({"message": "Practice started"})
    except Exception as exc:
        if video is not None:
            try:
                video.stop()
            except Exception:
                pass
        video = None
        speech = None
        recording = False
        return jsonify({"error": str(exc)}), 503


@app.route("/stop", methods=["GET", "POST"])
def stop():
    global video, speech, recording
    if not recording or video is None or speech is None:
        return jsonify({"error": "No practice session is running."}), 409

    audio_file = None
    try:
        video.stop()
        audio_file = speech.stop_recording()
        if video.capture_error:
            raise RuntimeError(video.capture_error)
        speech_data = speech.analyze(audio_file)
        final = calculate_metrics(video.get_metrics(), speech_data)

        PRACTICE_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = PRACTICE_RESULTS_PATH.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(final, indent=2), encoding="utf-8")
        temporary_path.replace(PRACTICE_RESULTS_PATH)
        return jsonify(final)
    except Exception as exc:
        return jsonify({"error": f"Practice analysis failed: {exc}"}), 500
    finally:
        recording = False
        if speech is not None and speech.stream is not None:
            try:
                speech.stop_recording()
            except Exception:
                pass
        if video is not None and video.running:
            try:
                video.stop()
            except Exception:
                pass
        if audio_file:
            Path(audio_file).unlink(missing_ok=True)
        video = None
        speech = None


if __name__=="__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
