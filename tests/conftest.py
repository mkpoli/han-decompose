import json
from pathlib import Path

import pytest

from han_decompose.schema import Json

GOLDEN = Path(__file__).parent / "golden"
FONT = "noto-sans-cjk-jp@2.004"


@pytest.fixture
def outlines() -> Json:
    value: Json = json.loads((GOLDEN / "outlines" / FONT / "050.json").read_text(encoding="utf-8"))
    return value


@pytest.fixture
def cuts() -> Json:
    value: Json = json.loads((GOLDEN / "cuts" / FONT / "050.json").read_text(encoding="utf-8"))
    return value
