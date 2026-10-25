# -*- coding: utf-8 -*-
"""Anonimizza testo, PDF e immagini. Nessuna chiamata di rete."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pymupdf

from hideme.detectors import apply_entities
from hideme.session import Session, load, photo_path

MAX_BYTES = 20 * 1024 * 1024


def anonymize_text(text: str) -> tuple[str, dict]:
    """Scansiona l'intero testo con i controlli di HideMe."""
    return apply_entities(text)


def _is_image(data: bytes) -> bool:
    if data.startswith(b"\xff\xd8\xff") or data.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if data.startswith((b"GIF87a", b"GIF89a")):
        return True
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return True
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return True
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in {
        b"heic", b"heix", b"heif", b"mif1", b"msf1",
    }:
        return True
    return False


def _is_pdf(data: bytes) -> bool:
    return data.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"%PDF-")


def _mostly_text(text: str) -> bool:
    if not text:
        return True
    sample = text[:8192]
    bad = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\t\n\r")
    return bad / len(sample) < 0.02


def _binary_noise(data: bytes) -> bool:
    sample = data[:8192]
    if not sample or data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return False
    nul = sample.count(0)
    controls = sum(1 for byte in sample if byte < 9 or 13 < byte < 32)
    return nul / len(sample) > 0.05 or controls / len(sample) > 0.02


def _decode(data: bytes) -> str:
    """Legge il file come testo, qualunque sia l'estensione."""
    if not data:
        return ""
    if _is_image(data) or _is_pdf(data) or _binary_noise(data):
        raise RuntimeError("il file non è testo")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16").replace("\x00", "")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    if not _mostly_text(text):
        raise RuntimeError("il file non è testo")
    return text


def _redact_pdf(data: bytes, mapping: dict, session: Session) -> bytes:
    doc = pymupdf.open(stream=data, filetype="pdf")
    seen: set[int] = set()
    for page in doc:
        for img in list(page.get_images()):
            xref = img[0]
            if xref in seen:
                continue
            seen.add(xref)
            try:
                info = doc.extract_image(xref)
            except Exception:
                info = None
            if info and info.get("image"):
                session.add_photo(info["image"], str(info.get("ext") or "bin"))
            try:
                page.delete_image(xref)
            except Exception:
                pass
    items = sorted(mapping.items(), key=lambda kv: len(str(kv[1])), reverse=True)
    for placeholder, value in items:
        if not isinstance(value, str) or value.startswith("file:") or len(value.strip()) < 3:
            continue
        for page in doc:
            try:
                rects = page.search_for(value)
            except Exception:
                continue
            if not rects:
                continue
            for rect in rects:
                page.add_redact_annot(rect, text=placeholder, fill=(1, 1, 1))
            page.apply_redactions()
    out = doc.tobytes()
    doc.close()
    return out


def anonymize_path(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError("file non trovato")
    if path.stat().st_size > MAX_BYTES:
        raise RuntimeError("file troppo grande")
    data = path.read_bytes()
    session = Session()
    ext = path.suffix.lower()
    photos_removed = 0
    anonymized_pdf = None

    if _is_image(data):
        placeholder = session.add_photo(data, ext.lstrip(".") or "img")
        anonymized = placeholder
        photos_removed = 1
    else:
        if _is_pdf(data):
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                if doc.needs_pass:
                    raise RuntimeError("PDF protetto da password")
                text = "\n".join(page.get_text() for page in doc)
        else:
            text = _decode(data)
        anonymized, mapping = anonymize_text(text)
        session.mapping.update(mapping)
        if _is_pdf(data):
            before = len(session.photos)
            anonymized_pdf = _redact_pdf(data, session.mapping, session)
            photos_removed = len(session.photos) - before
            if photos_removed:
                note = " ".join(
                    key for key in session.mapping
                    if key.startswith("[PHOTO_") and key not in anonymized
                )
                if note:
                    anonymized = (anonymized.rstrip() + "\n" + note).strip()

    session.save(path.name)
    result = {
        "session_id": session.id,
        "anonymized_text": anonymized,
        "n_entities": len(session.mapping),
        "photos_removed": photos_removed,
    }
    if anonymized_pdf is not None:
        from hideme.session import _photo_dir, _write_private
        folder = _photo_dir(session.id)
        folder.mkdir(parents=True, exist_ok=True)
        os.chmod(folder, 0o700)
        _write_private(folder / "anonymized.pdf", anonymized_pdf)
        result["anonymized_pdf"] = str(folder / "anonymized.pdf")
    return result


def values_leaked(anonymized: str, mapping: dict) -> bool:
    for value in mapping.values():
        token = str(value).strip()
        if token.startswith("file:"):
            continue
        if len(token) >= 4 and token in anonymized:
            return True
        if 0 < len(token) < 4 and re.search(rf"(?<!\w){re.escape(token)}(?!\w)", anonymized):
            return True
    return False


def restore_to_file(session_id: str, text: str, output_path: Path) -> Path:
    record = load(session_id)
    mapping = record["mapping"]
    restored = text
    for key in sorted(mapping, key=len, reverse=True):
        value = str(mapping[key])
        if value.startswith("file:"):
            name = value.removeprefix("file:")
            src = photo_path(session_id, name)
            dest_dir = output_path.parent / f"{output_path.stem}.photos"
            dest_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(dest_dir, 0o700)
            target = dest_dir / name
            if src.is_file() and not target.exists():
                from hideme.session import _write_private
                _write_private(target, src.read_bytes())
            restored = restored.replace(key, f"[foto:{name}]")
        else:
            restored = restored.replace(key, value)
    home = Path.home().resolve()
    dest = output_path.expanduser().resolve()
    if home not in dest.parents:
        raise RuntimeError("il file di ripristino deve stare nella home")
    from hideme.session import _write_private
    _write_private(dest, restored.encode("utf-8"))
    return dest
