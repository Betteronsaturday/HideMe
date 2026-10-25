# -*- coding: utf-8 -*-
"""Sessioni locali. Il dizionario non esce da ~/.local/share/hideme."""

from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

SESSIONS = Path.home() / ".local" / "share" / "hideme" / "sessions"
SESSION_ID_RE = re.compile(r"^[a-f0-9]{32}$")

os.umask(0o077)


def _write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    os.chmod(path, 0o600)


def _session_json(session_id: str) -> Path:
    if not SESSION_ID_RE.fullmatch(session_id):
        raise RuntimeError("session_id non valido")
    root = SESSIONS.resolve()
    path = (root / f"{session_id}.json").resolve()
    if path.parent != root:
        raise RuntimeError("percorso sessione rifiutato")
    return path


def _photo_dir(session_id: str) -> Path:
    root = SESSIONS.resolve()
    path = (root / session_id).resolve()
    if path.parent != root:
        raise RuntimeError("percorso foto rifiutato")
    return path


class Session:
    def __init__(self) -> None:
        SESSIONS.mkdir(parents=True, exist_ok=True)
        os.chmod(SESSIONS, 0o700)
        self.id = secrets.token_hex(16)
        self.mapping: dict[str, str] = {}
        self.photos: list[str] = []

    def add_photo(self, data: bytes, ext: str) -> str:
        ext = re.sub(r"[^a-z0-9]", "", ext.lower()) or "bin"
        number = 1 + sum(1 for key in self.mapping if key.startswith("[PHOTO_"))
        name = f"photo_{number}.{ext}"
        folder = _photo_dir(self.id)
        folder.mkdir(parents=True, exist_ok=True)
        os.chmod(folder, 0o700)
        _write_private(folder / name, data)
        placeholder = f"[PHOTO_{number}]"
        self.mapping[placeholder] = f"file:{name}"
        self.photos.append(name)
        return placeholder

    def save(self, source_name: str) -> None:
        record = {
            "session_id": self.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_name": source_name,
            "mapping": self.mapping,
            "photos": self.photos,
        }
        _write_private(
            _session_json(self.id),
            json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8"),
        )


def load(session_id: str) -> dict:
    path = _session_json(session_id)
    if not path.is_file():
        raise RuntimeError("sessione non trovata")
    record = json.loads(path.read_text("utf-8"))
    if not isinstance(record, dict) or not isinstance(record.get("mapping"), dict):
        raise RuntimeError("sessione illeggibile")
    return record


def photo_path(session_id: str, name: str) -> Path:
    if not re.fullmatch(r"photo_\d+\.[a-z0-9]+", name):
        raise RuntimeError("nome foto rifiutato")
    folder = _photo_dir(session_id)
    path = (folder / name).resolve()
    if path.parent != folder.resolve():
        raise RuntimeError("percorso foto rifiutato")
    return path
