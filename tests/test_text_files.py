# -*- coding: utf-8 -*-
"""File di testo con estensioni diverse. Dati finti."""

import tempfile
import unittest
from pathlib import Path

from hideme.anonymize import anonymize_path
from hideme.session import SESSIONS

BODY = "Email: mario.rossi@example.com\n"
JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


class TextFileTests(unittest.TestCase):
    def setUp(self):
        self.sessions: list[str] = []

    def tearDown(self):
        for session_id in self.sessions:
            (SESSIONS / f"{session_id}.json").unlink(missing_ok=True)
            folder = SESSIONS / session_id
            if folder.is_dir():
                for child in folder.iterdir():
                    child.unlink(missing_ok=True)
                folder.rmdir()

    def _run(self, name: str, data: bytes) -> dict:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / name
            path.write_bytes(data)
            result = anonymize_path(path)
        self.sessions.append(result["session_id"])
        return result

    def test_any_text_extension(self):
        names = (
            "note.csv",
            "note.json",
            "note.html",
            "note.xml",
            "note.log",
            "note.eml",
            "note.vcf",
            "note.yml",
            "note",
            "archivio.custom",
            "NOTE.TXT",
        )
        for name in names:
            result = self._run(name, BODY.encode("utf-8"))
            self.assertIn("[EMAIL_1]", result["anonymized_text"], name)
            self.assertNotIn("mario.rossi@example.com", result["anonymized_text"], name)

    def test_jpeg_renamed_as_text_stays_a_photo(self):
        result = self._run("pagina.csv", JPEG)
        self.assertEqual(result["anonymized_text"], "[PHOTO_1]")
        self.assertEqual(result["photos_removed"], 1)

    def test_binary_is_rejected(self):
        with self.assertRaises(RuntimeError):
            self._run("file.docx", b"PK\x03\x04" + b"\x00" * 80)
