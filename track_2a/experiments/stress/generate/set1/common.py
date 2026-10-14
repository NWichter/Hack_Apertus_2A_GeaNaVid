"""Shared parts of the stress test: proposal spec, page text, OpenRouter call."""

import json
import os
import re
import time
import unicodedata
import urllib.request
from functools import lru_cache
from pathlib import Path

import pymupdf

from pdftext_repo_copy import clean_page, loose

TRACK = Path(__file__).resolve().parents[4]
# Working folder of this set (booklets/, data/); the published copies are in data/stress-synth/.
BASE = Path(os.environ.get("STRESS_WORKDIR", TRACK / "data" / "stress-synth" / "work-set1"))
BOOKLETS = BASE / "booklets"
DATA = BASE / "data"
ENV = TRACK / ".env"  # OPENROUTER_API_KEY, unless it is set in the environment

# Proposals: date, key, PDF page range (1-based, inclusive, same for de/fr/it), printed titles.
SPEC = [
    (
        "1999-06-13",
        "asyl99",
        (4, 11),
        {"de": "Asylgesetz", "fr": "Loi sur l’asile", "it": "Legge sull’asilo"},
    ),
    (
        "1999-06-13",
        "mutter99",
        (64, 69),
        {
            "de": "Mutterschaftsversicherung",
            "fr": "Assurance-maternité",
            "it": "Assicurazione per la maternità",
        },
    ),
    (
        "2002-03-03",
        "uno02",
        (3, 15),
        {
            "de": "Volksinitiative «für den Beitritt der Schweiz zur Organisation der Vereinten Nationen (UNO)»",
            "fr": "Initiative populaire «pour l’adhésion de la Suisse à l’Organisation des Nations Unies (ONU)»",
            "it": "Iniziativa popolare «per l’adesione della Svizzera all’Organizzazione delle Nazioni Unite (ONU)»",
        },
    ),
    (
        "2002-03-03",
        "arbeit02",
        (16, 23),
        {
            "de": "Volksinitiative «für eine kürzere Arbeitszeit»",
            "fr": "Initiative populaire «pour une durée du travail réduite»",
            "it": "Iniziativa popolare «per una durata ridotta del lavoro»",
        },
    ),
    (
        "2005-06-05",
        "schengen05",
        (3, 13),
        {
            "de": "Abkommen zu Schengen und Dublin",
            "fr": "Accords Schengen/Dublin",
            "it": "Accordi di Schengen e Dublino",
        },
    ),
    (
        "2005-06-05",
        "partner05",
        (14, 19),
        {
            "de": "Partnerschaftsgesetz",
            "fr": "Loi sur le partenariat",
            "it": "Legge sull’unione domestica registrata",
        },
    ),
    (
        "2008-11-30",
        "ahv08",
        (12, 21),
        {
            "de": "Volksinitiative «Für ein flexibles AHV-Alter»",
            "fr": "Initiative populaire «Pour un âge de l’AVS flexible»",
            "it": "Iniziativa popolare «Per un’età di pensionamento flessibile»",
        },
    ),
    (
        "2008-11-30",
        "hanf08",
        (32, 41),
        {
            "de": "Volksinitiative «Für eine vernünftige Hanf-Politik mit wirksamem Jugendschutz»",
            "fr": "Initiative populaire «Pour une politique raisonnable en matière de chanvre protégeant efficacement la jeunesse»",
            "it": "Iniziativa popolare «Per una politica della canapa che sia ragionevole e che protegga efficacemente i giovani»",
        },
    ),
    (
        "2010-11-28",
        "ausschaffung10",
        (4, 15),
        {
            "de": "Volksinitiative «Für die Ausschaffung krimineller Ausländer (Ausschaffungsinitiative)»",
            "fr": "Initiative populaire «Pour le renvoi des étrangers criminels (Initiative sur le renvoi)»",
            "it": "Iniziativa popolare «Per l’espulsione degli stranieri che commettono reati (Iniziativa espulsione)»",
        },
    ),
    (
        "2010-11-28",
        "steuer10",
        (20, 29),
        {
            "de": "Steuergerechtigkeits-Initiative",
            "fr": "Initiative pour des impôts équitables",
            "it": "Iniziativa per imposte eque",
        },
    ),
    (
        "2013-03-03",
        "abzocker13",
        (12, 23),
        {
            "de": "Eidgenössische Volksinitiative «gegen die Abzockerei»",
            "fr": "Initiative populaire fédérale «contre les rémunérations abusives»",
            "it": "Iniziativa popolare «contro le retribuzioni abusive»",
        },
    ),
    (
        "2013-03-03",
        "rpg13",
        (24, 33),
        {
            "de": "Änderung des Raumplanungsgesetzes (RPG)",
            "fr": "Modification de la loi sur l’aménagement du territoire",
            "it": "Modifica della legge sulla pianificazione del territorio (LPT)",
        },
    ),
    (
        "2014-02-09",
        "fabi14",
        (4, 15),
        {
            "de": "Bundesbeschluss über die Finanzierung und den Ausbau der Eisenbahninfrastruktur (direkter Gegenentwurf zur zurückgezogenen Volksinitiative «Für den öffentlichen Verkehr»)",
            "fr": "Arrêté fédéral portant règlement du financement et de l’aménagement de l’infrastructure ferroviaire (contre-projet direct à l’initiative populaire «Pour les transports publics», qui a été retirée)",
            "it": "Decreto federale concernente il finanziamento e l’ampliamento dell’infrastruttura ferroviaria (controprogetto diretto all’iniziativa popolare «Per i trasporti pubblici», ritirata)",
        },
    ),
    (
        "2014-02-09",
        "mei14",
        (27, 39),
        {
            "de": "Volksinitiative «Gegen Masseneinwanderung»",
            "fr": "Initiative populaire «Contre l’immigration de masse»",
            "it": "Iniziativa popolare «Contro l’immigrazione di massa»",
        },
    ),
    (
        "2016-06-05",
        "bge16",
        (12, 21),
        {
            "de": "Volksinitiative «Für ein bedingungsloses Grundeinkommen»",
            "fr": "Initiative populaire « Pour un revenu de base inconditionnel »",
            "it": "Iniziativa popolare «Per un reddito di base incondizionato»",
        },
    ),
    (
        "2016-06-05",
        "asyl16",
        (48, 55),
        {
            "de": "Änderung des Asylgesetzes (AsylG)",
            "fr": "Modification de la loi sur l’asile (LAsi)",
            "it": "Modifica della legge sull’asilo (LAsi)",
        },
    ),
    (
        "2017-05-21",
        "eng17",
        (4, 15),
        {
            "de": "Energiegesetz (EnG)",
            "fr": "Loi sur l'énergie (LEne)",
            "it": "Legge federale sull’energia (LEne)",
        },
    ),
    (
        "2018-03-04",
        "fino18",
        (4, 13),
        {
            "de": "Bundesbeschluss über die neue Finanzordnung 2021",
            "fr": "Arrêté fédéral concernant le nouveau régime financier 2021",
            "it": "Decreto federale concernente il nuovo ordinamento finanziario 2021",
        },
    ),
    (
        "2018-03-04",
        "billag18",
        (14, 28),
        {
            "de": "Volksinitiative «Ja zur Abschaffung der Radio- und Fernsehgebühren (Abschaffung der Billag-Gebühren)»",
            "fr": "Initiative populaire « Oui à la suppression des redevances radio et télévision (suppression des redevances Billag) »",
            "it": "Iniziativa popolare «Sì all’abolizione del canone radiotelevisivo (Abolizione del canone Billag)»",
        },
    ),
]
LANGS = ("de", "fr", "it")
LABELS = {"entailment": 0, "neutral": 1, "contradiction": 2}
NAMES = {v: k for k, v in LABELS.items()}


