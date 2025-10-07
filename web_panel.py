from flask import Flask, render_template, request, jsonify
import subprocess
import json
import os

app = Flask(__name__)

QUEUE_FILE = "queue.json"

@app.route("/")
def index():
    return "<h1>TS3 Music Bot API</h1><p>Use /queue, /play, /skip, etc.</p>"

@app.route("/queue")
def show_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r") as f:
            queue_data = json.load(f)
    else:
        queue_data = []
    return jsonify(queue_data)

@app.route("/play", methods=["POST"])
def play_url():
    url = request.form.get("url")
    if url:
        # Отправляем команду через TS3 Query
        subprocess.run([
            "ts3query",
            "sendtextmessage",
            "targetmode=2",
            f"msg=!play {url}"
        ])
        return jsonify({"status": "added", "url": url})
    return jsonify({"error": "URL is required"}), 400

@app.route("/skip", methods=["POST"])
def skip_track():
    subprocess.run([
        "ts3query",
        "sendtextmessage",
        "targetmode=2",
        "msg=!skip"
    ])
    return jsonify({"status": "skipped"})

@app.route("/stop", methods=["POST"])
def stop_bot():
    subprocess.run([
        "ts3query",
        "sendtextmessage",
        "targetmode=2",
        "msg=!stop"
    ])
    return jsonify({"status": "stopped"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)