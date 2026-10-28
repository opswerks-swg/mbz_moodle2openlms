"""Grading: each graded Moodle item's share of the course grade, and the pass mark."""

from __future__ import annotations

from ..context import Context
from ..findings import FAIL, PASS, WARN


def run(ctx: Context) -> None:
    course, moodle = ctx.openlms, ctx.moodle
    weights = moodle.gradebook.weights()
    graded = set()
    for cmid, expected in weights.items():
        node = ctx.nodes.get(cmid)
        act = moodle.activities.get(cmid)
        if node is None or act is None:
            continue
        sub = node.sub
        graded.add(id(sub))
        if not sub.graded or not sub.format:
            detail = f"graded in Moodle ({expected:.0%}), subsection '{sub.name}' is ungraded"
            ctx.add(f"grading|{act.where}", "grading", act.where, FAIL, detail)
            continue
        share = course.share(sub)
        ctx.add(
            f"grading|{act.where}",
            "grading",
            act.where,
            PASS if abs(share - expected) < 0.005 else FAIL,
            f"{share:.0%} of the course grade ('{sub.format}'), Moodle {expected:.0%}",
        )
    for _section, sub in course.subsections():
        if sub.graded and id(sub) not in graded and course.share(sub) > 0:
            detail = f"counts {course.share(sub):.0%} of the grade, but nothing in it is graded"
            ctx.add(
                f"grading-extra|{sub.name}", "grading", f"subsection '{sub.name}'", FAIL, detail
            )
    _pass_mark(ctx)


def _pass_mark(ctx: Context) -> None:
    gb = ctx.moodle.gradebook
    items = [i for i in gb.items if i.counts and i.cmid in ctx.moodle.activities]
    ratios = {round(i.grade_pass / i.grade_max, 4) for i in items if i.grade_pass > 0}
    if gb.course_item and gb.course_item.grade_pass and gb.course_item.grade_max:
        ratios = {round(gb.course_item.grade_pass / gb.course_item.grade_max, 4)}
    cutoff = ctx.openlms.cutoff
    shown = "not set" if cutoff is None else f"{cutoff:.0%}"
    if len(ratios) == 1:
        ratio = ratios.pop()
        ok = cutoff is not None and abs(cutoff - ratio) < 0.001
        detail = f"pass cutoff {shown}, Moodle pass mark {ratio:.0%}"
        ctx.add("pass-mark", "grading", "course", PASS if ok else FAIL, detail)
    elif not ratios:
        default = cutoff is None or abs(cutoff - 0.5) < 0.001  # Open edX's default
        detail = f"Moodle has no pass mark; OpenLMS cutoff {shown}"
        ctx.add("pass-mark", "grading", "course", PASS if default else WARN, detail)
    else:
        marks = ", ".join(f"{r:.0%}" for r in sorted(ratios))
        detail = f"Moodle pass marks differ ({marks}); OpenLMS has one cutoff ({shown})"
        ctx.add("pass-mark", "grading", "course", WARN, detail)
