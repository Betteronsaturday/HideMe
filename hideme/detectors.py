# -*- coding: utf-8 -*-
"""Rilevatori locali di HideMe.

Cercano email, telefoni, indirizzi, importi e ruoli nell'intero testo.
Nessuna chiamata di rete: i numeri passano da libphonenumber, già installata in locale.
"""

from __future__ import annotations

import re

from phonenumbers import PhoneNumberMatcher
from phonenumbers import Leniency

PLACEHOLDER = re.compile(r"\[[A-Z][A-Z0-9]*_\d+\]")

# Regioni usate solo come ipotesi per i numeri scritti senza prefisso internazionale.
# I numeri con + o 00 vengono riconosciuti in ogni regione.
PHONE_REGIONS = (
    "IT", "SM", "VA", "US", "CA", "GB", "IE", "DE", "AT", "CH", "FR", "BE", "NL",
    "ES", "PT", "LU", "SE", "NO", "DK", "FI", "PL", "CZ", "HU", "RO", "GR", "TR",
    "BR", "MX", "AR", "CL", "CO", "PE", "IN", "CN", "JP", "KR", "AU", "NZ", "ZA",
    "AE", "SA", "IL", "SG", "HK", "TH", "MY", "PH", "ID", "NG", "EG", "MA", "UA",
)

_NUM = r"(?:\d{1,3}(?:[ .,''\u00a0\u202f]\d{3})+|\d+)(?:[.,]\d{1,2})?"
_SYMBOL = r"(?:US\$|R\$|C\$|A\$|NZ\$|HK\$|S\$|[$€£¥₹₩₽₺₴฿₫₱₪])"
_CODE = (
    r"(?:USD|EUR|GBP|CHF|JPY|CAD|AUD|CNY|INR|BRL|MXN|SEK|NOK|DKK|PLN|CZK|HUF|"
    r"RON|ZAR|KRW|SGD|HKD|NZD|AED|SAR|ILS|THB|MYR|PHP|IDR|NGN|EGP|MAD|ARS|CLP|"
    r"COP|PEN|QAR|KWD|BHD|OMR|TWD|VND|UAH|BGN|TRY)"
)
_WORD = r"(?:euro|euros|dollari|dollars|sterline|pounds|yen|franchi|francs|reais)"
_MONEY = re.compile(
    rf"{_SYMBOL}\s*{_NUM}"
    rf"|{_NUM}\s*(?:{_SYMBOL}|{_CODE}\b|{_WORD}\b)"
    rf"|\b{_CODE}\s*{_NUM}"
    rf"|(?i:\b{_WORD}\b)\s*{_NUM}",
)
_SALARY_WORD = re.compile(
    r"(?i)\b(?:salari[oa]|stipendi[oa]|retribuzion[ei]|remunerazion[ei]|compenso|"
    r"emolumenti|paga(?:\s+lorda|\s+netta)?|ral|cedolino|"
    r"salary|salaries|wage|wages|compensation|remuneration|stipend|"
    r"base\s+pay|gross\s+pay|net\s+pay|pay\s+package|annual\s+salary|"
    r"gehalt|lohn|salaire|sueldo)\b"
)
_BARE_SALARY = re.compile(
    rf"(?i)\b(?:ral|stipendio|salario|salary|wage|sueldo|gehalt|salaire|compensation)"
    rf"\b\s*[:=]?\s*(?:di\s+|of\s+|da\s+)?{_NUM}\b"
)

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_USERNAME = re.compile(
    r"(?i)\b(?:nome\s+utente|username|user\s*name|userid|user\s*id|login|"
    r"account\s*name|nome\s+account|nickname|nick)\s*[:=]\s*@?([A-Za-z0-9._\-]{2,40})"
)
_HANDLE = re.compile(r"(?<![\w.+%\-])@[A-Za-z][\w.]{1,30}\b")
_SOCIAL_URL = re.compile(
    r"(?i)\b(?:https?://)?(?:www\.)?(?:[\w-]+\.)?"
    r"(?:linkedin\.com/in/|instagram\.com/|facebook\.com/|fb\.com/|"
    r"twitter\.com/|x\.com/|tiktok\.com/@?|github\.com/|"
    r"youtube\.com/(?:@|channel/|c/)|t\.me/|telegram\.me/|"
    r"snapchat\.com/add/|pinterest\.com/|reddit\.com/(?:user|u)/|"
    r"threads\.net/@|bsky\.app/profile/|wa\.me/)"
    r"[\w./?=#&%+\-]{1,80}"
)
_PHOTO_REF = re.compile(
    r"!\[[^\]]*\]\([^)\s]+\)"
    r"|<img\b[^>]*>"
    r"|\b[\w./\\-]+\.(?:jpg|jpeg|png|gif|webp|heic|heif|tif|tiff|bmp)\b",
    re.IGNORECASE,
)

