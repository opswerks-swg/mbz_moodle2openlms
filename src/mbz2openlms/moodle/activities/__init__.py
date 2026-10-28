"""One reader per Moodle module type, for ``activities/<modname>_<cmid>/<modname>.xml``.

A reader returns the typed detail of the activity and its HTML fields as (label, html) pairs,
so the course reader can scan them for links and files. Unknown types get a generic reader:
name, intro and their raw settings.
"""

from __future__ import annotations

from collections.abc import Callable
from xml.etree.ElementTree import Element

from ...safe.xml import html, leaves
from ..model import Detail, GenericDetail, QuestionBank
from . import assign, content, feedback, quiz

Html = list[tuple[str, str]]
Reader = Callable[[Element, QuestionBank], tuple[Detail, Html]]

READERS: dict[str, Reader] = {
    "assign": assign.read,
    "book": content.read_book,
    "feedback": feedback.read,
    "folder": content.read_generic_files,
    "label": content.read_label,
    "page": content.read_page,
    "quiz": quiz.read,
    "resource": content.read_generic_files,
    "url": content.read_url,
}


def read(modname: str, el: Element, bank: QuestionBank) -> tuple[Detail, Html]:
    return READERS.get(modname, _generic)(el, bank)


def _generic(el: Element, _bank: QuestionBank) -> tuple[Detail, Html]:
    intro = html(el, "intro")
    # Never keep credentials (LTI consumer keys and secrets) in the model.
    settings = {
        k: v
        for k, v in leaves(el).items()
        if k not in ("intro", "password", "resourcekey", "secret")
    }
    return GenericDetail(intro_html=intro, settings=settings), [("intro", intro)]
