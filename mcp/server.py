#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP stdio di HideMe. Nessuna chiamata di rete."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hideme.anonymize import anonymize_path, restore_to_file, values_leaked
from hideme.session import SESSIONS, load

PROTOCOL = "2024-11-05"


def _send(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _ok(req_id, result: dict) -> None:
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _tool(text: str, is_error: bool = False) -> dict:
    out = {"content": [{"type": "text", "text": text}]}
    if is_error:
        out["isError"] = True
    return out


def anonimizza_file(path_str: str) -> dict:
    result = anonymize_path(Path(path_str).expanduser())
    record = load(result["session_id"])
    if values_leaked(result["anonymized_text"], record["mapping"]):
        raise RuntimeError("anonimizzazione incompleta: output non restituito")
    return {
        "session_id": result["session_id"],
        "anonymized_text": result["anonymized_text"],
        "photos_removed": result["photos_removed"],
    }


def ripristina(session_id: str, testo: str, output_path: str | None) -> dict:
    if output_path:
        dest = Path(output_path).expanduser()
    else:
        dest = SESSIONS / f"{session_id}.restored.txt"
    path = restore_to_file(session_id, testo, dest)
    return {
        "session_id": session_id,
        "output_path": str(path),
        "bytes": path.stat().st_size,
        "note": "Testo ripristinato scritto su file. Il contenuto non è in questa risposta.",
    }


TOOLS = [
    {
        "name": "anonimizza_file",
        "description": (
            "Anonimizza un file locale con HideMe. Restituisce solo il testo "
            "anonimizzato e l'id sessione. Il dizionario resta in "
            "~/.local/share/hideme/sessions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Percorso del file sul disco."}
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ripristina",
        "description": (
            "Ripristina i valori di una sessione HideMe e li scrive su file. "
            "Usare solo se l'utente lo chiede. Non include il testo ripristinato."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "testo": {"type": "string", "description": "Testo con i segnaposto."},
                "output_path": {"type": "string"},
            },
            "required": ["session_id", "testo"],
            "additionalProperties": False,
        },
    },
]


def _call(name: str, arguments: dict) -> dict:
    if name == "anonimizza_file":
        result = anonimizza_file(str(arguments.get("path") or ""))
    elif name == "ripristina":
        result = ripristina(
            str(arguments.get("session_id") or ""),
            str(arguments.get("testo") or ""),
            arguments.get("output_path"),
        )
    else:
        raise RuntimeError(f"tool sconosciuto: {name}")
    return _tool(json.dumps(result, ensure_ascii=False))


def _handle(msg: dict) -> None:
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}
    if method in ("notifications/initialized", "initialized") or req_id is None:
        return
    if method == "initialize":
        _ok(req_id, {
            "protocolVersion": params.get("protocolVersion") or PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "HideMe", "version": "0.1.0"},
            "instructions": (
                "Anonimizza in locale. Non chiamare ripristina se l'utente non lo chiede. "
                "Non leggere i file di sessione né i file ripristinati."
            ),
        })
        return
    if method == "ping":
        _ok(req_id, {})
        return
    if method == "tools/list":
        _ok(req_id, {"tools": TOOLS})
        return
    if method == "tools/call":
        try:
            _ok(req_id, _call(params.get("name"), params.get("arguments") or {}))
        except Exception as exc:
            _ok(req_id, _tool(str(exc), is_error=True))
        return
    _send({
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": "method non supportato"},
    })


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(msg, dict):
            _handle(msg)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
