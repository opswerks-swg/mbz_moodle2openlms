"""``conversion-report.md``: what was built, where each activity went, and the manual
follow-ups in Studio. No answer keys."""

from __future__ import annotations

from ..convert import DROPPED, INFO, MANUAL, Result
from ..moodle.model import Course
from . import date, table

HEADINGS = {
    MANUAL: "Manual follow-up in Studio",
    DROPPED: "Not carried over",
    INFO: "For information",
}


def render(course: Course, result: Result, archive: str) -> str:
    olx = result.olx
    key = f"course-v1:{olx.org}+{olx.number}+{olx.run}"
    lines = [
        f"# Conversion: {course.fullname} ({course.shortname})",
        "",
        f"From `{course.source.backup_name}` to `{archive}` (course key as built: `{key}`; "
        "Studio import keeps the key of the course you import into).",
        "",
        "## Created",
        "",
    ]
    lines += table(["", "Count"], [[k, v] for k, v in result.stats.items()])
    lines += ["## Where each activity went", ""]
    lines += table(["Moodle", "OpenLMS"], [list(p) for p in result.placements])
    lines += ["## Grading", ""]
    rows = [[g["type"], f"{g['weight']:.0%}"] for g in olx.grading_policy.get("GRADER", [])]
    lines += table(["Assignment type", "Weight"], rows) if rows else ["Nothing is graded.", ""]
    cutoff = olx.grading_policy.get("GRADE_CUTOFFS", {}).get("Pass")
    if cutoff is not None:
        lines += [f"Pass cutoff: {cutoff:.0%}.", ""]

    for kind in (MANUAL, DROPPED, INFO):
        notes = [n for n in result.notes if n.kind == kind]
        lines += [f"## {HEADINGS[kind]}", ""]
        if kind == MANUAL:
            lines += ["Do these in Studio after the import, then run `mbz2openlms check`.", ""]
            lines += [f"{i}. **{n.where}**: {n.detail}" for i, n in enumerate(notes, 1)] or [
                "Nothing."
            ]
            lines += [""]
        else:
            lines += (
                table(["Where", "Detail"], [[n.where, n.detail] for n in notes])
                if notes
                else [
                    "Nothing.",
                    "",
                ]
            )

    lines += ["## Dates from the Moodle run", ""]
    if result.options.keep_dates:
        lines += ["Kept (`--keep-dates`). Check they suit the new run.", ""]
    else:
        lines += [
            "Not carried over: they belong to the old run. Set the new run's dates in Studio "
            "(subsection › Configure › Due date). Until a due date is set, answers and "
            'correctness that Moodle showed "after the quiz closed" stay hidden.',
            "",
        ]
    rows = [[where, what, date(when)] for where, what, when in result.dates]
    lines += table(["Where", "What", "Moodle"], rows) if rows else ["None.", ""]
    return "\n".join(lines)
