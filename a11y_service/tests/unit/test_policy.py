from app.evaluation.policy import finding_verdict, overall_verdict
from app.knowledge.schemas import Chunk
from app.schemas import Observation, OverallVerdict, Verdict


def chunk(sc, authority="normative"):
    return Chunk(chunk_id=f"c{sc}", document_id="d", document="WCAG 2.2", document_version="2.2",
                 authority=authority, success_criterion=sc, title="t", level="A", content="x",
                 source_url="u", retrieved="2026", checksum="c")


def obs(status, crit=("4.1.2",)):
    return Observation(rule_id="r", status=status, observation="o", candidate_criteria=list(crit))


def test_fail_needs_normative_support():
    assert finding_verdict(obs("fail"), [chunk("4.1.2")])[0] == Verdict.FAIL
    assert finding_verdict(obs("fail"), [chunk("4.1.2", "official_explanatory")])[0] == Verdict.INSUFFICIENT_EVIDENCE
    assert finding_verdict(obs("fail"), [chunk("1.1.1")])[0] == Verdict.INSUFFICIENT_EVIDENCE
    assert finding_verdict(obs("fail"), [])[0] == Verdict.INSUFFICIENT_EVIDENCE
    assert finding_verdict(obs("fail", ()), [chunk("4.1.2")])[0] == Verdict.INSUFFICIENT_EVIDENCE


def test_other_statuses():
    assert finding_verdict(obs("manual"), [])[0] == Verdict.MANUAL_REVIEW
    assert finding_verdict(obs("pass"), [])[0] == Verdict.PASS
    assert finding_verdict(obs("unknown"), [])[0] == Verdict.INSUFFICIENT_EVIDENCE


def test_overall_priority():
    V = Verdict
    assert overall_verdict([V.PASS, V.FAIL, V.MANUAL_REVIEW]) == OverallVerdict.FAIL
    assert overall_verdict([V.PASS, V.MANUAL_REVIEW, V.INSUFFICIENT_EVIDENCE]) == OverallVerdict.MANUAL_REVIEW
    assert overall_verdict([V.PASS, V.INSUFFICIENT_EVIDENCE]) == OverallVerdict.INSUFFICIENT_EVIDENCE
    assert overall_verdict([V.PASS]) == OverallVerdict.PASS_WITH_SCOPE_LIMITATION
    assert overall_verdict([]) == OverallVerdict.INSUFFICIENT_EVIDENCE
