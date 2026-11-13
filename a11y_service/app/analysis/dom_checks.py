"""Deterministic static DOM checks.

Each check returns a CheckOutcome. A check is *executed* when it was applicable to the input; only
executed checks that found nothing wrong produce a (rule-scoped) PASS observation.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from bs4 import BeautifulSoup, NavigableString, Tag

from app.analysis.aria_data import ARIA_ATTRS, IDREF_ATTRS, VALID_ROLES
from app.analysis.html_parser import ParsedDocument, excerpt, selector_for
from app.analysis.rule_map import candidate_criteria
from app.schemas import Observation

_NON_LABELLABLE_INPUT = {"hidden", "submit", "button", "reset", "image"}
_AMBIGUOUS_LINK_TEXT = {
    "click here", "here", "more", "read more", "learn more", "link", "this link", "details",
    "continue", "click", "more info", "more...", "read more...",
}
_LANG_RE = re.compile(r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})*$")


@dataclass
class CheckOutcome:
    rule_id: str
    applicable: int = 0
    observations: list[Observation] = field(default_factory=list)
    pass_text: str = ""

    def finalize(self) -> list[Observation]:
        """Failures/manual items as emitted; add a rule-scoped PASS only if applicable and clean."""
        has_fail = any(o.status in ("fail", "unknown") for o in self.observations)
        if self.applicable and not has_fail:
            return [
                Observation(
                    rule_id=self.rule_id, status="pass", observation=self.pass_text,
                    candidate_criteria=candidate_criteria(self.rule_id),
                ),
                *self.observations,
            ]
        return self.observations


def _obs(rule: str, status: str, tag: Tag | None, text: str, impact: str | None = None) -> Observation:
    return Observation(
        rule_id=rule, status=status, impact=impact, observation=text,
        element=excerpt(tag) if tag is not None else "",
        selector=selector_for(tag) if tag is not None else "",
        candidate_criteria=candidate_criteria(rule),
    )


# ---------- accessible-name helpers ----------

def _hidden(tag: Tag) -> bool:
    return tag.has_attr("hidden") or (tag.get("aria-hidden") or "").lower() == "true"


def _content_text(tag: Tag) -> str:
    parts: list[str] = []
    for child in tag.children:
        if isinstance(child, NavigableString):
            if type(child).__name__ in ("Comment", "Doctype", "CData"):
                continue
            parts.append(str(child))
        elif isinstance(child, Tag):
            if _hidden(child) or child.name in ("script", "style"):
                continue
            if child.name == "img":
                parts.append(child.get("alt", ""))
            elif child.name == "svg":
                title = child.find("title")
                parts.append(child.get("aria-label", "") or (title.get_text() if title else ""))
            else:
                parts.append(_content_text(child))
    return " ".join(" ".join(parts).split())


def _ids(soup: BeautifulSoup) -> dict[str, list[Tag]]:
    out: dict[str, list[Tag]] = {}
    for t in soup.find_all(id=True):
        out.setdefault(t["id"], []).append(t)
    return out


def _labelledby_text(tag: Tag, ids: dict[str, list[Tag]]) -> str:
    refs = (tag.get("aria-labelledby") or "").split()
    texts = [" ".join(ids[r][0].get_text().split()) for r in refs if r in ids]
    return " ".join(t for t in texts if t).strip()


def accessible_name(tag: Tag, ids: dict[str, list[Tag]], soup: BeautifulSoup, from_content: bool = True) -> str:
    name = _labelledby_text(tag, ids)
    if name:
        return name
    if (tag.get("aria-label") or "").strip():
        return tag["aria-label"].strip()
    if tag.name == "img" or (tag.name == "input" and (tag.get("type") or "").lower() == "image"):
        if (tag.get("alt") or "").strip():
            return tag["alt"].strip()
    if tag.name == "input" and (tag.get("type") or "").lower() in ("button", "submit", "reset"):
        if (tag.get("value") or "").strip():
            return tag["value"].strip()
        if tag["type"].lower() in ("submit", "reset"):
            return tag["type"].lower()  # browser-supplied default label
    if tag.name in ("input", "select", "textarea"):
        if tag.get("id"):
            for lab in soup.find_all("label", attrs={"for": tag["id"]}):
                text = _content_text(lab)
                if text:
                    return text
        for parent in tag.parents:
            if isinstance(parent, Tag) and parent.name == "label":
                text = _content_text(parent)
                if text:
                    return text
                break
    if from_content:
        text = _content_text(tag)
        if text:
            return text
    return (tag.get("title") or "").strip()


# ---------- checks ----------

def check_html_lang(doc: ParsedDocument) -> CheckOutcome:
    out = CheckOutcome("html-has-lang", pass_text="The <html> element has a lang attribute.")
    if not doc.is_full_document:
        return out
    html = doc.soup.find("html")
    out.applicable = 1
    lang = (html.get("lang") or "").strip() if html else ""
    if not lang:
        out.observations.append(_obs("html-has-lang", "fail", html, "The document has no lang attribute on <html>.", "serious"))
    elif not _LANG_RE.match(lang):
        out.observations.append(_obs("html-lang-valid", "fail", html, f"The lang value '{lang}' is not a valid language tag.", "serious"))
    return out


def check_image_alt(doc: ParsedDocument) -> CheckOutcome:
    out = CheckOutcome("image-alt", pass_text="Every <img> has an alt attribute.")
    for img in doc.soup.find_all("img"):
        out.applicable += 1
        if _hidden(img) or img.get("role") in ("presentation", "none"):
            pass
        elif not img.has_attr("alt") and not (img.get("aria-label") or img.get("aria-labelledby") or img.get("title")):
            out.observations.append(_obs("image-alt", "fail", img, "The image has no alt attribute or other text alternative.", "critical"))
        # Whether the image is decorative / alt text is meaningful cannot be decided statically.
        out.observations.append(_obs(
            "image-alt-quality", "manual", img,
            "Confirm whether the image is decorative (alt=\"\") or informative, and that any alt text conveys its purpose.",
        ))
    for el in doc.soup.find_all(attrs={"role": "img"}):
        out.applicable += 1
        ids = _ids(doc.soup)
        if not accessible_name(el, ids, doc.soup, from_content=False) and not (el.name == "svg" and el.find("title")):
            out.observations.append(_obs("svg-img-alt" if el.name == "svg" else "role-img-alt", "fail", el,
                                         "An element with role=\"img\" has no accessible name.", "serious"))
    for inp in doc.soup.find_all("input", attrs={"type": "image"}):
        out.applicable += 1
        if not (inp.get("alt") or inp.get("aria-label") or inp.get("aria-labelledby") or "").strip():
            out.observations.append(_obs("input-image-alt", "fail", inp, "The image input has no text alternative.", "critical"))
    return out


def check_button_name(doc: ParsedDocument) -> CheckOutcome:
    out = CheckOutcome("button-name", pass_text="Every button has an accessible name.")
    ids = _ids(doc.soup)
    buttons = doc.soup.find_all(["button"]) + doc.soup.find_all(attrs={"role": "button"})
    for b in buttons:
        if _hidden(b):
            continue
        out.applicable += 1
        if not accessible_name(b, ids, doc.soup):
            out.observations.append(_obs("button-name", "fail", b, "The button has no accessible name.", "serious"))
    for i in doc.soup.find_all("input", attrs={"type": re.compile("^(button|submit|reset)$", re.I)}):
        out.applicable += 1
        if not accessible_name(i, ids, doc.soup):
            out.observations.append(_obs("input-button-name", "fail", i, "The input button has no accessible name.", "serious"))
    return out


def check_form_labels(doc: ParsedDocument) -> CheckOutcome:
    out = CheckOutcome("label", pass_text="Every form control has a programmatically associated label.")
    ids = _ids(doc.soup)
    for el in doc.soup.find_all(["input", "select", "textarea"]):
        if el.name == "input" and (el.get("type") or "text").lower() in _NON_LABELLABLE_INPUT:
            continue
        if _hidden(el):
            continue
        out.applicable += 1
        if not accessible_name(el, ids, doc.soup, from_content=False):
            rule = "select-name" if el.name == "select" else "label"
            orphan = [l for l in doc.soup.find_all("label") if not l.get("for") and not l.find(["input", "select", "textarea"])]
            hint = " A <label> exists but is not associated (missing for/id or wrapping)." if orphan else ""
            out.observations.append(_obs(rule, "fail", el, "The form control has no programmatically associated label." + hint, "critical"))
    return out


def check_links(doc: ParsedDocument) -> CheckOutcome:
    out = CheckOutcome("link-name", pass_text="Every link has an accessible name.")
    ids = _ids(doc.soup)
    for a in doc.soup.find_all("a", href=True):
        if _hidden(a):
            continue
        out.applicable += 1
        name = accessible_name(a, ids, doc.soup)
        if not name:
            out.observations.append(_obs("link-name", "fail", a, "The link has no accessible name (empty link).", "serious"))
        elif name.lower().strip(" .") in {t.strip(" .") for t in _AMBIGUOUS_LINK_TEXT}:
            out.observations.append(_obs(
                "link-text-ambiguous", "manual", a,
                f"The link text '{name}' is ambiguous out of context; confirm the purpose is clear from surrounding context.",
            ))
    return out


def check_headings(doc: ParsedDocument) -> CheckOutcome:
    out = CheckOutcome("heading-order", pass_text="Heading levels do not skip and no heading is empty.")
    ids = _ids(doc.soup)
    headings = [h for h in doc.soup.find_all(re.compile(r"^h[1-6]$")) if not _hidden(h)]
    prev = 0
    for h in headings:
        out.applicable += 1
        level = int(h.name[1])
        if not accessible_name(h, ids, doc.soup):
            out.observations.append(_obs("empty-heading", "fail", h, "The heading is empty.", "minor"))
        if prev and level > prev + 1:
            out.observations.append(_obs("heading-order", "fail", h, f"Heading level jumps from h{prev} to h{level}.", "moderate"))
        prev = level
    return out


def check_landmarks(doc: ParsedDocument) -> CheckOutcome:
    out = CheckOutcome("landmark-one-main", pass_text="The document has a main landmark.")
    if not doc.is_full_document:
        return out
    out.applicable = 1
    mains = doc.soup.find_all("main") + doc.soup.find_all(attrs={"role": "main"})
    if not mains:
        out.observations.append(_obs("landmark-one-main", "fail", doc.soup.find("body"), "The document has no main landmark.", "moderate"))
    elif len(mains) > 1:
        out.observations.append(_obs("landmark-one-main", "fail", mains[1], "The document has more than one main landmark.", "moderate"))
    return out


def check_aria(doc: ParsedDocument) -> list[CheckOutcome]:
    attr_out = CheckOutcome("aria-valid-attr", pass_text="All aria-* attributes are valid WAI-ARIA attributes.")
    val_out = CheckOutcome("aria-valid-attr-value", pass_text="All supplied ARIA attribute values and ID references are valid.")
    role_out = CheckOutcome("aria-roles", pass_text="All role attributes use valid WAI-ARIA roles.")
    ids = _ids(doc.soup)
    for el in doc.soup.find_all(True):
        aria = {k: v for k, v in el.attrs.items() if k.startswith("aria-")}
        role = el.get("role")
        if role:
            role_out.applicable += 1
            tokens = role.split() if isinstance(role, str) else role
            if not any(t.lower() in VALID_ROLES for t in tokens):
                role_out.observations.append(_obs("aria-roles", "fail", el, f"The role '{role}' is not a valid WAI-ARIA role.", "serious"))
        for name, raw in aria.items():
            value = (" ".join(raw) if isinstance(raw, list) else str(raw)).strip()
            attr_out.applicable += 1
            if name not in ARIA_ATTRS:
                attr_out.observations.append(_obs("aria-valid-attr", "fail", el, f"'{name}' is not a valid WAI-ARIA attribute.", "critical"))
                continue
            val_out.applicable += 1
            allowed = ARIA_ATTRS[name]
            if allowed is not None and value.lower() not in allowed:
                val_out.observations.append(_obs("aria-valid-attr-value", "fail", el, f"'{name}=\"{value}\"' is not an allowed value.", "critical"))
            if name in IDREF_ATTRS:
                missing = [r for r in value.split() if r not in ids]
                if not value or missing:
                    val_out.observations.append(_obs(
                        "aria-valid-attr-value", "fail", el,
                        f"'{name}' references ID(s) that do not exist: {', '.join(missing) or '(empty)'}.", "critical"))
                elif name == "aria-labelledby" and not _labelledby_text(el, ids):
                    val_out.observations.append(_obs(
                        "aria-labelledby-valid", "fail", el, "'aria-labelledby' references element(s) with no text, so the accessible name is empty.", "serious"))
    return [attr_out, val_out, role_out]


def check_duplicate_ids(doc: ParsedDocument) -> CheckOutcome:
    out = CheckOutcome("duplicate-id", pass_text="All id attributes are unique.")
    ids = _ids(doc.soup)
    out.applicable = 1 if ids else 0
    referenced: set[str] = set()
    for el in doc.soup.find_all(True):
        for attr in IDREF_ATTRS:
            referenced.update((el.get(attr) or "").split())
        if el.name == "label" and el.get("for"):
            referenced.add(el["for"])
    for id_, nodes in ids.items():
        if len(nodes) < 2:
            continue
        if id_ in referenced:
            out.observations.append(_obs(
                "duplicate-id-aria", "fail", nodes[1],
                f"The id '{id_}' is used {len(nodes)} times and is referenced by a label or ARIA attribute, so the reference is ambiguous.",
                "critical"))
        else:
            out.observations.append(_obs(
                "duplicate-id", "manual", nodes[1],
                f"The id '{id_}' is used {len(nodes)} times. Not referenced by label/ARIA; SC 4.1.1 Parsing is obsolete in WCAG 2.2, so confirm assistive technology does not depend on it."))
    return out


def _rgb(value: str) -> tuple[float, float, float] | None:
    v = value.strip().lower()
    m = re.match(r"^#([0-9a-f]{3}|[0-9a-f]{6})$", v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    m = re.match(r"^rgba?\(\s*(\d+)[ ,]+(\d+)[ ,]+(\d+)", v)
    return tuple(float(x) for x in m.groups()) if m else None  # type: ignore[return-value]


def _lum(rgb: tuple[float, float, float]) -> float:
    def ch(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float | None:
    a, b = _rgb(fg), _rgb(bg)
    if a is None or b is None:
        return None
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def check_contrast(doc: ParsedDocument) -> CheckOutcome:
    """Only runs for elements carrying computed colors (data-computed-color / data-computed-bg)."""
    out = CheckOutcome("color-contrast", pass_text="Elements with supplied computed colors meet the minimum contrast ratio.")
    for el in doc.soup.find_all(attrs={"data-computed-color": True, "data-computed-bg": True}):
        ratio = contrast_ratio(el["data-computed-color"], el["data-computed-bg"])
        if ratio is None:
            continue
        out.applicable += 1
        try:
            size = float(str(el.get("data-font-size-px", "16")).replace("px", ""))
        except ValueError:
            size = 16.0
        bold = str(el.get("data-font-weight", "400")) in ("700", "bold", "800", "900")
        large = size >= 24 or (size >= 18.66 and bold)
        need = 3.0 if large else 4.5
        if ratio < need:
            out.observations.append(_obs(
                "color-contrast", "fail", el, f"Contrast ratio {ratio:.2f}:1 is below the required {need}:1.", "serious"))
    return out


def manual_review_items(doc: ParsedDocument) -> list[Observation]:
    """Checks that cannot be decided statically; surfaced only when relevant elements exist."""
    interactive = doc.soup.find_all(["a", "button", "input", "select", "textarea", "summary"]) + doc.soup.find_all(attrs={"tabindex": True})
    if not interactive:
        return []
    return [
        _obs("focus-order-manual", "manual", None, "Logical keyboard focus order cannot be determined from static HTML; test with a keyboard."),
        _obs("focus-visible-manual", "manual", None, "Visible focus indication requires rendered styles; verify in a browser."),
        _obs("target-size-manual", "manual", None, "Target size (minimum 24x24 CSS px) requires rendered geometry; not supplied."),
    ]


CHECKS: list[Callable[[ParsedDocument], CheckOutcome | list[CheckOutcome]]] = [
    check_html_lang, check_image_alt, check_button_name, check_form_labels, check_links,
    check_headings, check_landmarks, check_aria, check_duplicate_ids, check_contrast,
]


def run_all(doc: ParsedDocument) -> tuple[list[Observation], int, int]:
    """Returns (observations, checks_executed, elements_evaluated)."""
    observations: list[Observation] = []
    executed = 0
    for check in CHECKS:
        result = check(doc)
        for outcome in result if isinstance(result, list) else [result]:
            if outcome.applicable:
                executed += 1
            observations.extend(outcome.finalize())
    observations.extend(manual_review_items(doc))
    elements = len(doc.soup.find_all(True))
    return observations, executed, elements