_JOB_CONTEXT = re.compile(
    r"(?i)\b(?:posizione\s+lavorativa|job\s+title|job\s+position|qualifica|"
    r"mansione|in\s+qualità\s+di|impiegat[oa]\s+come|assunt[oa]\s+come|"
    r"works\s+as|employed\s+as|ruolo\s+di)\s*[:=]?\s*"
    r"([A-Za-zÀ-ÿ][\w'’/&+\-]*(?:[ \t]+[A-Za-zÀ-ÿ][\w'’/&+\-]*){0,4})"
)

# Frasi intere, dalle più lunghe. Niente parole isolate troppo generiche
# ("manager", "director"): finirebbero dentro frasi che non sono un ruolo.
_TITLES = (
    "chief executive officer", "chief financial officer", "chief technology officer",
    "amministratore delegato", "direttore generale", "direttore commerciale",
    "direttore del personale", "consulente del lavoro", "medico chirurgo",
    "impiegato amministrativo", "impiegata amministrativa", "operaio specializzato",
    "operaia specializzata", "responsabile marketing", "responsabile vendite",
    "responsabile risorse umane", "sviluppatore software", "ingegnere informatico",
    "analista programmatore", "software engineer", "data scientist", "product manager",
    "project manager", "account manager", "sales manager", "hr manager",
    "general manager", "customer success manager",
    "commercialista", "avvocato", "avvocata", "notaio", "infermiere", "infermiera",
    "insegnante", "professore", "professoressa", "ricercatore", "ricercatrice",
    "programmatore", "programmatrice", "sviluppatore", "sviluppatrice",
    "contabile", "cassiere", "cassiera", "commesso", "commessa", "cameriere",
    "cameriera", "cuoco", "cuoca", "chef", "autista", "magazziniere", "magazziniera",
    "geometra", "architetto", "architetta", "ingegnere", "giornalista",
    "farmacista", "psicologo", "psicologa", "psicoterapeuta", "fisioterapista",
    "elettricista", "idraulico", "muratore", "receptionist", "segretaria", "segretario",
    "ceo", "cfo", "cto", "coo", "cmo",
    "nurse", "accountant", "lawyer", "attorney", "physician", "surgeon",
    "pharmacist", "architect", "journalist",
)
_TITLE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in sorted(_TITLES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

_ADDRESS_RES = (
    # Italiano: Via / Viale / Piazza / Corso + nome, con civico e CAP facoltativi.
    re.compile(
        r"\b(?:[Vv]ia|[Vv]iale|[Vv]\.le|[Pp]iazza|[Pp]\.zza|[Cc]orso|[Cc]\.so|"
        r"[Ll]argo|[Vv]icolo|[Ss]trada|[Ll]ungotevere|[Ll]ungomare)\s+"
        r"[A-ZÀ-ÖØ-Þ][\w'’.\-]+(?:\s+[A-ZÀ-ÖØ-Þ][\w'’.\-]+){0,3}"
        r"(?:\s*,?\s*(?:n\.?|numero)?\s*\d{1,4}[A-Za-z]?)?"
        r"(?:\s*,?\s*\d{5})?"
        r"(?:\s+[A-ZÀ-ÖØ-Þ][\w'’.\-]+){0,2}"
    ),
    # Inglese e internazionale: 1600 Amphitheatre Parkway
    re.compile(
        r"\b\d{1,6}\s+(?:[A-Z][\w'’.\-]{1,30}\s+){0,4}"
        r"(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|Lane|Ln\.?|"
        r"Drive|Dr\.?|Way|Court|Ct\.?|Place|Pl\.?|Terrace|Crescent|Square|"
        r"Gardens|Parkway|Pkwy\.?|Highway|Hwy\.?|Route|Rt\.?)\b"
        r"(?:\s*,\s*[A-Z][\w'’.\-]+(?:\s+[A-Z][\w'’.\-]+){0,3})?"
        r"(?:\s*,?\s*[A-Z]{2})?"
        r"(?:\s+\d{5}(?:-\d{4})?)?"
        r"(?:\s+[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})?"
    ),
    # Francese
    re.compile(
        r"\b(?:\d{1,4}\s*,?\s*)?(?:rue|avenue|boulevard|impasse|allée|chemin)\s+"
        r"(?:de\s+|du\s+|des\s+|la\s+|le\s+|d'|l')?[A-ZÀ-ÖØ-Þ][\w'’\-]+"
        r"(?:\s+[A-ZÀ-ÖØ-Þ][\w'’\-]+){0,3}",
    ),
    # Tedesco: Hauptstraße 15
    re.compile(
        r"\b[A-ZÄÖÜ][\w\-]*(?:straße|strasse|str\.)\s+\d{1,4}[a-z]?\b"
    ),
    # Spagnolo / portoghese
    re.compile(
        r"\b(?:[Cc]alle|[Cc]arrera|[Aa]venida|[Aa]vda\.|[Pp]aseo|[Cc]amino|"
        r"[Rr]ua|[Aa]venida)\s+"
        r"(?:de\s+|del\s+|de\s+la\s+)?[A-ZÁÉÍÓÚÑÜ][\w'’.\-]+"
        r"(?:\s+[A-ZÁÉÍÓÚÑÜ][\w'’.\-]+){0,3}"
        r"(?:\s*,?\s*(?:nº|n°|no\.?|#)?\s*\d{1,5})?"
    ),
)


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < b and end > a for a, b in spans)


