"""Assignments: an Open Response Assessment, staff-graded."""

from __future__ import annotations

from ...moodle.model import Activity, AssignDetail
from ..build import DROPPED, INFO, MANUAL, Build, Units
from ..ora import ora


def assign(act: Activity, b: Build) -> Units:
    d = act.detail
    assert isinstance(d, AssignDetail)
    text = "required" if "onlinetext" in d.submission_types else ""
    upload = d.file_submission
    file_response = ("optional" if text else "required") if upload else ""
    if not text and not file_response:
        text = "required"
        b.note(INFO, act.where, "No submission type is enabled in Moodle: text response used.")
    if d.grade < 0:
        b.note(MANUAL, act.where, "Graded with a Moodle scale: set up the rubric by hand.")
    if d.team_submission:
        b.note(DROPPED, act.where, "Group submission becomes individual submission.")
    component = ora(
        b,
        act.title,
        d.intro_html + d.activity_html,
        act.context_id,
        act.where,
        text_response=text,
        file_response=file_response,
        upload=upload,
        opens=d.opens,
        due=d.due,
        points=int(d.grade) if d.grade > 0 else None,
    )
    units = Units([b.unit(act.cmid, act.title, [component])])
    if d.grade > 0:
        units.attrs.update(b.graded(act, "Assignment"))
    b.record_date(act.where, "due", d.due)
    if d.cutoff:
        b.note(DROPPED, act.where, "Cut-off date has no equivalent: the due date is used.")
    return units
