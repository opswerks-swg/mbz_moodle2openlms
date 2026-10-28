"""Reader for quizzes (mod_quiz): settings and slots resolved against the question bank."""

from __future__ import annotations

import json
from xml.etree.ElementTree import Element

from ...safe.xml import flag, html, integer, number, text, timestamp
from ..model import Detail, QuestionBank, QuizDetail, RandomGroup, Slot
from ..questions import filter_key, filter_tags, random_pool

Html = list[tuple[str, str]]


def read(el: Element, bank: QuestionBank) -> tuple[Detail, Html]:
    slots = [
        _slot(qi, bank)
        for qi in sorted(
            el.findall("question_instances/question_instance"),
            key=lambda i: integer(i, "slot") or 0,
        )
    ]
    detail = QuizDetail(
        intro_html=html(el, "intro"),
        opens=timestamp(el, "timeopen"),
        closes=timestamp(el, "timeclose"),
        time_limit_minutes=(integer(el, "timelimit") or 0) // 60,
        attempts=integer(el, "attempts_number") or 0,
        shuffle_answers=flag(el, "shuffleanswers"),
        questions_per_page=integer(el, "questionsperpage") or 0,
        grade=number(el, "grade") or 0.0,
        sum_grades=number(el, "sumgrades") or 0.0,
        password_set=bool(text(el, "password")),
        subnet_restricted=bool(text(el, "subnet")),
        browser_security=(text(el, "browsersecurity") or "-") != "-",
        review={c.tag: integer(el, c.tag) or 0 for c in el if c.tag.startswith("review")},
        slots=slots,
        random_groups=_groups(slots),
    )
    return detail, [("intro", detail.intro_html)]


def _slot(qi: Element, bank: QuestionBank) -> Slot:
    slot = Slot(
        number=integer(qi, "slot") or 0,
        page=integer(qi, "page") or 0,
        max_mark=number(qi, "maxmark") or 0.0,
        kind="unknown",
    )
    ref = qi.find("question_reference")
    set_ref = qi.find("question_set_reference")
    if ref is not None:
        slot.kind = "fixed"
        slot.entry_id = integer(ref, "questionbankentryid")
        slot.pinned_version = integer(ref, "version")
        entry = bank.entries.get(slot.entry_id or -1)
        slot.question = entry.version(slot.pinned_version) if entry else None
    elif set_ref is not None:
        condition = json.loads(text(set_ref, "filtercondition") or "{}")
        slot.kind = "random"
        slot.filter_key = filter_key(condition)
        slot.filter_tags = filter_tags(bank, condition)
        slot.pool, slot.unhandled_filters = random_pool(bank, condition)
    return slot


def _groups(slots: list[Slot]) -> list[RandomGroup]:
    groups: dict[str, RandomGroup] = {}
    for slot in slots:
        if slot.kind != "random" or slot.filter_key is None:
            continue
        group = groups.setdefault(slot.filter_key, RandomGroup([], [], slot.filter_tags, slot.pool))
        group.slots.append(slot.number)
        group.marks.append(slot.max_mark)
    return list(groups.values())
