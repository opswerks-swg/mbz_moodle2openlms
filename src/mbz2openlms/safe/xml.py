"""Parse untrusted XML.

Moodle backup XML goes through defusedxml (stdlib ElementTree API). Moodle writes SQL NULL as
the literal ``$@NULL@$``; the readers here return ``None`` for it. OLX from Studio exports and
APIs is parsed with lxml with entities and network access off.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from lxml import etree

NULL = "$@NULL@$"
OLX_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, remove_comments=True)


def parse(path: Path) -> Element:
    return ElementTree.parse(path).getroot()


def parse_olx(source: Path | bytes) -> etree._Element:
    if isinstance(source, bytes):
        return etree.fromstring(source, OLX_PARSER)
    return etree.parse(str(source), OLX_PARSER).getroot()


def text(el: Element | None, path: str) -> str | None:
    if el is None:
        return None
    node = el.find(path)
    if node is None or node.text is None or node.text == NULL:
        return None
    return node.text


def html(el: Element | None, path: str) -> str:
    """An HTML field: never None."""
    return text(el, path) or ""


def number(el: Element | None, path: str) -> float | None:
    value = text(el, path)
    if value is None or not value.strip():
        return None
    return float(value)


def integer(el: Element | None, path: str) -> int | None:
    value = number(el, path)
    return None if value is None else int(value)


def flag(el: Element | None, path: str) -> bool:
    return bool(integer(el, path))


def timestamp(el: Element | None, path: str) -> datetime | None:
    """A Unix timestamp field. Moodle uses 0 for "not set"."""
    return from_ts(integer(el, path))


def from_ts(value: int | None) -> datetime | None:
    return datetime.fromtimestamp(value, UTC) if value else None


def leaves(el: Element) -> dict[str, str | None]:
    """Each leaf child's tag mapped to its text: ``<single>1</single>`` -> ``{"single": "1"}``."""
    return {c.tag: (None if c.text == NULL else c.text) for c in el if len(c) == 0}
