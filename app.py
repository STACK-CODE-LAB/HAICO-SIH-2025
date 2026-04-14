"""
app.py
======
Flask backend for the Polaris Obfuscator Web UI.

Routes
------
GET  /                      Serve frontend
POST /upload                Accept source file + options, run pipeline
GET  /status/<job_id>       Poll job status
GET  /report/<job_id>       Full JSON report
GET  /download/<job_id>     Download obfuscated binary
"""

import json
import os
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_file, render_template

import ai_enhancer
import obfuscator
import report as report_builder
import config

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = config.UPLOAD_FOLDER
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

# In-memory job store  { job_id: { "status": str, "report": dict | None } }
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in config.ALLOWED_EXTS


def _run_pipeline(job_id: str, src_path: str, filename: str, passes: str):
    """Background thread: AI enhance → obfuscate → build report."""
    job_dir = str(Path(config.UPLOAD_FOLDER) / job_id)

    try:
        # ── 1. AI Enhancement ─────────────────────────────────────────────────
        with _jobs_lock:
            _jobs[job_id]["status"] = "ai_enhancing"

        with open(src_path, "r", errors="replace") as f:
            original_source = f.read()

        ai_result = ai_enhancer.enhance(original_source, filename)

        # Write enhanced source to disk (used for compilation)
        enhanced_path = str(Path(job_dir) / f"enhanced_{filename}")
        with open(enhanced_path, "w") as f:
            f.write(ai_result["enhanced_source"])

        # ── 2. Obfuscation ────────────────────────────────────────────────────
        with _jobs_lock:
            _jobs[job_id]["status"] = "compiling"

        obfu_result = obfuscator.run_pipeline(
            src=enhanced_path,
            job_dir=job_dir,
            passes=passes,
        )

        # ── 3. Build Report ───────────────────────────────────────────────────
        final_report = report_builder.build(
            ai_result=ai_result,
            obfu_result=obfu_result,
            original_filename=filename,
            passes_used=passes or config.DEFAULT_PASSES,
        )

        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["report"] = final_report

    except Exception as exc:
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["report"] = {
                "verdict": "ERROR",
                "error":   str(exc),
            }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def index():
    return render_template("index.html")


@app.post("/upload")
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    f = request.files["file"]
    if not f.filename or not _allowed(f.filename):
        return jsonify({"error": "Only .c and .cpp files are accepted"}), 400

    passes  = request.form.get("passes", "").strip()
    job_id  = uuid.uuid4().hex
    job_dir = Path(config.UPLOAD_FOLDER) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save original upload
    src_path = str(job_dir / f.filename)
    f.save(src_path)

    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "report": None}

    # Kick off background pipeline
    t = threading.Thread(
        target=_run_pipeline,
        args=(job_id, src_path, f.filename, passes),
        daemon=True,
    )
    t.start()

    return jsonify({"job_id": job_id}), 202


@app.get("/status/<job_id>")
def status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({"job_id": job_id, "status": job["status"]})


@app.get("/report/<job_id>")
def get_report(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] not in ("done", "error"):
        return jsonify({"error": "Report not ready yet", "status": job["status"]}), 202
    return jsonify(job["report"])


@app.get("/download/<job_id>")
def download(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] != "done":
        return jsonify({"error": "Not ready"}), 202

    obfu_bin = Path(config.UPLOAD_FOLDER) / job_id / "obfu_out"
    if not obfu_bin.exists():
        return jsonify({"error": "Binary not found"}), 404

    return send_file(
        str(obfu_bin),
        as_attachment=True,
        download_name="obfuscated_binary",
        mimetype="application/octet-stream",
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
    )