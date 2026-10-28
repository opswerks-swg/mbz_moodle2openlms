"""Readers for content activities: page, label, URL, book, file, folder."""

from __future__ import annotations

import html as html_lib
from xml.etree.ElementTree import Element

from ...safe.xml import flag, html, integer, text
from ..model import BookDetail, Chapter, Detail, LabelDetail, PageDetail, QuestionBank, UrlDetail

Html = list[tuple[str, str]]


def read_page(el: Element, _bank: QuestionBank) -> tuple[Detail, Html]:
    detail = PageDetail(intro_html=html(el, "intro"), content_html=html(el, "content"))
    return detail, [("intro", detail.intro_html), ("content", detail.content_html)]


def read_label(el: Element, _bank: QuestionBank) -> tuple[Detail, Html]:
    detail = LabelDetail(intro_html=html(el, "intro"))
    return detail, [("text", detail.intro_html)]


def read_url(el: Element, _bank: QuestionBank) -> tuple[Detail, Html]:
    detail = UrlDetail(intro_html=html(el, "intro"), external_url=text(el, "externalurl") or "")
    link = f'<a href="{html_lib.escape(detail.external_url)}"></a>'
    return detail, [("intro", detail.intro_html), ("url", link)]


def read_book(el: Element, _bank: QuestionBank) -> tuple[Detail, Html]:
    chapters = sorted(
        (
            Chapter(
                id=int(ch.get("id")),
                pagenum=integer(ch, "pagenum") or 0,
                title=text(ch, "title") or "",
                subchapter=flag(ch, "subchapter"),
                hidden=flag(ch, "hidden"),
                content_html=html(ch, "content"),
            )
            for ch in el.findall("chapters/chapter")
        ),
        key=lambda c: c.pagenum,
    )
    detail = BookDetail(intro_html=html(el, "intro"), chapters=chapters)
    return detail, [("intro", detail.intro_html)] + [
        (f"chapter '{c.title}'", c.content_html) for c in chapters
    ]


def read_generic_files(el: Element, _bank: QuestionBank) -> tuple[Detail, Html]:
    """File and folder: the files themselves are in files.xml, by context."""
    detail = Detail(intro_html=html(el, "intro"))
    return detail, [("intro", detail.intro_html)]
