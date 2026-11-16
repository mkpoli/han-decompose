"""The identifiers of the data format: fonts, designs, glyphs, structures, components and cuts.

`docs/format.md` (2) states each form. Every identifier is a string that stays the same across
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
#: A GlyphWiki glyph name, with the revision suffix its versions carry.
_NAME = r"[0-9a-z_-]+(?:@[0-9]+)?"
_SELECTOR = rf"(?:U\+{_POINT}(?:\.{_VARIATION})?|gid\.{_NUMBER}|name\.{_NAME})"
_PATH = rf"(?:-|{_NUMBER}(?:\.{_NUMBER})*)"
_STEP = rf"[0-9a-f]{{8}}-[a-z]+:{_PATH}"
_IDC = "[⿰-⿿㇯]"
#: A variation selector as a character, which may follow a component.
_VARIATION_CHARS = "[\ufe00-\ufe0f\U000e0100-\U000e01ef]?"

FONT = re.compile(rf"(?P<slug>{_SLUG})@(?P<version>[0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*)")
SELECTOR = re.compile(
    rf"U\+(?P<base>{_POINT})(?:\.(?P<selector>{_VARIATION}))?|gid\.(?P<gid>{_NUMBER})|name\.(?P<name>{_NAME})"
)
GLYPH = re.compile(rf"(?P<font>{_FONT})/(?P<selector>{_SELECTOR})")
STEP = re.compile(rf"(?P<structure>[0-9a-f]{{8}})-(?P<method>[a-z]+):(?P<path>{_PATH})")
CUT = re.compile(rf"(?P<glyph>{_FONT}/{_SELECTOR})(?P<steps>(?:~{_STEP})+)")
STRUCTURE = re.compile(r"s\.[0-9a-f]{8}")
#: The code point a GlyphWiki name starts with: `u793e-j`, `u20b36`.
_NAMED_POINT = re.compile(rf"u({_POINT.lower()})(?![0-9a-f])")

#: What a subtree starts with: the ideographic description characters U+2FF0–U+2FFF and U+31EF.
OPERATORS = frozenset(ARITY)

_COMPONENT = {
    "u": re.compile(rf"{_POINT}(?:\.{_VARIATION})?"),
    "ids": re.compile(rf"{_IDC}.+"),
    "x": re.compile(r"X-[0-9]{5}"),
    "bsp": re.compile(_NUMBER),
    "chise": re.compile(r"[^&;\s:]+"),
    "ucv": re.compile(r"[0-9a-f]+\.[1-9][0-9]*"),
    "aj1": re.compile(_NUMBER),
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


def name_selector(name: str) -> str:
    """The selector of a GlyphWiki glyph by its name: `name.u793e-j`."""
    out = f"name.{name}"
    if not SELECTOR.fullmatch(out):
        raise ValueError(f"{name!r} is not a glyph name.")
    return out


def selected(selector: str) -> str | None:
    """The character or variation sequence a selector names; None for a glyph index or a name."""
    match = SELECTOR.fullmatch(selector)
    if match is None:
        raise ValueError(f"{selector!r} is not a glyph selector.")
    if match["base"] is None:
        return None
    return chr(int(match["base"], 16)) + (chr(int(match["selector"], 16)) if match["selector"] else "")


def shard(selector: str) -> str:
    """The shard that holds a glyph: its code point's block of 256 in hex, at least three digits
    (`050` for U+50AC, `20b` for U+20B36); `gid` for a glyph no code point reaches. A glyph
    selected by name goes by the code point its name starts with (`079` for `name.u793e-j`), and
    in `name` where its name holds none (`name.cdp-8bf9`)."""
    match = SELECTOR.fullmatch(selector)
    if match is None:
        raise ValueError(f"{selector!r} is not a glyph selector.")
    if match["gid"] is not None:
        return "gid"
    if match["name"] is not None:
        named = _NAMED_POINT.match(match["name"])
        return f"{int(named[1], 16) >> 8:03x}" if named else "name"
    return f"{int(match['base'], 16) >> 8:03x}"


def order(selector: str) -> tuple[int, int, int, str]:
    """The order glyphs of one font are written in: by code point and variation selector, then by
    index, then by name."""
    match = SELECTOR.fullmatch(selector)
    if match is None:
        raise ValueError(f"{selector!r} is not a glyph selector.")
    if match["gid"] is not None:
        return (1, int(match["gid"]), 0, "")
    if match["name"] is not None:
        return (2, 0, 0, match["name"])
    return (0, int(match["base"], 16), int(match["selector"], 16) if match["selector"] else 0, "")


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


def structure_id(text: str) -> str:
    """`s.<h8>`: the structure whose text is `text`, the canonical tree."""
    if not text or text[0] not in OPERATORS:
        raise ValueError(f"{text!r} is not a structure: it starts with an operator.")
    return f"s.{h8(text)}"


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


class UnknownComponent(ValueError):
    """A component the notation of the format has no reference for: an entity or a numbered
    component that no ledger identifier names."""


def component_of(text: str) -> str:
    """The reference of a component as a structure writes it: a character with or without a
    variation selector, an IDS that starts with an operator, or a token `&…;` that holds a corpus
    identifier (`&bsp:42;` for BabelStone's `{42}`, `&chise:CDP-8958;`), a ledger identifier
    (`&X-00777;`) or an IDS (`&⿸⿹丅丿丨;`)."""
    if text[:1] in OPERATORS:
        return component("ids", text)
    if match := re.fullmatch(r"&(X-[0-9]{5});", text):
        return component("x", match[1])
    if match := re.fullmatch(r"&(bsp|chise):([^&;\s]+);", text):
        return component(match[1], match[2])
    if match := re.fullmatch(rf"&({_IDC}.+);", text):
        return component("ids", match[1])
    if len(text) > 1 and not re.fullmatch(rf"[^\x00-\x7f]{_VARIATION_CHARS}", text):
        raise UnknownComponent(f"{text!r} has no reference in the format.")
    return component("u", selector(text)[2:])


def written(reference: str) -> str | None:
    """A component as structures write it; None for an Adobe-Japan1 CID, which none writes, and
    for a UCV form, which is written after a component and has no text of its own."""
    kind, value = split_component(reference)
    if kind == "u":
        return "".join(chr(int(point, 16)) for point in value.split("."))
    if kind in ("x", "bsp", "chise"):
        return f"&{value};" if kind == "x" else f"&{kind}:{value};"
    if kind == "ids":
        return f"&{value};"
    return None


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


def step(structure: str, method: str, path: Sequence[int]) -> str:
    """`<h8>-<method>:<path>`: one layer of a cut, the structure's hash, the reading's method and
    the node's path in that layer."""
    out = f"{h8(structure)}-{method}:{path_text(path)}"
    if not structure or not re.fullmatch(_STEP, out):
        raise ValueError(f"{out!r} is not a step of a cut identifier.")
    return out


def cut_id(glyph: str, steps: Iterable[str]) -> str:
    """`<glyph>~<step>~<step>…`."""
    out = "~".join([glyph, *steps])
    if not CUT.fullmatch(out):
        raise ValueError(f"{out!r} is not a cut identifier.")
    return out


def split_cut_id(cut: str) -> tuple[str, list[str]]:
    """A cut identifier's glyph and its steps."""
    match = CUT.fullmatch(cut)
    if match is None:
        raise ValueError(f"{cut!r} is not a cut identifier.")
    return match["glyph"], match["steps"][1:].split("~")


def sig(component: str, contours: Iterable[int]) -> str:
    """The signature of a cut: the hash of its class reference and its contour indices,
    ascending, in decimal, all joined by single spaces. A verdict binds to a cut identifier and this
    signature together."""
    split_component(component)
    indices = sorted(set(contours))
    if not indices or indices[0] < 0:
        raise ValueError("A contour set holds at least one index, none negative.")
    return h8(" ".join([component, *map(str, indices)]))
