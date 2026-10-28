"""Prepare Moodle HTML for OLX.

HTML components keep HTML as-is, but problem and ORA XML must be well-formed, so Moodle's loose
HTML (``<br>``, ``&nbsp;``, unclosed tags) is turned into XHTML first.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from lxml import etree
from lxml import html as lxml_html

from ..htmlutil import MOODLE_LINK, PLUGINFILE

_PLUGINFILE_URL = re.compile(re.escape(PLUGINFILE) + r"/([^\"'\s<>]+)")


def rewrite_links(
    html: str, static_name: Callable[[str], str | None], on_moodle_link: Callable[[str], None]
) -> str:
    """Point embedded files at /static/ and neutralise links to other Moodle items.

    ``static_name`` maps a pluginfile path (as written) to its name under /static/, or None
    when the file is not in the backup (the link is then left as it is, for the report).
    """

    def file_repl(match: re.Match[str]) -> str:
        name = static_name(match.group(1))
        return f"/static/{name}" if name else match.group(0)

    def link_repl(match: re.Match[str]) -> str:
        on_moodle_link(match.group(0))
        return "#"

    return MOODLE_LINK.sub(link_repl, _PLUGINFILE_URL.sub(file_repl, html or ""))


def to_xhtml(fragment: str | None) -> str:
    """``fragment`` as a well-formed XHTML fragment ("" for empty input)."""
    if not fragment or not fragment.strip():
        return ""
    wrapper = lxml_html.fragment_fromstring(fragment, create_parent="div")
    for el in list(wrapper.iter(etree.Comment, etree.ProcessingInstruction)):
        parent = el.getparent()
        if el.tail:
            prev = el.getprevious()
            if prev is not None:
                prev.tail = (prev.tail or "") + el.tail
            else:
                parent.text = (parent.text or "") + el.tail
        parent.remove(el)
    out = etree.tostring(wrapper, encoding="unicode", method="xml")
    return "" if out == "<div/>" else out[len("<div>") : -len("</div>")]


def append_html(parent: etree._Element, fragment: str | None) -> None:
    """Append an HTML fragment's content to ``parent`` as XML."""
    xhtml = to_xhtml(fragment)
    if not xhtml:
        return
    wrapper = etree.fromstring(f"<div>{xhtml}</div>")
    text = wrapper.text or ""
    if len(parent):
        parent[-1].tail = (parent[-1].tail or "") + text
    else:
        parent.text = (parent.text or "") + text
    for child in list(wrapper):
        parent.append(child)


def unwrap_paragraph(fragment: str | None) -> str:
    """``<p>chown</p>`` -> ``chown``; anything richer is returned as XHTML."""
    xhtml = to_xhtml(fragment).strip()
    match = re.fullmatch(r"<p>(.*)</p>", xhtml, flags=re.S)
    if match and "<p" not in match.group(1):
        return match.group(1).strip()
    return xhtml
