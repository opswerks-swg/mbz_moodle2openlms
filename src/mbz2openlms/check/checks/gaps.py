"""Moodle features with no OpenLMS equivalent.

These are predictable from the Moodle backup alone, so ``gaps init`` seeds a known-gaps file
from them. Once reviewed, a listed finding is reported as a known gap instead of a failure.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ...mapping import CONVERTED_QTYPES
from ...moodle.model import Activity, FeedbackDetail, QuizDetail
from ..context import Context
from ..findings import FAIL, PASS, WARN

# Activity types the converter handles (and the other checks compare).
HANDLED = {"book", "page", "label", "url", "resource", "folder", "assign", "quiz", "feedback"}
NO_CONTENT = {"subsection", "qbank"}


def run(ctx: Context) -> None:
    for act in ctx.moodle.activities.values():
        _activity(ctx, act)


def _activity(ctx: Context, act: Activity) -> None:
    where = act.where
    if act.modname not in HANDLED | NO_CONTENT:
        detail = f"Moodle '{act.modname}' activities have no OpenLMS equivalent"
        ctx.add(f"unsupported|{where}", "gaps", where, FAIL, detail)
    d = act.detail
    if isinstance(d, QuizDetail):
        _quiz(ctx, act, d)
    elif isinstance(d, FeedbackDetail):
        _feedback(ctx, act, d)
    _restriction(ctx, act)


def _quiz(ctx: Context, act: Activity, d: QuizDetail) -> None:
    where = act.where
    if d.time_limit_minutes:
        node = ctx.nodes.get(act.cmid)
        limited = node is not None and node.sub.time_limited
        ctx.add(
            f"time-limit|{where}",
            "gaps",
            where,
            PASS if limited else FAIL,
            f"time limit {d.time_limit_minutes} min"
            + (" set" if limited else ": not set (timed exams are off on OpenLMS)"),
        )
    security = [
        name
        for name, on in (
            ("password", d.password_set),
            ("network restriction", d.subnet_restricted),
            ("browser security", d.browser_security),
        )
        if on
    ]
    if security:
        detail = f"Moodle {', '.join(security)} has no OpenLMS equivalent"
        ctx.add(f"quiz-security|{where}", "gaps", where, FAIL, detail)
    for slot in d.fixed_slots:
        q = slot.question
        if q and q.kind not in CONVERTED_QTYPES:
            detail = f"question type '{q.qtype}' is not converted"
            ctx.add(f"qtype|{where} slot {slot.number}", "gaps", where, FAIL, detail)
    for n, group in enumerate(d.random_groups, 1):
        for q in group.pool:
            if q.kind not in CONVERTED_QTYPES:
                detail = f"random group {n}: question type '{q.qtype}' is not converted"
                ctx.add(f"qtype|{where} question {q.id}", "gaps", where, FAIL, detail)


def _feedback(ctx: Context, act: Activity, d: FeedbackDetail) -> None:
    where = act.where
    for item in d.questions:
        if item.is_free_text:
            detail = f"free-text question has no OpenLMS equivalent: '{item.name}'"
            ctx.add(f"free-text|{where} item {item.id}", "gaps", where, FAIL, detail)
        elif item.is_agreement and not item.required:
            detail = f"optional statement is required in OpenLMS: '{item.name[:60]}…'"
            ctx.add(f"optional-item|{where} item {item.id}", "gaps", where, WARN, detail)
    if d.page_after_submit_html.strip() and not (
        not d.is_agreement and any(i.is_rating for i in d.questions)
    ):
        detail = "'page after submit' message has no OpenLMS equivalent"
        ctx.add(f"after-submit|{where}", "gaps", where, WARN, detail)


def _restriction(ctx: Context, act: Activity) -> None:
    r = act.restriction
    if r is None:
        return
    where = act.where
    if not r.flat:
        detail = f"restriction can't be expressed in OpenLMS: {r.summary}"
        ctx.add(f"restriction-complex|{where}", "gaps", where, FAIL, detail)
        return
    dates = r.dates()
    if dates:
        text = ", ".join(
            f"{kind} {datetime.fromtimestamp(ts, UTC).isoformat(timespec='minutes')}"
            for kind, ts in dates
        )
        detail = (
            f"Moodle date restriction ({text}) has no per-activity equivalent: use the "
            "subsection start and due dates for the new run"
        )
        ctx.add(f"restriction-window|{where}", "gaps", where, FAIL, detail)
    for kind in r.other_types():
        detail = f"'{kind}' restriction has no OpenLMS equivalent"
        ctx.add(f"restriction-other|{where}", "gaps", where, FAIL, detail)
    if ctx.openlms is None and len(r.completion_cmids()) > 1:
        # Predicting from the backup alone; the prerequisites check gives the same id.
        names = ", ".join(
            f"'{ctx.moodle.activities[c].title}'"
            for c in r.completion_cmids()
            if c in ctx.moodle.activities
        )
        detail = f"Moodle needs {names} completed; OpenLMS allows one prerequisite per subsection"
        ctx.add(f"restriction-multi|{where}", "prerequisites", where, FAIL, detail)
