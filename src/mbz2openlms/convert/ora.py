"""Open Response Assessment (ORA) components, staff-graded."""

from __future__ import annotations

import re
from datetime import datetime

from lxml import etree

from ..htmlutil import plain_text
from ..moodle.model import FileSubmission
from ..olx.model import Component
from .build import INFO, Build, olx_date

IMAGE_TYPES = {"image", "web_image", "optimised_image"}


def ora(
    b: Build,
    title: str,
    prompt_html: str,
    context_id: int | None,
    where: str,
    *,
    text_response: str,
    file_response: str,
    upload: FileSubmission | None,
    opens: datetime | None,
    due: datetime | None,
    points: int | None,
    grader_info: str = "",
) -> Component:
    """An ORA with one staff-assessment step.

    ``points`` None gives an ungraded completion rubric; otherwise one "score" criterion with
    options in 5% steps up to ``points``.
    """
    el = etree.Element(
        "openassessment",
        prompts_type="html",
        text_response=text_response,
        file_upload_response=file_response,
        allow_latex="False",
        show_rubric_during_response="False",
    )
    if file_response and upload:
        kind, extensions = _upload_type(upload.file_types)
        el.set("file_upload_type", kind)
        if extensions:
            el.set("white_listed_file_types", extensions)
        el.set("allow_multiple_files", "True" if upload.max_files > 1 else "False")
        if kind == "pdf-and-image" and upload.file_types:
            detail = f"Moodle file types '{upload.file_types}' allowed as PDF and images."
            b.note(INFO, where, detail)
    if b.opts.keep_dates:
        if opens:
            el.set("submission_start", olx_date(opens))
        if due:
            el.set("submission_due", olx_date(due))
    etree.SubElement(el, "title").text = title
    assessments = etree.SubElement(el, "assessments")
    etree.SubElement(assessments, "assessment", name="staff-assessment", required="True")
    prompt = etree.SubElement(etree.SubElement(el, "prompts"), "prompt")
    etree.SubElement(prompt, "description").text = b.rewrite(prompt_html, context_id, where)

    rubric = etree.SubElement(el, "rubric")
    criterion = etree.SubElement(rubric, "criterion", feedback="optional")
    if points is None:
        name, label, question = "completion", "Completion", "Did the learner complete the task?"
        options = [(0, "Not complete"), (1, "Complete")]
    else:
        name, label = "score", "Score"
        question = plain_text(grader_info) or f"Score out of {points} (Moodle marks)."
        steps = sorted({round(points * i / 20) for i in range(21)})
        options = [(p, f"{p} / {points}") for p in steps]
    etree.SubElement(criterion, "name").text = name
    etree.SubElement(criterion, "label").text = label
    etree.SubElement(criterion, "prompt").text = question
    for value, text in options:
        option = etree.SubElement(criterion, "option", points=str(value))
        etree.SubElement(option, "name").text = f"p{value}"
        etree.SubElement(option, "label").text = text
        etree.SubElement(option, "explanation").text = ""
    etree.SubElement(rubric, "feedbackprompt").text = "Comments for the learner (optional)."
    etree.SubElement(rubric, "feedback_default_text").text = ""
    return Component("openassessment", b.olx.url_name("ora", title), title, el, inline=True)


def _upload_type(file_types: str) -> tuple[str, str]:
    tokens = {t.strip().lower() for t in re.split(r"[,;\s]+", file_types or "") if t.strip()}
    if tokens and tokens <= IMAGE_TYPES:
        return "image", ""
    extensions = {t.lstrip(".") for t in tokens if t.startswith(".")}
    if tokens and tokens == {f".{e}" for e in extensions}:
        return "custom", ",".join(sorted(extensions))
    return "pdf-and-image", ""
