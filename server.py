import os
import subprocess
import tempfile
import time
import uuid

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY", "")
WHISPER_SERVER_URL = os.environ.get("WHISPER_SERVER_URL", "http://192.168.1.250:8788")
TEMP_DIR = "/tmp/whisp"

os.makedirs(TEMP_DIR, exist_ok=True)


def require_api_key(f):
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if not API_KEY or key != API_KEY:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return f(*args, **kwargs)

    decorated.__name__ = f.__name__
    return decorated


def download_audio(url, work_dir):
    """Download audio-only with yt-dlp, return (file_path, title)."""
    output_template = os.path.join(work_dir, "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "-o", output_template,
        "--print", "after_move:filepath",
        "--print", "%(title)s",
        "--no-warnings",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr.strip()}")

    lines = result.stdout.strip().split("\n")
    if len(lines) < 2:
        raise RuntimeError(f"yt-dlp unexpected output: {result.stdout.strip()}")

    filepath = lines[-2]
    title = lines[-1]
    return filepath, title


def convert_to_wav16k(input_path, work_dir):
    """Convert audio to 16kHz mono WAV for whisper."""
    output_path = os.path.join(work_dir, f"{uuid.uuid4().hex}.wav")
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()}")
    return output_path


def transcribe_audio(wav_path):
    """Send WAV to whisper-server and return transcript text."""
    with open(wav_path, "rb") as f:
        resp = requests.post(
            f"{WHISPER_SERVER_URL}/inference",
            files={"file": ("audio.wav", f, "audio/wav")},
            data={"response_format": "json", "temperature": "0.0"},
            timeout=1800,
        )
    resp.raise_for_status()
    return resp.json().get("text", "").strip()


def cleanup_dir(work_dir):
    """Remove all files in a work directory."""
    try:
        for f in os.listdir(work_dir):
            os.remove(os.path.join(work_dir, f))
        os.rmdir(work_dir)
    except OSError:
        pass


@app.route("/transcribe", methods=["POST"])
@require_api_key
def transcribe():
    body = request.get_json(silent=True) or {}
    url = body.get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "missing 'url' in request body"}), 400

    work_dir = os.path.join(TEMP_DIR, uuid.uuid4().hex)
    os.makedirs(work_dir, exist_ok=True)

    try:
        start = time.time()

        audio_path, title = download_audio(url, work_dir)
        wav_path = convert_to_wav16k(audio_path, work_dir)
        text = transcribe_audio(wav_path)

        duration = round(time.time() - start, 1)
        return jsonify({"ok": True, "title": title, "text": text, "duration": duration})

    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "download timed out"}), 504
    except requests.exceptions.Timeout:
        return jsonify({"ok": False, "error": "transcription timed out"}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"ok": False, "error": "whisper server unreachable"}), 502
    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        cleanup_dir(work_dir)


@app.route("/health", methods=["GET"])
def health():
    whisper_status = "unknown"
    try:
        resp = requests.get(WHISPER_SERVER_URL, timeout=5)
        whisper_status = "ok" if resp.status_code == 200 else f"http {resp.status_code}"
    except requests.exceptions.ConnectionError:
        whisper_status = "unreachable"
    except requests.exceptions.Timeout:
        whisper_status = "timeout"

    ok = whisper_status == "ok"
    status_code = 200 if ok else 503
    return jsonify({"status": "ok" if ok else "degraded", "whisper_server": whisper_status}), status_code
