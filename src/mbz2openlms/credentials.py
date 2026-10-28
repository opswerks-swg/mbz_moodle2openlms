"""Spot credentials in course text: passwords, keys and tokens.

Shared by the converter (to list them as manual follow-ups) and the checker's review rules
(to fail a course that still contains them). Matches are shown truncated, never in full.
"""

from __future__ import annotations

import re

from lxml import etree
from lxml import html as lxml_html

# Blocks an instructor edits as one line: the unit a credential is removed in.
BLOCKS = ("p", "li", "td", "th", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "dd", "dt")

PATTERNS = {
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|github_pat_\w{22,}"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "password or key assignment": re.compile(
        r"\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)"
        r"\s*[:=]\s*['\"]?[^\s'\"<]{6,}",
        re.I,
    ),
    "credentials in URL": re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@\"'<>]+:[^/\s@\"'<>]+@", re.I),
}


def find(text: str) -> list[tuple[str, str]]:
    """(kind, truncated match) for every credential-like string in ``text``."""
    found = []
    for kind, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            value = match.group(0)
            cut = max(value.find(":"), value.find("="), value.find("@")) + 1 or 4
            found.append((kind, value[: min(cut + 4, len(value) - 2)] + "…"))
    return found


def blocks_with_credentials(root: etree._Element) -> list[etree._Element]:
    """The innermost blocks (paragraph, list item, cell, …) whose text holds a credential."""
    return [
        el
        for el in root.iter(*BLOCKS)
        if find(el.text_content())
        and not any(find(c.text_content()) for c in el.iterdescendants(*BLOCKS))
    ]


def without_credentials(html: str) -> str:
    """Plain text of ``html`` minus every block holding a credential (and any credential left
    outside a block): what must remain once the runbook's "remove credentials" step is done."""
    if not html or not html.strip():
        return ""
    try:
        root = lxml_html.fragment_fromstring(html, create_parent="div")
    except (etree.ParserError, ValueError):
        return redact(html)
    for el in blocks_with_credentials(root):
        tail = el.tail
        el.clear()
        el.tail = tail
    return redact(etree.tostring(root, encoding="unicode", method="html"))


def redact(text: str) -> str:
    """``text`` without anything credential-like."""
    for pattern in PATTERNS.values():
        text = pattern.sub(" ", text)
    return text
