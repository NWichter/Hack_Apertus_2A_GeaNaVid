"""booklint: check claims against Swiss official voting booklets (document-level NLI with evidence)."""

__version__ = "0.2.0"

LABELS = {"entailment": 0, "neutral": 1, "contradiction": 2}
LABEL_NAMES = {v: k for k, v in LABELS.items()}
LANGS = ("de", "fr", "it")
