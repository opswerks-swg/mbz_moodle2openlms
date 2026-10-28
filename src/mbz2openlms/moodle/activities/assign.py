"""Reader for assignments (mod_assign)."""

from __future__ import annotations

from xml.etree.ElementTree import Element

from ...safe.xml import flag, html, number, text, timestamp
from ..model import AssignDetail, Detail, FileSubmission, QuestionBank

Html = list[tuple[str, str]]


def read(el: Element, _bank: QuestionBank) -> tuple[Detail, Html]:
    plugins: dict[tuple[str, str], dict[str, str | None]] = {}
    for cfg in el.findall("plugin_configs/plugin_config"):
        key = (text(cfg, "subtype") or "", text(cfg, "plugin") or "")
        plugins.setdefault(key, {})[text(cfg, "name") or ""] = text(cfg, "value")
    submission = sorted(
        plugin
        for (subtype, plugin), cfg in plugins.items()
        if subtype == "assignsubmission" and cfg.get("enabled") == "1" and plugin != "comments"
    )
    file_cfg = plugins.get(("assignsubmission", "file"), {})
    detail = AssignDetail(
        intro_html=html(el, "intro"),
        activity_html=html(el, "activity"),
        opens=timestamp(el, "allowsubmissionsfromdate"),
        due=timestamp(el, "duedate"),
        cutoff=timestamp(el, "cutoffdate"),
        grade=number(el, "grade") or 0.0,
        submission_types=submission,
        file_submission=FileSubmission(
            max_files=int(file_cfg.get("maxfilesubmissions") or 1),
            max_bytes=int(file_cfg.get("maxsubmissionsizebytes") or 0),
            file_types=file_cfg.get("filetypeslist") or "",
        )
        if "file" in submission
        else None,
        team_submission=flag(el, "teamsubmission"),
    )
    return detail, [("intro", detail.intro_html), ("instructions", detail.activity_html)]