def pdf_path(date, lang):
    return BOOKLETS / f"{date}_{lang}.pdf"


@lru_cache(maxsize=None)
def raw_pages(date, lang):
    return tuple(p.get_text() for p in pymupdf.open(pdf_path(date, lang)))


@lru_cache(maxsize=None)
def clean_pages(date, lang):
    return tuple(clean_page(p) for p in raw_pages(date, lang))


@lru_cache(maxsize=None)
def loose_pages(date, lang):
    return tuple(loose(p) for p in raw_pages(date, lang))


def garbled(text):
    """Page with broken font encoding (e.g. 2005, voting text) or almost empty."""
    if len(text) < 300:
        return True
    letters = sum(ch.isalpha() for ch in text)
    vowels = sum(ch.lower() in "aeiouàèéìòùäöü" for ch in text)
    return letters / len(text) < 0.6 or vowels / max(letters, 1) < 0.25


def proposal_pages(date, rng, lang):
    pages = clean_pages(date, lang)
    out = []
    for p in range(rng[0], rng[1] + 1):
        if p <= len(pages) and not garbled(pages[p - 1]):
            out.append(p)
    return out


def proposal_text(date, rng, lang):
    return "\n\n".join(
        f"[PDF page {p}]\n{clean_pages(date, lang)[p - 1]}"
        for p in proposal_pages(date, rng, lang)
    )


def verbatim_on_page(quote, date, lang, page):
    q = loose(quote)
    return len(q) >= 15 and q in loose_pages(date, lang)[page - 1]


def find_quote(quote, date, lang, pages):
    q = loose(quote)
    if len(q) < 15:
        return None
    for p in pages:
        if q in loose_pages(date, lang)[p - 1]:
            return p
    return None


def load_env():
    env = {k: v for k, v in os.environ.items() if k == "OPENROUTER_API_KEY"}
    if env or not ENV.is_file():
        return env
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def openrouter(
    model, messages, max_tokens=4000, temperature=0.0, retries=6, extra=None
):
    key = load_env()["OPENROUTER_API_KEY"]
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "usage": {"include": True},
    }
    if extra:
        body.update(extra)
    data = json.dumps(body).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                out = json.loads(r.read().decode())
            if "choices" not in out:
                raise RuntimeError(str(out)[:300])
            return out
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(min(60, 5 * 2**attempt))
    raise RuntimeError(f"OpenRouter failed: {last!r}"[:400])


def parse_json(text):
    text = text or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("no JSON")
    dec = json.JSONDecoder()
    obj, _ = dec.raw_decode(text[start:])
    return obj


def nfkc(s):
    return unicodedata.normalize("NFKC", s or "")
