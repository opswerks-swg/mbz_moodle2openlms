"""Quizzes: problems, Problem Banks for random questions, ORAs for essays."""

from __future__ import annotations

from lxml import etree

from ...htmlutil import plain_text
from ...moodle.model import Activity, FileSubmission, QuizDetail, RandomGroup, Slot
from ...olx.model import Component
from ..build import DROPPED, INFO, MANUAL, Build, Units
from ..ora import ora
from ..problems import ProblemSettings, problem

# Quiz review-option bits (mod/quiz display_options).
DURING, IMMEDIATELY_AFTER, LATER_WHILE_OPEN, AFTER_CLOSE = 0x10000, 0x01000, 0x00100, 0x00010
NOW = DURING | IMMEDIATELY_AFTER


def quiz(act: Activity, b: Build) -> Units:
    d = act.detail
    assert isinstance(d, QuizDetail)
    settings = ProblemSettings(
        attempts=d.attempts,
        showanswer=showanswer(d.review.get("reviewrightanswer", 0)),
        shuffle=d.shuffle_answers,
        hints=bool(d.review.get("reviewspecificfeedback", 0) & NOW),
    )
    components: list[Component] = []
    if d.intro_html.strip():
        components.append(b.html(act.title, d.intro_html, act.context_id, act.where))

    gradable = False
    for slot in d.fixed_slots:
        q = slot.question
        if q is None:
            missing = f"Slot {slot.number}: the question is missing from the backup."
            b.note(MANUAL, act.where, missing)
        elif q.qtype == "description":
            components.append(b.html(q.name, q.text_html, q.context_id, act.where))
        elif q.qtype == "essay":
            components.append(_essay(act, d, slot, b))
            gradable = True
        elif (el := problem(b, q, slot.max_mark, settings, act.where)) is not None:
            components.append(_component(b, act, q.id, q.name, el))
            gradable = True
    for n, group in enumerate(d.random_groups, start=1):
        if bank := _bank(act, group, n, settings, b):
            components.append(bank)
            gradable = True

    if not settings.hints and _has_answer_feedback(d):
        b.note(
            DROPPED,
            act.where,
            "Per-answer feedback dropped: Moodle showed it only after the quiz closed, and "
            "Open edX shows hints straight away.",
        )
    units = Units([b.unit(act.cmid, act.title, components)])
    b.record_date(act.where, "opens", d.opens)
    b.record_date(act.where, "closes", d.closes)
    b.date_attr(units.attrs, "start", d.opens)
    b.date_attr(units.attrs, "due", d.closes)
    correctness = show_correctness(d.review.get("reviewcorrectness", 0))
    if correctness != "always":
        units.attrs["show_correctness"] = correctness
    if d.grade > 0 and gradable:
        units.attrs.update(b.graded(act, act.title))
    if d.time_limit_minutes:
        if b.opts.timed_exams:
            units.attrs.update(
                is_time_limited="true", default_time_limit_minutes=str(d.time_limit_minutes)
            )
        else:
            b.note(
                DROPPED,
                act.where,
                f"Time limit of {d.time_limit_minutes} min not set (timed exams are off). "
                "Convert again with --timed-exams once they are enabled.",
            )
    if d.password_set or d.subnet_restricted or d.browser_security:
        b.note(DROPPED, act.where, "Quiz password / network / browser restriction dropped.")
    return units


def _essay(act: Activity, d: QuizDetail, slot: Slot, b: Build) -> Component:
    q = slot.question
    o = q.options
    upload = None
    if int(o.get("attachments") or 0) != 0:
        upload = FileSubmission(int(o.get("attachments") or 1), 0, o.get("filetypeslist") or "")
    file_response = ""
    if upload:
        required = o.get("attachmentsrequired") not in (None, "0")
        file_response = "required" if required else "optional"
    text = ""
    if o.get("responseformat") != "noinline":
        text = "required" if o.get("responserequired") == "1" else "optional"
    if o.get("graderinfo"):
        b.note(INFO, act.where, "Moodle's grader information is used as the rubric prompt.")
    return ora(
        b,
        act.title,
        q.text_html,
        q.context_id,
        f"{act.where} question '{q.name}'",
        text_response=text or ("" if file_response else "required"),
        file_response=file_response,
        upload=upload,
        opens=d.opens,
        due=d.closes,
        points=int(slot.max_mark or 1),
        grader_info=o.get("graderinfo") or "",
    )


def _bank(
    act: Activity, group: RandomGroup, n: int, s: ProblemSettings, b: Build
) -> Component | None:
    marks = sorted(set(group.marks))
    if len(marks) > 1:
        b.note(
            MANUAL,
            act.where,
            f"Random slots {group.slots} have different marks {marks}: every problem in the "
            f"bank uses {marks[-1]:g}.",
        )
    weight = marks[-1] if marks else 1.0
    tags = ", ".join(group.tags)
    name = f"{act.title}: {tags} questions" if tags else f"{act.title}: questions"
    el = etree.Element("itembank", display_name=name, max_count=str(group.count))
    children = []
    for q in group.pool:
        p = problem(b, q, weight, s, act.where)
        if p is None:
            continue
        child = _component(b, act, q.id, q.name, p)
        etree.SubElement(el, "problem", url_name=child.url_name)
        children.append(child)
    if len(children) < group.count:
        b.note(
            MANUAL,
            act.where,
            f"Problem bank '{name}' has {len(children)} usable problem(s) for {group.count} slots.",
        )
    if not children:
        return None
    b.note(
        INFO,
        act.where,
        f"Random selection kept: '{name}' shows {group.count} of {len(children)} problems "
        "to each learner.",
    )
    return Component("itembank", b.olx.url_name("bank", act.cmid, n), name, el, children)


def _component(b: Build, act: Activity, qid: int, name: str, el) -> Component:
    return Component("problem", b.olx.url_name("q", act.cmid, qid), name, el)


def _has_answer_feedback(d: QuizDetail) -> bool:
    questions = [s.question for s in d.fixed_slots if s.question]
    questions += [q for g in d.random_groups for q in g.pool]
    return any(plain_text(a.feedback_html) for q in questions for a in q.answers)


def showanswer(bits: int) -> str:
    if bits & (NOW | LATER_WHILE_OPEN):
        return "finished"
    if bits & AFTER_CLOSE:
        return "past_due"
    return "never"


def show_correctness(bits: int) -> str:
    if bits & (NOW | LATER_WHILE_OPEN):
        return "always"
    if bits & AFTER_CLOSE:
        return "past_due"
    return "never"
