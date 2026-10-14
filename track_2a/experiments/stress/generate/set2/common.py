"""Shared parts of the stress test (second set, 2026-10-14b): proposal spec, page text, OpenRouter call."""

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
BASE = Path(os.environ.get("STRESS_WORKDIR", TRACK / "data" / "stress-synth" / "work-set2"))
BOOKLETS = BASE / "booklets"
DATA = BASE / "data"
ENV = TRACK / ".env"  # OPENROUTER_API_KEY, unless it is set in the environment

# Proposals: date, key, PDF page range (1-based, inclusive; a dict {lang: range} where the languages differ),
# printed titles. Ranges cover the explanations (and short voting texts); long law texts are left out.
SPEC = [
    (
        "1998-09-27",
        "lsva98",
        (4, 11),
        {
            "de": "Bundesgesetz über eine leistungsabhängige Schwerverkehrsabgabe",
            "fr": "Loi fédérale concernant une redevance sur le trafic des poids lourds liée aux prestations",
            "it": "Legge federale concernente una tassa sul traffico pesante commisurata alle prestazioni",
        },
    ),
    (
        "1998-09-27",
        "ahv98",
        (26, 31),
        {
            "de": 'Volksinitiative "für die 10. AHV-Revision ohne Erhöhung des Rentenalters"',
            "fr": 'Initiative populaire "pour la 10e révision de l’AVS sans relèvement de l’âge de la retraite"',
            "it": "Iniziativa popolare \"per la 10a revisione dell'AVS senza aumento dell'età di pensionamento\"",
        },
    ),
    (
        "1999-02-07",
        "transplant99",
        (10, 15),
        {
            "de": "Transplantationsmedizin",
            "fr": "Médecine de la transplantation",
            "it": "Medicina dei trapianti",
        },
    ),
    (
        "1999-02-07",
        "wohneigentum99",
        (16, 21),
        {
            "de": "Volksinitiative “Wohneigentum für alle”",
            "fr": 'Initiative populaire "propriété du logement pour tous"',
            "it": "Iniziativa popolare “abitazione in proprietà per tutti”",
        },
    ),
    (
        "2000-05-21",
        "bilaterale00",
        (2, 15),
        {
            "de": "Bilaterale Abkommen der Schweiz mit der Europäischen Union",
            "fr": "Accords bilatéraux entre la Suisse et l’Union européenne",
            "it": "Accordi bilaterali tra la Svizzera e l’Unione europea",
        },
    ),
    (
        "2001-03-04",
        "europa01",
        {"de": (1, 6), "fr": (1, 6), "it": (4, 9)},
        {
            "de": "Volksinitiative «Ja zu Europa!»",
            "fr": "Initiative «Oui à l’Europe!»",
            "it": "Iniziativa popolare «Sì all’Europa!»",
        },
    ),
    (
        "2001-03-04",
        "arznei01",
        {"de": (7, 12), "fr": (7, 12), "it": (10, 15)},
        {
            "de": "Volksinitiative «für tiefere Arzneimittelpreise»",
            "fr": "Initiative «pour des médicaments à moindre prix»",
            "it": "Iniziativa popolare «per farmaci a prezzi più bassi»",
        },
    ),
    (
        "2003-05-18",
        "armee03",
        (1, 6),
        {
            "de": "Änderung des Militärgesetzes (Armee XXI)",
            "fr": "Modification de la loi sur l’armée (Armée XXI)",
            "it": "Modifica della legge militare (Esercito XXI)",
        },
    ),
    (
        "2003-05-18",
        "behinderte03",
        (35, 42),
        {
            "de": "Volksinitiative «Gleiche Rechte für Behinderte»",
            "fr": "Initiative populaire «Droits égaux pour les personnes handicapées»",
            "it": "Iniziativa popolare «Parità di diritti per i disabili»",
        },
    ),
    (
        "2004-09-26",
        "post04",
        (14, 21),
        {
            "de": "Eidgenössische Volksinitiative «Postdienste für alle»",
            "fr": "Initiative populaire «Services postaux pour tous»",
            "it": "Iniziativa popolare «Servizi postali per tutti»",
        },
    ),
    (
        "2004-09-26",
        "eo04",
        (22, 27),
        {
            "de": "Änderung des Erwerbsersatzgesetzes (für Dienstleistende und bei Mutterschaft)",
            "fr": "Modification de la loi sur les allocations pour perte de gain (en cas de service ou de maternité)",
            "it": "Modifica della legge sulle indennità di perdita di guadagno (in caso di servizio o di maternità)",
        },
    ),
    (
        "2006-09-24",
        "nbgewinne06",
        (4, 11),
        {
            "de": "Volksinitiative «Nationalbankgewinne für die AHV»",
            "fr": "Initiative populaire «Bénéfices de la Banque nationale pour l’AVS»",
            "it": "Iniziativa popolare «Utili della Banca nazionale per l’AVS»",
        },
    ),
    (
        "2006-09-24",
        "auslaender06",
        (12, 19),
        {
            "de": "Bundesgesetz über die Ausländerinnen und Ausländer",
            "fr": "Loi fédérale sur les étrangers",
            "it": "Legge federale sugli stranieri",
        },
    ),
    (
        "2007-06-17",
        "iv07",
        (5, 15),
        {
            "de": "Änderung des Bundesgesetzes über die Invalidenversicherung (5. IV-Revision)",
            "fr": "Modification de la loi fédérale sur l’assurance-invalidité (5e révision de l’AI)",
            "it": "Modifica della legge federale sull’assicurazione per l’invalidità (5a revisione dell’AI)",
        },
    ),
    (
        "2009-11-29",
        "kriegsmaterial09",
        (12, 21),
        {
            "de": "Volksinitiative «Für ein Verbot von Kriegsmaterial-Exporten»",
            "fr": "Initiative populaire «Pour l’interdiction d’exporter du matériel de guerre»",
            "it": "Iniziativa popolare «Per il divieto di esportare materiale bellico»",
        },
    ),
    (
        "2009-11-29",
        "minarett09",
        (22, 29),
        {
            "de": "Volksinitiative «Gegen den Bau von Minaretten»",
            "fr": "Initiative populaire «Contre la construction de minarets»",
            "it": "Iniziativa popolare «Contro l’edificazione di minareti»",
        },
    ),
    (
        "2011-02-13",
        "waffen11",
        (4, 13),
        {
            "de": "Eidgenössische Volksinitiative «Für den Schutz vor Waffengewalt»",
            "fr": "Initiative populaire «Pour la protection face à la violence des armes»",
            "it": "Iniziativa popolare «Per la protezione dalla violenza perpetrata con le armi»",
        },
    ),
    (
        "2012-03-11",
        "zweitwohnungen12",
        (4, 13),
        {
            "de": "Eidgenössische Volksinitiative «Schluss mit uferlosem Bau von Zweitwohnungen!»",
            "fr": "Initiative populaire «Pour en finir avec les constructions envahissantes de résidences secondaires»",
            "it": "Iniziativa popolare «Basta con la costruzione sfrenata di abitazioni secondarie!»",
        },
    ),
    (
        "2012-03-11",
        "buchpreis12",
        (40, 48),
        {
            "de": "Bundesgesetz über die Buchpreisbindung",
            "fr": "Loi fédérale sur la réglementation du prix du livre",
            "it": "Legge federale sul prezzo fisso dei libri",
        },
    ),
    (
        "2013-09-22",
        "wehrpflicht13",
        (4, 15),
        {
            "de": "Volksinitiative «Ja zur Aufhebung der Wehrpflicht»",
            "fr": "Initiative populaire «Oui à l’abrogation du service militaire obligatoire»",
            "it": "Iniziativa popolare «Sì all’abolizione del servizio militare obbligatorio»",
        },
    ),
    (
        "2013-09-22",
        "epidemien13",
        (16, 23),
        {
            "de": "Bundesgesetz über die Bekämpfung übertragbarer Krankheiten des Menschen (Epidemiengesetz)",
            "fr": "Loi fédérale sur la lutte contre les maladies transmissibles de l’homme (loi sur les épidémies)",
            "it": "Legge federale sulla lotta contro le malattie trasmissibili dell’essere umano (Legge sulle epidemie)",
        },
    ),
    (
        "2015-06-14",
        "pid15",
        (4, 13),
        {
            "de": "Bundesbeschluss über die Änderung der Verfassungsbestimmung zur Fortpflanzungsmedizin und Gentechnologie im Humanbereich",
            "fr": "Arrêté fédéral concernant la modification de l’article constitutionnel relatif à la procréation médicalement assistée et au génie génétique dans le domaine humain",
            "it": "Decreto federale concernente la modifica dell’articolo costituzionale relativo alla medicina riproduttiva e all’ingegneria genetica in ambito umano",
        },
    ),
    (
        "2015-06-14",
        "erbschaft15",
        (24, 33),
        {
            "de": "Volksinitiative «Millionen-Erbschaften besteuern für unsere AHV (Erbschaftssteuerreform)»",
            "fr": "Initiative populaire « Imposer les successions de plusieurs millions pour financer notre AVS (Réforme de la fiscalité successorale) »",
            "it": "Iniziativa popolare «Tassare le eredità milionarie per finanziare la nostra AVS (Riforma dell’imposta sulle successioni)»",
        },
    ),
    (
        "2016-09-25",
        "gruenewirtschaft16",
        (4, 13),
        {
            "de": "Volksinitiative «Für eine nachhaltige und ressourceneffiziente Wirtschaft (Grüne Wirtschaft)»",
            "fr": "Initiative populaire « Pour une économie durable et fondée sur une gestion efficiente des ressources (économie verte) »",
            "it": "Iniziativa popolare «Per un’economia sostenibile ed efficiente in materia di gestione delle risorse (economia verde)»",
        },
    ),
    (
        "2016-09-25",
        "ndg16",
        (24, 31),
        {
            "de": "Bundesgesetz über den Nachrichtendienst (Nachrichtendienstgesetz, NDG)",
            "fr": "Loi fédérale sur le renseignement (LRens)",
            "it": "Legge federale sulle attività informative (LAIn)",
        },
    ),
    (
        "2017-09-24",
        "ernaehrung17",
        (4, 11),
        {
            "de": "Bundesbeschluss über die Ernährungssicherheit (direkter Gegenentwurf zur zurückgezogenen Volksinitiative «Für Ernährungssicherheit»)",
            "fr": "Arrêté fédéral sur la sécurité alimentaire (contre-projet direct à l’initiative populaire « Pour la sécurité alimentaire », qui a été retirée)",
            "it": "Decreto federale sulla sicurezza alimentare (controprogetto diretto all’iniziativa popolare «Per la sicurezza alimentare», ritirata)",
        },
    ),
    (
        "2018-09-23",
        "velo18",
        (10, 18),
        {
            "de": "Bundesbeschluss über die Velowege sowie die Fuss- und Wanderwege (direkter Gegenentwurf zur zurückgezogenen Volksinitiative «Zur Förderung der Velo-, Fuss- und Wanderwege [Velo-Initiative]»)",
            "fr": "Arrêté fédéral concernant les voies cyclables et les chemins et sentiers pédestres (contre-projet direct à l’initiative populaire « Pour la promotion des voies cyclables et des chemins et sentiers pédestres [initiative vélo] », qui a été retirée)",
            "it": "Decreto federale concernente le vie ciclabili, i sentieri e i percorsi pedonali (controprogetto diretto all’iniziativa popolare «Per la promozione delle vie ciclabili e dei sentieri e percorsi pedonali [Iniziativa per la bici]», ritirata)",
        },
    ),
    (
        "2018-09-23",
        "fairfood18",
        (20, 29),
        {
            "de": "Volksinitiative «Für gesunde sowie umweltfreundlich und fair hergestellte Lebensmittel (Fair-Food-Initiative)»",
            "fr": "Initiative populaire « Pour des denrées alimentaires saines et produites dans des conditions équitables et écologiques (initiative pour des aliments équitables) »",
            "it": "Iniziativa popolare «Per derrate alimentari sane, prodotte nel rispetto dell’ambiente e in modo equo (Iniziativa per alimenti equi)»",
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


def lang_range(rng, lang):
    return rng[lang] if isinstance(rng, dict) else rng


def proposal_pages(date, rng, lang):
    rng = lang_range(rng, lang)
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


# Budget guard: the whole job may spend at most 3.00 USD; stop new calls at BUDGET_STOP above the
# key usage logged as "start" in data/usage.log. Every call's own cost is appended to data/costs.jsonl.
BUDGET_STOP = 2.80
_guard = {"calls": 0, "lock": None}


def _baseline():
    for line in (DATA / "usage.log").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("tag") == "start":
            return rec["usage"]
    raise RuntimeError("no start entry in usage.log")


def key_usage():
    key = load_env()["OPENROUTER_API_KEY"]
    req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())["data"]["usage"]


def budget_check(force=False):
    import threading

    if _guard["lock"] is None:
        _guard["lock"] = threading.Lock()
    with _guard["lock"]:
        _guard["calls"] += 1
        if not force and _guard["calls"] % 20 != 1:
            return
        spent = key_usage() - _baseline()
        if spent > BUDGET_STOP:
            raise SystemExit(f"BUDGET STOP: key usage +{spent:.4f} USD since start")


def _log_cost(model, out):
    u = out.get("usage") or {}
    rec = {"model": model, "served": out.get("model"), "cost": u.get("cost"),
           "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens")}
    with (DATA / "costs.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec) + "\n")


def openrouter(
    model, messages, max_tokens=4000, temperature=0.0, retries=6, extra=None
):
    budget_check()
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
            _log_cost(model, out)
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
