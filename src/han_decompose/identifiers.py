"""The identifiers of the data format: fonts, glyphs, descriptions, components and cuts.

`docs/format.md` states each form. Every identifier is a string that stays the same across
rebuilds while the inputs it names are unchanged.
"""

import hashlib
import re
from collections.abc import Iterable, Sequence

from .ids import ARITY

_SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_NUMBER = r"(?:0|[1-9][0-9]*)"
_FONT = rf"{_SLUG}@[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*"
#: A code point in its one spelling: at least four hex digits, no further leading zero, no surrogate.
_POINT = r"(?:(?!D[89A-F])[0-9A-F]{4}|[1-9A-F][0-9A-F]{4}|10[0-9A-F]{4})"
#: A variation selector: U+FE00–U+FE0F or U+E0100–U+E01EF.
_VARIATION = r"(?:FE0[0-9A-F]|E01[0-9A-E][0-9A-F])"
_SELECTOR = rf"(?:U\+{_POINT}(?:\.{_VARIATION})?|gid\.{_NUMBER})"
_DESCRIPTION = rf"{_SLUG}\.[0-9a-f]{{8}}"
_PATH = rf"(?:-|{_NUMBER}(?:\.{_NUMBER})*)"

FONT = re.compile(rf"(?P<slug>{_SLUG})@(?P<version>[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)")
SELECTOR = re.compile(rf"U\+(?P<base>{_POINT})(?:\.(?P<selector>{_VARIATION}))?|gid\.(?P<gid>{_NUMBER})")
GLYPH = re.compile(rf"(?P<font>{_FONT})/(?P<selector>{_SELECTOR})")
DESCRIPTION = re.compile(rf"(?P<source>{_SLUG})\.(?P<hash>[0-9a-f]{{8}})")
CUT = re.compile(rf"(?P<glyph>{_FONT}/{_SELECTOR})~(?P<description>{_DESCRIPTION})~(?P<path>{_PATH})")

#: What a description starts with: the ideographic description characters U+2FF0–U+2FFF and
#: U+31EF, and the variation indicator U+303E that BabelStone puts before a variant form.
OPERATORS = frozenset(ARITY)

_COMPONENT = {
    "u": re.compile(rf"{_POINT}(?:\.{_VARIATION})?"),
    "bs": re.compile(_NUMBER),
    "chise": re.compile(r"[^&;\s]+"),
    "aj1": re.compile(_NUMBER),
    "zi": re.compile(r"#\(.+\)"),
    "ids": re.compile(r"[\u2ff0-\u2fff\u31ef\u303e].+"),
}


def h8(text: str) -> str:
    """The first 8 hex digits of the SHA-256 of `text` as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def font_id(slug: str, version: str) -> str:
    """`<family-slug>@<version>`."""
    out = f"{slug}@{version}"
    if not FONT.fullmatch(out):
        raise ValueError(f"{out!r} is not a font identifier.")
    return out


def selector(char: str) -> str:
    """The glyph selector of a character, alone (`U+50AC`) or with a variation selector (`U+845B.E0100`)."""
    out = "U+" + ".".join(f"{ord(c):04X}" for c in char)
    if not SELECTOR.fullmatch(out):
        raise ValueError(f"{char!r} is neither one character nor a variation sequence.")
    return out


def gid_selector(gid: int) -> str:
    """The selector of a glyph no code point reaches: `gid.1234`."""
    if gid < 0:
        raise ValueError("A glyph index is not negative.")
    return f"gid.{gid}"


def selected(selector: str) -> str | None:
    """The character or variation sequence a selector names; None for a glyph index."""
    match = SELECTOR.fullmatch(selector)
    if match is None:
        raise ValueError(f"{selector!r} is not a glyph selector.")
    if match["gid"] is not None:
        return None
    return chr(int(match["base"], 16)) + (chr(int(match["selector"], 16)) if match["selector"] else "")


def shard(selector: str) -> str:
    """The shard that holds a glyph: its code point's block of 256 in hex, at least three digits
    (`050` for U+50AC, `20b` for U+20B36); `gid` for a glyph no code point reaches."""
    match = SELECTOR.fullmatch(selector)
    if match is None:
        raise ValueError(f"{selector!r} is not a glyph selector.")
    if match["gid"] is not None:
        return "gid"
    return f"{int(match['base'], 16) >> 8:03x}"


def glyph_id(font: str, selector: str) -> str:
    """`<font>/<selector>`."""
    out = f"{font}/{selector}"
    if not GLYPH.fullmatch(out):
        raise ValueError(f"{out!r} is not a glyph identifier.")
    return out


def split_glyph_id(glyph: str) -> tuple[str, str]:
    """A glyph identifier's font and selector."""
    match = GLYPH.fullmatch(glyph)
    if match is None:
        raise ValueError(f"{glyph!r} is not a glyph identifier.")
    return match["font"], match["selector"]


