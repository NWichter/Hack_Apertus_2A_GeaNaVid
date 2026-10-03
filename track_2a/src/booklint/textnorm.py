import re
import unicodedata

_STOP = {
    "de": "der die das und ist nicht mit von den dem des ein eine zu im auf für sich auch wird werden dass es".split(),
    "fr": "le la les et est pas avec de des du un une à au en pour que qui se sur dans par ce il".split(),
    "it": "il lo la le gli e è non con di del della dei un una che per in si sono da nel alla".split(),
}

_NUM_GROUP = re.compile(r"(?<=\d)['’   ](?=\d{3}\b)")
_TOKEN = re.compile(r"\d+(?:[.,]\d+)*|[^\W\d_]+", re.UNICODE)


def clean(text):
    text = text.replace("­ ", "").replace("­", "")
    text = text.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    return re.sub(r"\s+", " ", text).strip()


def detect_language(text):
    words = re.findall(r"[^\W\d_]+", text.lower())
    scores = {lang: sum(w in stop for w in words) for lang, stop in _STOP.items()}
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
