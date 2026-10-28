"""Check a migrated OpenLMS course against its Moodle original.

The expectations come from the Moodle model and the rules in ``checks/``; nothing comes from
the converter (``tests/test_boundaries.py`` enforces it), so a converter mistake can't hide
itself. Findings never contain answer keys: answers are compared and only counted.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..moodle.model import Course
from ..openlms.model import MigratedCourse
from . import known_gaps
from .checks import (
    assignments,
    content,
    dates,
    files,
    gaps,
    grading,
    prerequisites,
    quizzes,
    rules,
    structure,
)
from .context import Context
from .findings import FAIL, GAP, PASS, SKIP, WARN, Finding, KnownGap, Report
from .review import Rules

__all__ = ["FAIL", "GAP", "PASS", "SKIP", "WARN", "Finding", "KnownGap", "Report", "Rules"]
__all__ += ["check", "predict_gaps"]


def check(
    moodle: Course,
    openlms: MigratedCourse,
    gaps_list: list[KnownGap] | None = None,
    rules_: Rules | None = None,
    now: datetime | None = None,
) -> Report:
    ctx = Context(moodle, openlms, rules_ or Rules.load(), now or datetime.now(UTC))
    structure.run(ctx)  # places every activity; the rest compare what was placed
    content.run(ctx)
    quizzes.run(ctx)
    assignments.run(ctx)
    gaps.run(ctx)
    structure.extras(ctx)
    structure.published(ctx)
    grading.run(ctx)
    prerequisites.run(ctx)
    dates.run(ctx)
    files.run(ctx)
    rules.run(ctx)
    stale = known_gaps.apply(ctx.findings, gaps_list or [])
    return Report(
        f"{moodle.fullname} ({moodle.shortname})",
        moodle.source.backup_name,
        openlms.source,
        ctx.findings,
        stale,
    )


def predict_gaps(moodle: Course) -> list[Finding]:
    """The differences expected from the Moodle course alone, to seed a known-gaps file."""
    ctx = Context(moodle, None, Rules(), datetime.now(UTC))
    gaps.run(ctx)
    return ctx.findings
