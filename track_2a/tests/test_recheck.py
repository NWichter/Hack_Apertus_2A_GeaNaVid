import json
import math

from booklint.nli import contradiction_prob, recheck_messages
from booklint.pipeline import Options, Pipeline, committee_terms


def test_committee_terms_restores_the_booklet_word():
    assert committee_terms("Il comitato ritiene", "Der Ausschuss ist der Ansicht", "de") == "Das Komitee ist der Ansicht"
    assert committee_terms("Il comitato ritiene", "laut des Ausschusses", "de") == "laut des Komitees"
    assert committee_terms("Das Komitee findet", "La commission estime", "fr") == "Le comité estime"
    assert committee_terms("Le comité estime", "La commissione ritiene", "it") == "Il comitato ritiene"


def test_committee_terms_leaves_other_claims_alone():
    assert committee_terms("Il Consiglio federale", "Der Ausschuss", "de") == "Der Ausschuss"
    assert committee_terms("Il comitato", "Das Komitee meint", "de") == "Das Komitee meint"
    assert committee_terms("Il comitato", None, "de") is None


def _rec(verdict, p):
    content = json.dumps({"claim_detail": "x", "passage": 1, "passage_detail": "y", "verdict": verdict})
    head = content.split('"verdict": "')[0]
    other = "no" if verdict == "contradiction" else "contr"
    tokens = [{"token": head + '"verdict": "', "top": []},
              {"token": verdict[:5], "top": [[verdict[:5], math.log(p)], [other, math.log(1 - p)]]},
              {"token": verdict[5:] + '"}', "top": []}]
    return {"content": content, "logprobs": tokens}


def test_contradiction_prob_reads_the_verdict_token():
    assert abs(contradiction_prob(_rec("contradiction", 0.8)) - 0.8) < 1e-6
    assert abs(contradiction_prob(_rec("no_contradiction", 0.9)) - 0.1) < 1e-6
    assert contradiction_prob({"content": '{"verdict": "contradiction"}', "logprobs": None}) == 1.0


def test_recheck_prompt_carries_claim_and_translation():
    msgs = recheck_messages(["(p. 3) Text"], "Il comitato ritiene", "it", "de", "Das Komitee meint")
    assert "only for a contradiction" in msgs[0]["content"]
    assert "Das Komitee meint" in msgs[1]["content"] and "[1] (p. 3) Text" in msgs[1]["content"]


class _Model:
    def __init__(self, model):
        self.model = model


def test_recheck_and_terms_default_on_for_8b_only():
    small, large = Pipeline(_Model("apertus-v1.5-8b"), Options()), Pipeline(_Model("apertus-v1.5-70b"), Options())
    assert small.recheck and small.committee_terms
    assert not large.recheck and not large.committee_terms
    assert not Pipeline(_Model("apertus-v1.5-8b"), Options(recheck=False)).recheck
