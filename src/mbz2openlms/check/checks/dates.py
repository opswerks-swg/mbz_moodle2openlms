"""Dates for the new run: graded or dated subsections and assignments need a future due date.

Moodle's own dates belong to the old run and are not compared.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ...moodle.model import AssignDetail, FeedbackDetail, QuizDetail
from ..context import Context
from ..findings import FAIL, PASS, WARN


def run(ctx: Context) -> None:
    dated = set()
    for cmid, node in ctx.nodes.items():
        d = ctx.moodle.activities[cmid].detail
        if isinstance(d, (QuizDetail, FeedbackDetail)) and (d.opens or d.closes):
            dated.add(id(node.sub))
    for section, sub in ctx.openlms.subsections():
        if sub.graded or id(sub) in dated:
            fix = {"action": "due", "block": sub.id, "field": "due"}
            _due(ctx, f"due|{section.name} › {sub.name}", f"subsection '{sub.name}'", sub.due, fix)
    for cmid, node in ctx.nodes.items():
        act = ctx.moodle.activities[cmid]
        if not isinstance(act.detail, AssignDetail) or not act.detail.due:
            continue
        for ora in node.find("openassessment"):
            block = ctx.openlms.block_ids.get(ora) or ora.get("url_name") or ""
            fix = {"action": "due", "block": block, "field": "submission_due"}
            _due(ctx, f"due|{act.where}", act.where, ora.get("submission_due"), fix)


def _due(ctx: Context, fid: str, where: str, due: str | None, fix: dict[str, str]) -> None:
    if not due:
        ctx.add(fid, "dates", where, WARN, "no due date set for the new run", fix)
        return
    when = _parse(due)
    if when and when < ctx.now:
        detail = f"due {due} is in the past: learners can't submit and answers may show"
        ctx.add(fid, "dates", where, FAIL, detail, fix)
    else:
        ctx.add(fid, "dates", where, PASS, f"due {due}", fix)


def _parse(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
