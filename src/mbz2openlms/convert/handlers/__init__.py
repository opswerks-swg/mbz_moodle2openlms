"""One handler per Moodle module type: ``handler(activity, build) -> Units | None``."""

from __future__ import annotations

from collections.abc import Callable

from ...moodle.model import Activity
from ..build import Build, Units
from . import assign, content, feedback, quiz

Handler = Callable[[Activity, Build], Units | None]

HANDLERS: dict[str, Handler] = {
    "assign": assign.assign,
    "book": content.book,
    "feedback": feedback.feedback,
    "folder": content.files,
    "label": content.label,
    "page": content.page,
    "quiz": quiz.quiz,
    "resource": content.files,
    "url": content.url,
}
# Activities that become a plain unit; consecutive ones share a subsection.
SIMPLE = {"page", "label", "url", "resource", "folder"}
# Not learner-facing: nothing to convert.
SKIPPED = {"qbank", "subsection"}
