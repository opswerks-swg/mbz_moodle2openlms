"""Moodle questions as Open edX problems (CAPA XML)."""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

from ..htmlutil import plain_text
from ..moodle.model import Question
from .build import DROPPED, MANUAL, Build
from .xhtml import append_html, unwrap_paragraph


@dataclass
class ProblemSettings:
    """Quiz-level settings every problem of the quiz shares."""

    attempts: int  # 0 = unlimited
    showanswer: str
    shuffle: bool
    hints: bool  # show per-answer feedback


def problem(b: Build, q: Question, weight: float, s: ProblemSettings, where: str):
    """The problem element for ``q``, or None (with a note) when the type isn't converted."""
    where = f"{where} question '{q.name}'"
    el = etree.Element(
        "problem", display_name=q.name or "Question", weight=f"{weight:g}", showanswer=s.showanswer
    )
    if s.attempts:
        el.set("max_attempts", str(s.attempts))
    append_html(el, b.rewrite(q.text_html, q.context_id, where))
    best = max((a.fraction for a in q.answers), default=0.0)

    if q.qtype in ("multichoice", "truefalse"):
        _choices(b, q, el, s, best, where)
    elif q.qtype == "shortanswer":
        full = [plain_text(a.text_html) for a in q.answers if a.fraction == best and best > 0]
        if not full:
            b.note(MANUAL, where, "No correct answer found: not converted.")
            return None
        kind = "cs" if q.options.get("usecase") == "1" else "ci"
        response = etree.SubElement(el, "stringresponse", answer=full[0], type=kind)
        for extra in full[1:]:
            etree.SubElement(response, "additional_answer", answer=extra)
        etree.SubElement(response, "textline", size="40")
        if any("*" in a for a in full):
            b.note(MANUAL, where, "Wildcard (*) answers need a regexp answer in Studio.")
    elif q.qtype == "numerical":
        right = [a for a in q.answers if a.fraction == best and best > 0]
        if not right:
            b.note(MANUAL, where, "No correct answer found: not converted.")
            return None
        response = etree.SubElement(el, "numericalresponse", answer=plain_text(right[0].text_html))
        tolerance = q.options.get("tolerance")
        if tolerance and float(tolerance):
            default = f"{float(tolerance):g}"
            etree.SubElement(response, "responseparam", type="tolerance", default=default)
        etree.SubElement(response, "formulaequationinput")
        if len(right) > 1:
            b.note(DROPPED, where, "Only the first of several correct numbers is kept.")
    else:
        b.note(MANUAL, where, f"Question type '{q.qtype}' is not converted: rebuild it in Studio.")
        return None

    if plain_text(q.general_feedback_html):
        box = etree.SubElement(etree.SubElement(el, "solution"), "div")
        box.set("class", "detailed-solution")
        append_html(box, b.rewrite(q.general_feedback_html, q.context_id, where))
    return el


def _choices(b: Build, q: Question, el, s: ProblemSettings, best: float, where: str) -> None:
    single = q.qtype == "truefalse" or q.options.get("single") == "1"
    if single:
        group = etree.SubElement(
            etree.SubElement(el, "multiplechoiceresponse"), "choicegroup", type="MultipleChoice"
        )
        if any(0 < a.fraction < best for a in q.answers):
            b.note(DROPPED, where, "Partial-credit answers become incorrect.")

        def correct(a) -> bool:
            return best > 0 and a.fraction == best
    else:
        group = etree.SubElement(etree.SubElement(el, "choiceresponse"), "checkboxgroup")
        if len({a.fraction for a in q.answers if a.fraction > 0}) > 1:
            b.note(DROPPED, where, "Weighted checkbox credit becomes all-or-nothing.")

        def correct(a) -> bool:
            return a.fraction > 0

    if s.shuffle and q.qtype == "multichoice" and q.options.get("shuffleanswers") == "1":
        group.set("shuffle", "true")
    for a in q.answers:
        choice = etree.SubElement(group, "choice", correct=str(correct(a)).lower())
        append_html(choice, unwrap_paragraph(b.rewrite(a.text_html, q.context_id, where)))
        if s.hints and plain_text(a.feedback_html):
            hint = etree.SubElement(choice, "choicehint")
            append_html(hint, b.rewrite(a.feedback_html, q.context_id, where))
