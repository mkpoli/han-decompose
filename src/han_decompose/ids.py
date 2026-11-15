"""Ideographic description sequences as trees, in the notations of the three description sources.

A description is a prefix expression: an operator followed by its operands, each a component or a
description again. BabelStone writes an unencoded component as `{42}`, CHISE as an entity
`&CDP-8958;`, zi.tools as a stroke chain `#(丿𠃊)`; each is one component. A character keeps the
variation selector that follows it.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

#: How many operands each operator takes. `〾` marks a variant form of its one operand, `⿾` and
#: `⿿` a mirrored and a rotated one, `㇯` what is left of its first operand without its second.
ARITY: dict[str, int] = {
    **{chr(point): 2 for point in range(0x2FF0, 0x3000)},
    "⿲": 3,
    "⿳": 3,
    "㇯": 2,
    "⿾": 1,
    "⿿": 1,
    "〾": 1,
}

_ZI_NOTE = re.compile(r"\[[^\]]*\]")
_ZI_TAGS = re.compile(r"(?<!#)\([.,0-9A-Za-z]*\)$")


def _variation(char: str) -> bool:
    return 0xFE00 <= ord(char) <= 0xFE0F or 0xE0100 <= ord(char) <= 0xE01EF


def tokens(text: str) -> list[str]:
    """The operators and components of a description, in order."""
    out: list[str] = []
    at = 0
    while at < len(text):
        char = text[at]
        if char in "{&":
            end = text.find("}" if char == "{" else ";", at)
            if end < 0:
                raise ValueError(f"{text!r} opens a component at {at} and does not close it.")
            out.append(text[at : end + 1])
            at = end + 1
        elif char == "#" and text[at + 1 : at + 2] == "(":
            depth, end = 0, at + 1
            while end < len(text):
                depth += {"(": 1, ")": -1}.get(text[end], 0)
                end += 1
                if depth == 0:
                    break
            if depth:
                raise ValueError(f"{text!r} opens a stroke chain at {at} and does not close it.")
            out.append(text[at:end])
            at = end
        elif _variation(char):
            if not out or out[-1] in ARITY:
                raise ValueError(f"{text!r} has a variation selector at {at} with no character before it.")
            out[-1] += char
            at += 1
        else:
            out.append(char)
            at += 1
    return out


@dataclass(eq=False)
class Node:
    """One node of a description: its own text, and its operator and operands when it has them.

    A node that stands for a component spelled out keeps the component's text and takes the
    operator and operands of the component's own description; `opened` then holds that
    description's text.
    """

    text: str
    operator: str | None = None
    children: list["Node"] = field(default_factory=list)
    opened: str | None = None

    @property
    def leaf(self) -> bool:
        return self.operator is None


def parse(text: str) -> Node:
    """A description as a tree. A text that is not one whole description raises ValueError."""
    items = tokens(text)
    at = 0

    def read() -> Node:
        nonlocal at
        if at >= len(items):
            raise ValueError(f"{text!r} ends before its operands do.")
        start, token = at, items[at]
        at += 1
        children = [read() for _ in range(ARITY.get(token, 0))]
        return Node("".join(items[start:at]), token if children else None, children)

    root = read()
    if at != len(items):
        raise ValueError(f"{text!r} goes on after its description ends.")
    return root


def leaves(node: Node) -> list[Node]:
    """The components a tree ends in, in the order the description reads."""
    if node.leaf:
        return [node]
    return [leaf for child in node.children for leaf in leaves(child)]


def spelled(node: Node) -> str:
    """A tree written back out as one description, opened components spelled out."""
    if node.leaf:
        return node.text
    return (node.operator or "") + "".join(spelled(child) for child in node.children)


def walk(node: Node, path: tuple[int, ...] = ()) -> Iterator[tuple[tuple[int, ...], Node]]:
    """Every node of a tree with its path: the operand indices from the root."""
    yield path, node
    for index, child in enumerate(node.children):
        yield from walk(child, (*path, index))


def without_notes(text: str) -> str:
    """A zi.tools description without its notes: the source tags that follow it (`(.,H)`) and the
    notes on an operator (`[1:]`)."""
    return _ZI_TAGS.sub("", _ZI_NOTE.sub("", text))


def character(text: str) -> str | None:
    """The one character a component is, or None for anything else: a character with a variation
    selector, a numbered component, an entity, a chain, a description."""
    return text if len(text) == 1 and text not in ARITY else None
