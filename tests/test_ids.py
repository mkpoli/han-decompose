import pytest

from han_decompose import identifiers as I
from han_decompose import ids


def test_a_component_of_each_notation_is_one_token() -> None:
    assert ids.tokens("⿰亻{42}") == ["⿰", "亻", "{42}"]
    assert ids.tokens("⿱&CDP-8958;⺜") == ["⿱", "&CDP-8958;", "⺜"]
    assert ids.tokens("⿹#(-𠃍㇉)一") == ["⿹", "#(-𠃍㇉)", "一"]
    assert ids.tokens("⿰葛\U000e0100刂") == ["⿰", "葛\U000e0100", "刂"]


@pytest.mark.parametrize("text", ["⿰亻{42", "⿱&CDP-8958", "⿹#(丿", "︀一", "⿰︀一二"])
def test_a_component_left_open_is_refused(text: str) -> None:
    with pytest.raises(ValueError):
        ids.tokens(text)


def test_a_description_reads_as_a_tree_and_writes_back() -> None:
    root = ids.parse("⿰亻⿱山隹")
    assert root.operator == "⿰" and [child.text for child in root.children] == ["亻", "⿱山隹"]
    assert [leaf.text for leaf in ids.leaves(root)] == ["亻", "山", "隹"]
    assert [(path, node.text) for path, node in ids.walk(root)] == [
        ((), "⿰亻⿱山隹"),
        ((0,), "亻"),
        ((1,), "⿱山隹"),
        ((1, 0), "山"),
        ((1, 1), "隹"),
    ]
    assert ids.spelled(root) == "⿰亻⿱山隹"
    assert ids.parse("山").leaf


def test_operators_take_one_two_or_three_operands() -> None:
    assert len(ids.parse("⿲彳𧗳亍").children) == 3
    assert len(ids.parse("㇯上一").children) == 2
    variant = ids.parse("〾⿻一乚")
    assert variant.operator == "〾" and variant.children[0].text == "⿻一乚"
    assert I.component_of(variant.text) == "ids:〾⿻一乚"


@pytest.mark.parametrize("text", ["⿰亻", "亻山", "⿰亻山隹", ""])
def test_a_text_that_is_not_one_description_is_refused(text: str) -> None:
    with pytest.raises(ValueError):
        ids.parse(text)


def test_an_opened_node_is_spelled_out_under_its_component() -> None:
    root = ids.parse("⿰亻崔")
    inside = ids.parse("⿱山隹")
    root.children[1] = ids.Node("崔", inside.operator, inside.children, opened="⿱山隹")
    assert ids.spelled(root) == "⿰亻⿱山隹"
    assert [node.text for _, node in ids.walk(root) if node.opened] == ["崔"]


def test_the_notes_of_zi_tools_come_off() -> None:
    assert ids.without_notes("⿻乚一(.,T)") == "⿻乚一"
    assert ids.without_notes("⿰[1:]木木(q4862.)") == "⿰木木"
    assert ids.without_notes("⿹#(-𠃍㇉)一") == "⿹#(-𠃍㇉)一"
    assert ids.without_notes("#(H)(.)") == "#(H)"


def test_only_a_bare_character_is_one() -> None:
    assert ids.character("山") == "山"
    assert all(ids.character(text) is None for text in ("{42}", "&CDP-8958;", "#(丿𠃊)", "葛\U000e0100", "⿰亻山"))
