"""Compare text and answers between Moodle HTML and OLX, independently of the converter."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher

from lxml import etree

from .. import credentials
from ..htmlutil import plain_text
from ..moodle.model import Question

# Share of the Moodle words that must appear, in order, in the OpenLMS text.
COVERAGE = 0.95
CHOICE_TYPES = {"multichoice", "truefalse"}


def expected_words(html: str | None) -> list[str]:
    """Words of Moodle HTML the migrated course must contain. Credentials are left out: the
    runbook has them removed."""
    return plain_text(credentials.without_credentials(html or "")).split()


def words_of(roots: list[etree._Element]) -> list[str]:
    """Visible words of OLX elements (escaped or CDATA HTML unwrapped, survey labels included)."""
    out: list[str] = []
    for root in roots:
        for el in root.iter():
            if not isinstance(el.tag, str):
                continue
            for value in (el.text, el.tail):
                if value and value.strip():
                    out += plain_text(value).split() if "<" in value else value.split()
            if el.tag == "survey":
                for _key, q in json.loads(el.get("questions") or "[]"):
                    out += plain_text(q.get("label")).split()
    return out


def coverage(expected: list[str], actual: list[str]) -> float:
    if not expected:
        return 1.0
    matcher = SequenceMatcher(None, expected, actual, autojunk=False)
    return sum(b.size for b in matcher.get_matching_blocks()) / len(expected)


def found(html: str | None, roots: list[etree._Element]) -> float:
    return coverage(expected_words(html), words_of(roots))


def norm(value: str | None) -> str:
    return " ".join((value or "").split())


def answer_key(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


Answers = frozenset[tuple[str, bool]]


def moodle_answers(q: Question) -> Answers:
    if q.qtype in CHOICE_TYPES:
        return frozenset((answer_key(plain_text(a.text_html)), a.fraction > 0) for a in q.answers)
    best = max((a.fraction for a in q.answers), default=0.0)
    keys = [
        answer_key(plain_text(a.text_html)) for a in q.answers if best > 0 and a.fraction == best
    ]
    if q.qtype == "numerical":
        keys = keys[:1]  # one number per problem
    return frozenset((k, True) for k in keys)


def problem_answers(problem: etree._Element) -> Answers:
    choices = problem.findall(".//choicegroup/choice") + problem.findall(".//checkboxgroup/choice")
    if choices:
        return frozenset((answer_key(_choice_text(c)), c.get("correct") == "true") for c in choices)
    keys = set()
    for response in problem.iter("stringresponse", "numericalresponse"):
        keys.add((answer_key(response.get("answer") or ""), True))
        for extra in response.iter("additional_answer"):
            keys.add((answer_key(extra.get("answer") or extra.text or ""), True))
    return frozenset(keys)


def _choice_text(choice: etree._Element) -> str:
    parts = [choice.text or ""]
    for child in choice:
        if child.tag != "choicehint":
            parts.append("".join(child.itertext()))
        parts.append(child.tail or "")
    return " ".join(parts)


def answer_counts(answers: Answers) -> str:
    return f"{len(answers)} answer(s), {sum(ok for _, ok in answers)} correct"


def rubric_points(ora: etree._Element) -> float:
    return sum(
        max((float(o.get("points") or 0) for o in c.findall("option")), default=0.0)
        for c in ora.iter("criterion")
    )