def _keep(spans: list[dict], protected: list[tuple[int, int]]) -> list[dict]:
    """Tiene gli span più lunghi. A parità di lunghezza vince la priorità."""
    rank = {
        "PHOTO": 0, "EMAIL": 1, "SOCIAL": 2, "USERNAME": 3, "PHONE": 4,
        "SALARY": 5, "ADDRESS": 6, "JOBTITLE": 7, "CURRENCY": 8,
    }
    ordered = sorted(
        spans,
        key=lambda s: (-(s["end"] - s["start"]), rank.get(s["label"], 9), s["start"]),
    )
    chosen: list[dict] = []
    taken = list(protected)
    for span in ordered:
        if span["end"] <= span["start"]:
            continue
        if _overlaps(span["start"], span["end"], taken):
            continue
        chosen.append(span)
        taken.append((span["start"], span["end"]))
    chosen.sort(key=lambda s: s["start"])
    return chosen


def _add(out: list[dict], label: str, start: int, end: int, text: str) -> None:
    value = text[start:end]
    if not value.strip():
        return
    out.append({"label": label, "start": start, "end": end, "value": value})


def _phones(text: str, out: list[dict]) -> None:
    seen: list[tuple[int, int]] = []
    for region in PHONE_REGIONS:
        try:
            matches = PhoneNumberMatcher(text, region, leniency=Leniency.VALID)
        except Exception:
            continue
        for match in matches:
            if match.end - match.start < 8:
                continue
            if _overlaps(match.start, match.end, seen):
                continue
            digits = re.sub(r"\D", "", match.raw_string)
            if len(digits) < 8 or len(digits) > 15:
                continue
            seen.append((match.start, match.end))
            _add(out, "PHONE", match.start, match.end, text)