def description_id(source: str, ids: str) -> str:
    """`<source>.<h8>`: the source and the hash of the description's text, which the caller gives
    without what the source attaches to it."""
    out = f"{source}.{h8(ids)}"
    if not ids or not DESCRIPTION.fullmatch(out):
        raise ValueError(f"{source!r} is not a source identifier, or the description is empty.")
    return out


def component(kind: str, value: str) -> str:
    """A component reference `<kind>:<value>`."""
    if kind not in _COMPONENT or not _COMPONENT[kind].fullmatch(value):
        raise ValueError(f"{kind}:{value} is not a component reference.")
    return f"{kind}:{value}"


def split_component(reference: str) -> tuple[str, str]:
    """A component reference's kind and value."""
    kind, _, value = reference.partition(":")
    component(kind, value)
    return kind, value


def component_of(text: str) -> str:
    """The reference of a component as a description writes it: a character with or without a
    variation selector, BabelStone's `{42}`, CHISE's `&CDP-8958;`, a zi.tools chain `#(丿𠃊)`, or a
    subtree that starts with a description character."""
    if text[:1] in OPERATORS:
        return component("ids", text)
    if text.startswith("#("):
        return component("zi", text)
    if match := re.fullmatch(r"\{(.+)\}", text):
        return component("bs", match[1])
    if match := re.fullmatch(r"&(.+);", text):
        return component("chise", match[1])
    return component("u", selector(text)[2:])


def written(reference: str) -> str | None:
    """A component as descriptions write it; None for an Adobe-Japan1 CID, which none writes."""
    kind, value = split_component(reference)
    if kind == "u":
        return "".join(chr(int(point, 16)) for point in value.split("."))
    if kind == "bs":
        return f"{{{value}}}"
    if kind == "chise":
        return f"&{value};"
    if kind == "aj1":
        return None
    return value


def path_text(path: Sequence[int]) -> str:
    """A node's path as text: operand indices joined by dots, `-` for the root."""
    if any(index < 0 for index in path):
        raise ValueError("An operand index is not negative.")
    return ".".join(map(str, path)) or "-"


def parse_path(text: str) -> tuple[int, ...]:
    """A path read back from `path_text`."""
    if not re.fullmatch(_PATH, text):
        raise ValueError(f"{text!r} is not a path.")
    return () if text == "-" else tuple(int(index) for index in text.split("."))


def cut_id(glyph: str, description: str, path: Sequence[int]) -> str:
    """`<glyph>~<description>~<path>`."""
    out = f"{glyph}~{description}~{path_text(path)}"
    if not CUT.fullmatch(out):
        raise ValueError(f"{out!r} is not a cut identifier.")
    return out


def split_cut_id(cut: str) -> tuple[str, str, tuple[int, ...]]:
    """A cut identifier's glyph, description and path."""
    match = CUT.fullmatch(cut)
    if match is None:
        raise ValueError(f"{cut!r} is not a cut identifier.")
    return match["glyph"], match["description"], parse_path(match["path"])


def sig(component: str, contours: Iterable[int]) -> str:
    """The signature of a cut: the hash of its component reference and its contour indices,
    ascending, in decimal, all joined by single spaces. A verdict binds to a cut identifier and this
    signature together."""
    split_component(component)
    indices = sorted(set(contours))
    if not indices or indices[0] < 0:
        raise ValueError("A contour set holds at least one index, none negative.")
    return h8(" ".join([component, *map(str, indices)]))
