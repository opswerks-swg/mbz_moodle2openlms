"""Assignments: an ORA with the instructions, the submission types and the points."""

from __future__ import annotations

from ...moodle.model import Activity, AssignDetail
from ..context import Context, Node
from ..findings import FAIL, PASS, WARN
from ..text import rubric_points
from .content import text


def run(ctx: Context) -> None:
    for cmid, node in ctx.nodes.items():
        act = ctx.moodle.activities[cmid]
        if isinstance(act.detail, AssignDetail):
            _assign(ctx, act, act.detail, node)


def _assign(ctx: Context, act: Activity, d: AssignDetail, node: Node) -> None:
    oras = node.find("openassessment")
    if not oras:
        ctx.add(f"ora|{act.where}", "assignments", act.where, FAIL, "no Open Response Assessment")
        return
    ora = oras[0]
    text(ctx, f"prompt|{act.where}", act.where, d.intro_html + " " + d.activity_html, [ora],
         what="instructions")  # fmt: skip
    problems = []
    if "file" in d.submission_types:
        if ora.get("file_upload_response") not in ("required", "optional"):
            problems.append("file upload is off")
        files = d.file_submission.max_files if d.file_submission else 1
        if files > 1 and ora.get("allow_multiple_files") not in ("True", "true"):
            problems.append(f"Moodle allows {files} files, the ORA one")
    elif ora.get("file_upload_response") == "required":
        problems.append("the ORA requires a file Moodle didn't ask for")
    if "onlinetext" in d.submission_types and ora.get("text_response") not in (
        "required",
        "optional",
    ):
        problems.append("text response is off")
    ctx.add(
        f"submission|{act.where}",
        "assignments",
        act.where,
        FAIL if problems else PASS,
        "; ".join(problems)
        or f"submission types match ({', '.join(d.submission_types) or 'none'})",
    )
    if d.grade > 0:
        points = rubric_points(ora)
        ok = abs(points - d.grade) < 0.01
        detail = f"rubric out of {points:g}, Moodle grade out of {d.grade:g}"
        ctx.add(f"points|{act.where}", "assignments", act.where, PASS if ok else WARN, detail)
