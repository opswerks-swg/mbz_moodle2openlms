"""Reader for Feedback activities (mod_feedback): surveys and agreement forms."""

from __future__ import annotations

from xml.etree.ElementTree import Element

from ...safe.xml import flag, html, integer, text, timestamp
from ..model import Detail, FeedbackDetail, FeedbackItem, QuestionBank

Html = list[tuple[str, str]]
STYLES = {"r": "radio", "c": "checkbox", "d": "dropdown"}


def read(el: Element, _bank: QuestionBank) -> tuple[Detail, Html]:
    items = []
    for item in el.findall("items/item"):
        presentation = text(item, "presentation") or ""
        entry = FeedbackItem(
            id=int(item.get("id")),
            position=integer(item, "position") or 0,
            type=text(item, "typ") or "",
            name=text(item, "name") or "",
            required=flag(item, "required"),
            presentation=presentation,
        )
        if entry.type in ("multichoice", "multichoicerated") and ">>>>>" in presentation:
            # "c>>>>>a|b|c": c = checkbox, r = radio, d = dropdown. Rated choices are
            # "1####Strongly Disagree|2####Disagree|…".
            style, options = presentation.split(">>>>>", 1)
            entry.choice_style = STYLES.get(style, style)
            entry.choices = options.split("|")
        items.append(entry)
    items.sort(key=lambda i: i.position)
    detail = FeedbackDetail(
        intro_html=html(el, "intro"),
        opens=timestamp(el, "timeopen"),
        closes=timestamp(el, "timeclose"),
        page_after_submit_html=html(el, "page_after_submit"),
        items=items,
    )
    labels = [(f"label item {i.id}", i.presentation) for i in items if i.type == "label"]
    return detail, [
        ("intro", detail.intro_html),
        *labels,
        ("page after submit", detail.page_after_submit_html),
    ]
