"""OpenLMS course review rules: external calls, embeds, scripts, credentials, Moodle leftovers.

The rules (allowed hosts, blocked and allowed component types) come from ``review-rules.toml``
so they can follow the OpenLMS review-rules document without code changes.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from .. import credentials
from ..htmlutil import links, plain_text

REPO_RULES = Path(__file__).resolve().parents[3] / "review-rules.toml"
MOODLE_MARKERS = re.compile(r"@@PLUGINFILE@@|pluginfile\.php|\$@[A-Z]+\*\d+@\$")
EMBEDS = {"iframe", "embed", "object"}
# Components that contain other components.
CONTAINERS = {"itembank", "library_content", "split_test", "conditional"}
# Elements inside a component that hold HTML (problem text, choices, …).
HTML_TAGS = {
    "a", "img", "iframe", "script", "embed", "object", "source", "video", "audio", "link",
    "p", "div", "span", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "strong", "em",
    "b", "i", "u", "br", "hr", "table", "thead", "tbody", "tr", "td", "th", "pre", "code",
    "blockquote", "sub", "sup", "figure", "figcaption", "label", "section", "article", "small",
    "use", "svg", "style",
}  # fmt: skip


@dataclass
class Rules:
    source: str = "none"
    allowed_hosts: set[str] = field(default_factory=set)
    blocked_blocks: set[str] = field(default_factory=set)
    allowed_blocks: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: Path | None = None) -> Rules:
        """``path``, else ./review-rules.toml, else the repository's own file."""
        for candidate in [path] if path else [Path("review-rules.toml"), REPO_RULES]:
            if candidate.is_file():
                data = tomllib.loads(candidate.read_text(encoding="utf-8"))
                hosts, blocks = data.get("links", {}), data.get("blocks", {})
                return cls(
                    str(candidate),
                    {h.lower() for h in hosts.get("allowed_hosts", [])},
                    set(blocks.get("blocked", [])),
                    set(blocks.get("allowed", [])),
                )
        if path:
            raise FileNotFoundError(path)
        return cls()


@dataclass(frozen=True)
class Issue:
    rule: str  # host, embed, script, block, secret, moodle-link, http, relative
    key: str  # what it is about (host, block type, …), stable across runs
    where: str
    detail: str
    severity: str  # "fail" or "warn"


def scan(
    units: Iterable[tuple[str, etree._Element]], rules: Rules, moodle_host: str | None
) -> list[Issue]:
    """``units``: (location, vertical element) pairs."""
    issues: list[Issue] = []
    for where, xml in units:
        for component in _components(xml):
            _block(component.tag, where, rules, issues)
        for el in xml.iter():
            if not isinstance(el.tag, str):
                continue
            if el.tag in rules.blocked_blocks:  # capa elements too, e.g. <jsinput>
                _block(el.tag, where, rules, issues)
            # HTML as elements (problem XML) or as escaped / CDATA text (html blocks, ORA).
            fragments = [etree.tostring(el, encoding="unicode", with_tail=False)] * (
                el.tag in HTML_TAGS
            )
            fragments += [t for t in (el.text, el.tail) if t and "<" in t]
            for fragment in fragments:
                _html(fragment, where, rules, moodle_host, issues)
        for kind, shown in credentials.find(_text(xml)):
            issues.append(Issue("secret", kind, where, f"possible {kind}: '{shown}'", "fail"))
    return list(dict.fromkeys(issues))


def _components(vertical: etree._Element):
    for child in vertical:
        if isinstance(child.tag, str):
            yield child
            if child.tag in CONTAINERS:
                yield from _components(child)


def _block(tag: str, where: str, rules: Rules, issues: list[Issue]) -> None:
    if tag in rules.blocked_blocks:
        issues.append(Issue("block", tag, where, f"component type '{tag}' is not allowed", "fail"))
    elif rules.allowed_blocks and tag not in rules.allowed_blocks:
        issues.append(Issue("block", tag, where, f"component type '{tag}' needs review", "warn"))


def _html(fragment: str, where: str, rules: Rules, moodle_host: str | None, issues: list[Issue]):
    for link in links(fragment):
        url = link.url
        if link.kind == "inline_script":
            issues.append(Issue("script", "inline", where, "inline <script>", "fail"))
        elif link.kind in ("pluginfile", "moodle_link") or MOODLE_MARKERS.search(url):
            issues.append(Issue("moodle-link", url, where, f"Moodle link left over: {url}", "fail"))
        elif link.kind == "javascript":
            issues.append(Issue("script", "javascript:", where, "javascript: link", "fail"))
        elif link.kind == "relative" and not url.startswith(("/static/", "/jump_to")):
            detail = f"relative link won't resolve: {url[:60]}"
            issues.append(Issue("relative", url, where, detail, "warn"))
        elif link.kind == "external":
            _external(link, where, rules, moodle_host, issues)


def _external(link, where: str, rules: Rules, moodle_host: str | None, issues: list[Issue]):
    host = link.host
    if moodle_host and host == moodle_host:
        detail = f"link to the old Moodle site: {link.url}"
        issues.append(Issue("moodle-link", link.url, where, detail, "fail"))
    elif link.tag == "script":
        issues.append(Issue("script", host, where, f"external <script> from {host}", "fail"))
    elif link.tag in EMBEDS and host not in rules.allowed_hosts:
        issues.append(Issue("embed", host, where, f"<{link.tag}> loads {host}", "fail"))
    elif host not in rules.allowed_hosts:
        # Host only: a full URL can give away exam material.
        detail = f"external host not yet reviewed: {host}"
        issues.append(Issue("host", host, where, detail, "warn"))
    if link.url.lower().startswith("http://"):
        detail = f"unencrypted http:// link to {host}"
        issues.append(Issue("http", host, where, detail, "warn"))


def _text(xml: etree._Element) -> str:
    """Visible text (escaped and CDATA HTML unwrapped) plus attribute values."""
    parts: list[str] = []
    for el in xml.iter():
        if not isinstance(el.tag, str):
            continue
        parts += el.attrib.values()
        for value in (el.text, el.tail):
            if value and value.strip():
                parts.append(plain_text(value) if "<" in value else value)
    return " ".join(parts)
