"""Content activities: page, label, URL, file, folder, book."""

from __future__ import annotations

import html as html_lib

from ...moodle.model import Activity, BookDetail, PageDetail, UrlDetail
from ..build import DROPPED, INFO, Build, Units


def page(act: Activity, b: Build) -> Units:
    d = act.detail
    assert isinstance(d, PageDetail)
    return _single(act, b, d.content_html)


def label(act: Activity, b: Build) -> Units:
    return _single(act, b, act.detail.intro_html)


def url(act: Activity, b: Build) -> Units:
    d = act.detail
    assert isinstance(d, UrlDetail)
    link = (
        f'<p><a href="{html_lib.escape(d.external_url)}" target="_blank" rel="noopener">'
        f"{html_lib.escape(act.title)}</a></p>"
    )
    return _single(act, b, d.intro_html + link)


def files(act: Activity, b: Build) -> Units:
    """File (resource) and folder: upload the files, list them as links."""
    content = [f for f in b.course.files_of(act.context_id) if f.filearea == "content"]
    if act.modname == "folder" and any(f.filepath != "/" for f in content):
        b.note(INFO, act.where, "Subfolders are flattened into one list.")
    items = []
    for f in content:
        if not f.present:
            b.note(DROPPED, act.where, f"File '{f.filename}' is not in the backup.")
            continue
        items.append(f'<li><a href="/static/{b.static(f)}">{html_lib.escape(f.filename)}</a></li>')
    body = act.detail.intro_html + (f"<ul>{''.join(items)}</ul>" if items else "")
    return _single(act, b, body)


def book(act: Activity, b: Build) -> Units:
    """One unit per chapter (subchapters too, in order)."""
    d = act.detail
    assert isinstance(d, BookDetail)
    units = []
    for ch in d.chapters:
        if ch.hidden:
            b.note(DROPPED, act.where, f"Hidden chapter '{ch.title}' is not converted.")
            continue
        where = f"{act.where} chapter '{ch.title}'"
        html = b.html(ch.title, ch.content_html, act.context_id, where)
        units.append(b.unit(f"{act.cmid}_{ch.pagenum}", ch.title, [html]))
    return Units(units)


def _single(act: Activity, b: Build, html: str) -> Units:
    component = b.html(act.title, html, act.context_id, act.where)
    return Units([b.unit(act.cmid, act.title, [component])])
