import re
import unicodedata

_NUM_GROUP = re.compile(r"(?<=\d)['’   ](?=\d{3}\b)")
_TOKEN = re.compile(r"\d+(?:[.,]\d+)*|[^\W\d_]+", re.UNICODE)


def clean(text):
    text = text.replace("­ ", "").replace("­", "")
    text = text.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    return re.sub(r"\s+", " ", text).strip()


_STOP = {
    "de": set(
        "der die das und ist nicht mit von den dem des ein eine einen zu im auf für sich auch wird werden dass es "
        "bei zur zum über nach soll sollen kann können wenn sind hat haben oder aus durch um wie wird diese dieser".split()
    ),
    "fr": set(
        "les et est pas avec de des du en une à au aux pour que qui sur dans par ce cette ces sont sera pourra être "
        "plus ne qu d leur leurs été ont où sous entre selon".split()
    ),
    "it": set(
        "e è non con di del della delle dei degli una che per sono nel nella nelle alla alle al dal dalla sul "
        "sulla sulle sui ai agli viene verrà sarà potrà anche più gli lo dell nell all sull dall questo questa "
        "essere hanno ha tra secondo".split()
    ),
}
_CHAR_FEATURES = {
    "de": [
        (re.compile(r"[äöüß]"), 1.0),
        (re.compile(r"sch|ung\b|tz|ck|eit\b|gesetz|bundes|volks"), 0.7),
    ],
    "fr": [
        (re.compile(r"[éêçœ]|è(?=\w)"), 0.6),
        (re.compile(r"eau|\boi|oi\b|aux\b|eux\b|tion|ée\b"), 0.7),
    ],
    "it": [
        (re.compile(r"[àìòù]\b|\bè\b"), 1.0),
        (re.compile(r"zion|zz|gli|cch|[^\W\d_]{2,}[aio]\b"), 0.5),
    ],
}
_QUOTED = re.compile(r"«[^»]*»|„[^“”]*[“”]|\"[^\"]*\"|“[^”]*”")


def language_scores(text):
    """de / fr / it scores from function words; letters and suffixes break ties and decide short titles.
    Quoted titles are ignored when enough text remains (a German claim may quote a French initiative)."""
    text = text.lower().replace("’", "'")
    unquoted = _QUOTED.sub(" ", text)
    if len(re.findall(r"[^\W\d_]+", unquoted)) >= 4:
        text = unquoted
    words = re.findall(r"[^\W\d_]+", text)
    scores = {}
    for lang, stop in _STOP.items():
        s = sum(w in stop for w in words)
        for pattern, weight in _CHAR_FEATURES[lang]:
            s += weight * len(pattern.findall(text))
        scores[lang] = s
    return scores


def detect_language(text):
    scores = language_scores(text)
    return max(scores, key=scores.get)


def fold(text):
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def tokens(text, stem=6):
    text = _NUM_GROUP.sub("", fold(clean(text)))
    out = []
    for tok in _TOKEN.findall(text):
        if tok[0].isdigit():
            out.append(tok.replace(",", "."))
        elif len(tok) > 1:
            out.append(tok[:stem])
    return out
