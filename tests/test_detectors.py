# -*- coding: utf-8 -*-
"""Testi finti. Nessun dato reale."""

import unittest

from hideme.detectors import apply_entities


SAMPLE = """
Nome utente: mario.rossi
Email: mario.rossi@example.com
Instagram: https://instagram.com/mario.rossi
Posizione lavorativa: software engineer
È avvocato.
Salario: $85,000
RAL 42.000 €
Compenso GBP 70000
Telefono +1 415 555 0132 e +44 20 7946 0958
Abita in Via Roma 12, 20121 Milano
e al 1600 Amphitheatre Parkway
Hauptstraße 15
![ritratto](foto.jpg)
"""


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.out, self.mapping = apply_entities(SAMPLE)

    def test_placeholders_present(self):
        for label in ("USERNAME", "EMAIL", "SOCIAL", "JOBTITLE", "SALARY", "PHONE", "ADDRESS", "PHOTO"):
            self.assertIn(f"[{label}_", self.out, label)

    def test_values_removed_from_output(self):
        for secret in (
            "mario.rossi@example.com",
            "https://instagram.com/mario.rossi",
            "software engineer",
            "$85,000",
            "+1 415 555 0132",
            "+44 20 7946 0958",
            "Via Roma 12",
            "1600 Amphitheatre Parkway",
            "Hauptstraße 15",
            "foto.jpg",
        ):
            self.assertNotIn(secret, self.out, secret)

    def test_salary_survives_a_job_title_on_the_same_line(self):
        text = "Posizione lavorativa: software engineer. Salario: $85,000."
        out, _mapping = apply_entities(text)
        self.assertNotIn("$85,000", out)
        self.assertIn("[SALARY_", out)
        self.assertIn("[JOBTITLE_", out)

    def test_existing_placeholder_is_kept(self):
        text = "Già [FULLNAME_1], email altro@example.com"
        out, mapping = apply_entities(text)
        self.assertIn("[FULLNAME_1]", out)
        self.assertIn("[EMAIL_1]", out)
        self.assertNotIn("altro@example.com", out)
        self.assertNotIn("FULLNAME", mapping)


if __name__ == "__main__":
    unittest.main()
