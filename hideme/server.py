# -*- coding: utf-8 -*-
"""Server locale di HideMe. Ascolta solo su 127.0.0.1."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request

from hideme.anonymize import anonymize_path, anonymize_text, values_leaked
from hideme.session import Session, load

HOST = "127.0.0.1"
DEFAULT_PORT = 5006
MAX_BYTES = 20 * 1024 * 1024
PAGE = Path(__file__).with_name("index.html")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES


def _public(session: Session, anonymized: str, photos_removed: int) -> dict:
    if values_leaked(anonymized, session.mapping):
        raise RuntimeError("anonymization incomplete: output withheld")
    return {
        "session_id": session.id,
        "anonymized_text": anonymized,
        "n_entities": len(session.mapping),
        "photos_removed": photos_removed,
    }


@app.route("/")
def home():
    html = PAGE.read_text(encoding="utf-8")
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "host": HOST,
        "port": app.config.get("HIDEME_PORT", DEFAULT_PORT),
    })


@app.route("/analyze", methods=["POST"])
def analyze():
    upload = request.files.get("file")
    try:
        if upload is not None and upload.filename:
            suffix = Path(upload.filename).suffix
            data = upload.read()
            if len(data) > MAX_BYTES:
                return jsonify({"error": "file too large"}), 400
            fd, name = tempfile.mkstemp(suffix=suffix or ".bin")
            os.close(fd)
            tmp = Path(name)
            try:
                tmp.write_bytes(data)
                result = anonymize_path(tmp)
            finally:
                tmp.unlink(missing_ok=True)
            record = load(result["session_id"])
            if values_leaked(result["anonymized_text"], record["mapping"]):
                return jsonify({"error": "anonymization incomplete"}), 400
            return jsonify({
                "session_id": result["session_id"],
                "anonymized_text": result["anonymized_text"],
                "n_entities": result["n_entities"],
                "photos_removed": result["photos_removed"],
            })
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text") or "")
        if not text.strip():
            return jsonify({"error": "no text"}), 400
        anonymized, mapping = anonymize_text(text)
        session = Session()
        session.mapping.update(mapping)
        session.save("testo")
        return jsonify(_public(session, anonymized, 0))
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400


def main() -> None:
    parser = argparse.ArgumentParser(description="HideMe, anonimizzazione locale")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    if args.host != HOST:
        print("HideMe listens only on 127.0.0.1", file=sys.stderr)
        sys.exit(2)
    app.config["HIDEME_PORT"] = args.port
    print(f"HideMe at http://{HOST}:{args.port}")
    app.run(host=HOST, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
