"""Feedback activities.

An all-checkbox Feedback (an integrity agreement) becomes a checkboxes problem with every box
required. Rating questions become a Survey component. Free-text questions have no equivalent.
"""

from __future__ import annotations

import json
import re

from lxml import etree

from ...htmlutil import plain_text
from ...moodle.model import Activity, FeedbackDetail
from ...olx.model import Component
from ..build import DROPPED, INFO, MANUAL, Build, Units
from ..xhtml import append_html

AGREEMENT_TYPE = "Integrity Agreement"


def feedback(act: Activity, b: Build) -> Units | None:
    d = act.detail
    assert isinstance(d, FeedbackDetail)
    survey = False
    if d.is_agreement:
        return _agreement(act, d, b)

    components = []
    if d.intro_html.strip():
        components.append(b.html(act.title, d.intro_html, act.context_id, act.where))
    rated = [i for i in d.questions if i.is_rating]
    if rated and len({tuple(i.choices) for i in rated}) == 1:
        components.append(_survey(act, rated, b))
        survey = True
    elif rated:
        b.note(MANUAL, act.where, "Rating questions use different scales: rebuild them as polls.")
    for item in d.questions:
        if item.is_free_text:
            b.note(MANUAL, act.where, f"Free-text question not converted: '{item.name}'.")
        elif not item.is_rating:
            b.note(MANUAL, act.where, f"Question type '{item.type}' not converted: '{item.name}'.")
    if d.page_after_submit_html.strip() and not survey:
        b.note(DROPPED, act.where, "The 'page after submit' message is not converted.")
    if not components:
        return None
    return Units([b.unit(act.cmid, act.title, components)])


def _agreement(act: Activity, d: FeedbackDetail, b: Build) -> Units:
    problem = etree.Element("problem", display_name=act.title, showanswer="never", weight="1")
    append_html(problem, b.rewrite(d.intro_html, act.context_id, act.where))
    group = etree.SubElement(etree.SubElement(problem, "choiceresponse"), "checkboxgroup")
    for item in d.questions:
        choice = etree.SubElement(group, "choice", correct="true")
        choice.text = f"{item.name} — {item.choices[0]}"
        if not item.required:
            b.note(INFO, act.where, f"Optional statement is now required: '{item.name[:60]}…'.")
    if d.page_after_submit_html.strip():
        b.note(DROPPED, act.where, "The 'page after submit' message is not converted.")
    component = Component("problem", b.olx.url_name("agreement", act.cmid), act.title, problem)
    # Graded at 0% of the course grade: Open edX gates a subsection on the *graded* score of
    # its prerequisite, so an ungraded agreement could never unlock the assessment.
    b.fixed_weights[AGREEMENT_TYPE] = 0.0
    return Units(
        [b.unit(act.cmid, act.title, [component])],
        {"graded": "true", "format": AGREEMENT_TYPE},
    )


def _survey(act: Activity, rated, b: Build) -> Component:
    answers = []
    for choice in rated[0].choices:
        key, _, label = choice.partition("####")
        answers.append([key, label] if label else [_slug(key), key])
    questions = [[f"q{i.id}", {"label": i.name, "img": None, "img_alt": None}] for i in rated]
    el = etree.Element(
        "survey",
        block_name=act.title,
        answers=json.dumps(answers, ensure_ascii=False),
        questions=json.dumps(questions, ensure_ascii=False),
        feedback=plain_text(act.detail.page_after_submit_html),
        private_results="true",
        max_submissions="1",
    )
    return Component("survey", b.olx.url_name("survey", act.cmid), act.title, el, inline=True)


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "option"