def _money(text: str, out: list[dict]) -> None:
    amounts = [(m.start(), m.end()) for m in _MONEY.finditer(text)]
    keywords = [(m.start(), m.end()) for m in _SALARY_WORD.finditer(text)]
    used: list[tuple[int, int]] = []
    for start, end in amounts:
        near = None
        for ks, ke in keywords:
            if abs(start - ke) <= 80 or abs(ks - end) <= 80:
                chunk_a, chunk_b = min(start, ks), max(end, ke)
                if "\n" not in text[chunk_a:chunk_b]:
                    near = (chunk_a, chunk_b)
                    break
        if near:
            _add(out, "SALARY", near[0], near[1], text)
            _add(out, "SALARY", start, end, text)
            used.append(near)
        else:
            _add(out, "CURRENCY", start, end, text)
    for match in _BARE_SALARY.finditer(text):
        if _overlaps(match.start(), match.end(), used):
            continue
        _add(out, "SALARY", match.start(), match.end(), text)


def _jobs(text: str, out: list[dict]) -> None:
    for match in _TITLE_RE.finditer(text):
        _add(out, "JOBTITLE", match.start(), match.end(), text)
    for match in _JOB_CONTEXT.finditer(text):
        value = match.group(1).strip(" .,;:")
        if len(value) < 2:
            continue
        start = match.start(1)
        end = start + len(value)
        _add(out, "JOBTITLE", start, end, text)


def find_entities(text: str) -> list[dict]:
    """Entità HideMe che non cadono sopra un segnaposto già presente."""
    protected = [(m.start(), m.end()) for m in PLACEHOLDER.finditer(text)]
    found: list[dict] = []
    for match in _EMAIL.finditer(text):
        _add(found, "EMAIL", match.start(), match.end(), text)
    for match in _SOCIAL_URL.finditer(text):
        _add(found, "SOCIAL", match.start(), match.end(), text)
    for match in _HANDLE.finditer(text):
        _add(found, "SOCIAL", match.start(), match.end(), text)
    for match in _USERNAME.finditer(text):
        value = match.group(1)
        start, end = match.start(1), match.end(1)
        if "@" in value and "." in value.split("@")[-1]:
            _add(found, "EMAIL", start, end, text)
        else:
            _add(found, "USERNAME", match.start(), match.end(), text)
    for pattern in _ADDRESS_RES:
        for match in pattern.finditer(text):
            _add(found, "ADDRESS", match.start(), match.end(), text)
    _phones(text, found)
    _money(text, found)
    _jobs(text, found)
    for match in _PHOTO_REF.finditer(text):
        _add(found, "PHOTO", match.start(), match.end(), text)
    return _keep(found, protected)


def apply_entities(text: str, entities: list[dict] | None = None) -> tuple[str, dict]:
    """Sostituisce le entità con [ETICHETTA_N], continuando la numerazione già usata."""
    entities = find_entities(text) if entities is None else entities
    counters: dict[str, int] = {}
    for label in {e["label"] for e in entities}:
        nums = [int(n) for n in re.findall(rf"\[{label}_(\d+)\]", text)]
        counters[label] = max(nums, default=0)
    mapping: dict[str, str] = {}
    tagged = []
    for entity in entities:
        counters[entity["label"]] += 1
        placeholder = f"[{entity['label']}_{counters[entity['label']]}]"
        tagged.append((entity["start"], entity["end"], placeholder, entity["value"]))
        mapping[placeholder] = entity["value"]
    out = text
    for start, end, placeholder, _value in reversed(tagged):
        out = out[:start] + placeholder + out[end:]
    return out, mapping
