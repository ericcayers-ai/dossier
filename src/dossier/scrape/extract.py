"""HTML → the two things this workspace stores: readable text and links.

Deliberately small. A full readability implementation is a dependency with its own
opinion about what a page means, and a job posting is not an article: the useful
part is the block text under the title, and the failure mode that matters is
*dropping* a requirement, not keeping a cookie banner.

So the rules are explicit:

* Script, style, form and embedded-object elements are removed before any text is
  read — they carry no requirement and their bodies look like prose to a naive
  extractor.
* An explicit selector wins. Without one, the first of `main`, `article`,
  `[role=main]` that carries real text wins, and `<body>` is the last resort. That
  order is why a board's navigation cannot outvote its posting.
* Block elements become paragraph breaks, so a requirements list survives as a
  list instead of one run-on line.
* `challenge_marker` names human-verification interstitials. It reads text; it does
  not act on it. Nothing in this package answers a challenge.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

#: Elements that carry no posting text, or carry code that reads like prose.
STRIP_TAGS = ("script", "style", "noscript", "template", "svg", "iframe", "object",
              "embed", "form", "button", "input", "select", "textarea", "canvas")

#: Chrome that is not the posting. Removed before a selector is applied, because a
#: board's menu otherwise becomes the first line of every archived posting. A
#: recipe can add selectors; it cannot re-enable these, and that is deliberate —
#: `<header>` is *kept* because it usually holds the page's own title.
DEFAULT_REMOVE = ("nav", "footer", "aside", "[role='navigation']", "[role='contentinfo']")

#: Elements that start or end a paragraph.
BLOCK_TAGS = frozenset({
    "address", "article", "aside", "blockquote", "br", "dd", "details", "div", "dl",
    "dt", "fieldset", "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5",
    "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section", "table",
    "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
})

#: Interstitials that mean "a human is being asked to prove themselves". Strong
#: phrases are searched in the title and the page's opening text; weak ones only in
#: the title, because a posting that mentions a captcha in its application form is
#: a posting. Case-insensitive throughout.
CHALLENGE_PHRASES = (
    "just a moment",
    "checking your browser",
    "verify you are human",
    "verify you are a human",
    "are you a robot",
    "unusual traffic",
    "enable javascript and cookies to continue",
    "checking if the site connection is secure",
)

#: Only meaningful in a `<title>`. Anywhere else these are ordinary words.
WEAK_CHALLENGE_PHRASES = ("captcha", "access denied", "attention required", "cf-challenge")

_WHITESPACE = re.compile(r"[ \t\u00a0]+")
_BLANK_RUN = re.compile(r"\n{3,}")


def _lxml():
    from lxml import html as lxml_html
    return lxml_html


def document(html: str):
    """Parse HTML leniently. A board's malformed markup is not an error worth failing on."""
    parser = _lxml().HTMLParser(recover=True, remove_comments=False, huge_tree=True)
    if not (html or "").strip():
        return _lxml().fromstring("<html><body></body></html>", parser=parser)
    return _lxml().fromstring(html, parser=parser)


def page_title(html: str) -> str:
    tree = document(html)
    for candidate in (tree.xpath("//meta[@property='og:title']/@content"),
                      tree.xpath("//title/text()")):
        if candidate and str(candidate[0]).strip():
            return _clean_line(str(candidate[0]))
    heading = tree.xpath("//h1//text()")
    return _clean_line(" ".join(heading)) if heading else ""


def meta_description(html: str) -> str:
    tree = document(html)
    for path in ("//meta[@name='description']/@content",
                 "//meta[@property='og:description']/@content"):
        values = tree.xpath(path)
        if values and str(values[0]).strip():
            return _clean_line(str(values[0]))
    return ""


def _clean_line(text: str) -> str:
    return _WHITESPACE.sub(" ", (text or "").replace("\r", " ")).strip()


def _strip(tree, remove=()) -> None:
    for tag in STRIP_TAGS:
        for node in tree.xpath(f"//{tag}"):
            node.drop_tree()
    for selector in tuple(DEFAULT_REMOVE) + tuple(remove or ()):
        try:
            for node in tree.cssselect(selector):
                node.drop_tree()
        except Exception:  # noqa: BLE001 - a bad selector is reported by the recipe, not here
            continue


def content_root(html: str, selector: str = ""):
    """The element holding the page's real text, after stripping noise."""
    tree = document(html)
    _strip(tree)
    if selector:
        try:
            chosen = tree.cssselect(selector)
        except Exception as exc:  # noqa: BLE001
            from .errors import RecipeError
            raise RecipeError(f"{selector!r} is not a selector lxml accepts: {exc}") from None
        if chosen:
            return chosen[0]
    best = None
    best_len = 0
    for path in ("//main", "//article", "//*[@role='main']"):
        for node in tree.xpath(path):
            length = len(" ".join(node.text_content().split()))
            if length > best_len:
                best, best_len = node, length
    if best is not None and best_len >= 200:
        return best
    body = tree.find("body")
    return body if body is not None else tree


def _walk(element, out: list[str]) -> None:
    tag = element.tag if isinstance(element.tag, str) else ""
    block = tag in BLOCK_TAGS
    if block:
        out.append("\n")
    if element.text:
        out.append(element.text)
    for child in element:
        _walk(child, out)
        if child.tail:
            out.append(child.tail)
    if block:
        out.append("\n")


def text(html: str, selector: str = "", remove=()) -> str:
    """The page's readable text, one paragraph per line group, noise removed."""
    root = content_root(html, selector)
    if remove:
        _strip(root, remove)
    chunks: list[str] = []
    _walk(root, chunks)
    raw = "".join(chunks).replace("\r", "")
    lines = [_clean_line(line) for line in raw.split("\n")]
    cleaned = "\n".join(lines)
    cleaned = _BLANK_RUN.sub("\n\n", cleaned)
    return cleaned.strip()


def links(html: str, base_url: str = "") -> list[dict]:
    """Every anchor on the page, de-duplicated by resolved href, in document order."""
    tree = document(html)
    seen: set[str] = set()
    rows: list[dict] = []
    for anchor in tree.iter("a"):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        resolved = urljoin(base_url, href) if base_url else href
        if resolved in seen:
            continue
        seen.add(resolved)
        rows.append({"href": resolved,
                     "text": _clean_line(anchor.text_content())[:300],
                     "rel": anchor.get("rel") or ""})
    return rows


def challenge_marker(page_title: str = "", body: str = "") -> str | None:
    """The human-verification phrase the page is showing, if any.

    Strong phrases are checked against the title and the page's opening text only:
    a posting that says "we use a captcha on our application form" is a posting,
    not a wall. The weak phrases are therefore title-only.
    """
    title = (page_title or "").casefold()
    haystack = f"{title}\n{(body or '')[:1500].casefold()}"
    for phrase in CHALLENGE_PHRASES:
        if phrase in haystack:
            return phrase
    for phrase in WEAK_CHALLENGE_PHRASES:
        if phrase in title:
            return phrase
    return None


__all__ = ["BLOCK_TAGS", "CHALLENGE_PHRASES", "DEFAULT_REMOVE", "STRIP_TAGS",
           "WEAK_CHALLENGE_PHRASES", "challenge_marker", "content_root", "document",
           "links", "meta_description", "page_title", "text"]
