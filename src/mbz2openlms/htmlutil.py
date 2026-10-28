"""HTML helpers shared by the Moodle reader, the converter and the checker.

Finds links, embedded files and embeds in HTML, and reduces HTML to comparable plain text.
Nothing here knows about conversion, so the checker can use it without sharing the
converter's assumptions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

from lxml import etree
from lxml import html as lxml_html

PLUGINFILE = "@@PLUGINFILE@@"
URL_ATTRS = {"href", "src", "data", "poster"}
EMBED_TAGS = {"iframe", "script", "object", "embed"}
# Links to other course items are encoded at backup time, e.g. $@QUIZVIEWBYID*704@$.
MOODLE_LINK = re.compile(r"\$@([A-Z]+)\*(\d+)@\$")
# Tags that start a new line, so "disk<br>2." and "disk<br/> 2." give the same words.
_BLOCK_TAG = re.compile(r"<(?=/?(?:br|p|div|li|ul|ol|h[1-6]|tr|td|th|pre|table)\b)", re.I)


@dataclass(frozen=True)
class Link:
    kind: str  # pluginfile, external, relative, contact, data_uri, javascript,
    #            inline_script, moodle_link
    tag: str
    url: str

    @property
    def embed(self) -> str | None:
        return self.tag if self.tag in EMBED_TAGS else None

    @property
    def host(self) -> str:
        url = "https:" + self.url if self.url.startswith("//") else self.url
        return (urlsplit(url).hostname or "").lower()


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[tuple[str, str]] = []
        self.inline_scripts = 0
        self._script_without_src = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        urls = [value.strip() for name, value in attrs if name in URL_ATTRS and value]
        self.refs.extend((tag, url) for url in urls)
        if tag == "script" and not urls:
            self._script_without_src = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._script_without_src:
            self.inline_scripts += 1
            self._script_without_src = False


def classify(url: str) -> str:
    lowered = url.lower()
    if url.startswith(PLUGINFILE):
        return "pluginfile"
    if lowered.startswith(("http://", "https://", "//")):
        return "external"
    if lowered.startswith(("mailto:", "tel:")):
        return "contact"
    if lowered.startswith("data:"):
        return "data_uri"
    if lowered.startswith("javascript:"):
        return "javascript"
    return "relative"


def links(html: str | None) -> list[Link]:
    """Every link, file reference, embed, inline script and encoded course link in ``html``."""
    if not html:
        return []
    collector = _Collector()
    collector.feed(html)
    collector.close()
    found = [Link(classify(u), tag, u) for tag, u in collector.refs if not u.startswith("#")]
    found += [Link("inline_script", "script", "")] * collector.inline_scripts
    found += [Link("moodle_link", "", m.group(0)) for m in MOODLE_LINK.finditer(html)]
    return found


def pluginfile_name(url: str) -> str:
    """``@@PLUGINFILE@@/sub/My%20File.png?time=1`` -> ``sub/My File.png``."""
    path = url[len(PLUGINFILE) :].split("?", 1)[0].split("#", 1)[0]
    return unquote(path).lstrip("/")


def plain_text(fragment: str | None) -> str:
    """Visible text of an HTML fragment, whitespace collapsed, with a break at block tags."""
    if not fragment or not fragment.strip():
        return ""
    try:
        root = lxml_html.fragment_fromstring(_BLOCK_TAG.sub(" <", fragment), create_parent="div")
    except (etree.ParserError, ValueError):
        return " ".join(fragment.split())
    return " ".join(root.text_content().split())


def words(fragment: str | None) -> list[str]:
    return plain_text(fragment).split()
