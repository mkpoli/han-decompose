import hashlib
import io
import re
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from han_decompose import pins
from han_decompose.cli import app
from han_decompose.schema import Json

ROOT = Path(__file__).parents[1]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Web:
    """Addresses and what each serves; counts every request."""

    def __init__(self, pages: dict[str, bytes]):
        self.pages = pages
        self.asked: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.asked.append(url)
        if url not in self.pages:
            raise OSError("404")
        return self.pages[url]


def font_row(data: bytes, **more: object) -> Json:
    return {"id": "test@1", "file": "Test-1.ttf", "url": "https://fonts.example/Test.ttf", "sha256": sha(data), **more}


def source_row(data: bytes, mirrors: list[str]) -> Json:
    file = {"file": "table.txt", "url": "https://tables.example/table.txt", "mirrors": mirrors, "sha256": sha(data)}
    return {"id": "table", "files": [file]}


def test_a_font_is_fetched_once_and_checked_on_every_read(tmp_path: Path) -> None:
    web = Web({"https://fonts.example/Test.ttf": b"font"})
    row = font_row(b"font")
    path = pins.font_path(row, tmp_path, download=web)
    assert path == tmp_path / "fonts" / "Test-1.ttf" and path.read_bytes() == b"font"
    assert pins.font_path(row, tmp_path, download=web) == path
    assert web.asked == ["https://fonts.example/Test.ttf"]
    path.write_bytes(b"other")
    with pytest.raises(pins.PinError, match="does not match its pinned SHA-256"):
        pins.font_path(row, tmp_path, download=web)


def test_bytes_that_differ_from_the_pin_are_never_kept(tmp_path: Path) -> None:
    web = Web({"https://fonts.example/Test.ttf": b"tampered"})
    with pytest.raises(pins.PinError, match="No address serves the pinned bytes of Test-1.ttf"):
        pins.font_path(font_row(b"font"), tmp_path, download=web)
    assert not list(tmp_path.rglob("*.ttf")) and not list(tmp_path.rglob("*.part"))


def test_a_missing_file_is_not_fetched_unasked(tmp_path: Path) -> None:
    web = Web({"https://fonts.example/Test.ttf": b"font"})
    with pytest.raises(pins.PinError, match="is not in the cache"):
        pins.font_path(font_row(b"font"), tmp_path, fetch=False, download=web)
    assert web.asked == []


def test_a_font_inside_an_archive(tmp_path: Path) -> None:
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as archive:
        archive.writestr("Test.ttf", b"font")
        archive.writestr("Other.ttf", b"other")
    data = packed.getvalue()
    web = Web({"https://fonts.example/Test.zip": data})
    row = font_row(b"font", url="https://fonts.example/Test.zip", archive={"sha256": sha(data), "member": "Test.ttf"})
    assert pins.font_path(row, tmp_path, download=web).read_bytes() == b"font"
    other = {**row, "id": "other@1", "file": "Other-1.ttf", "sha256": sha(b"other")}
    other["archive"] = {"sha256": sha(data), "member": "Other.ttf"}
    assert pins.font_path(other, tmp_path, download=web).read_bytes() == b"other"
    assert web.asked == ["https://fonts.example/Test.zip"]
    wrong = {**row, "file": "Wrong-1.ttf", "sha256": sha(b"something else")}
    with pytest.raises(pins.PinError, match="Test.ttf of https://fonts.example/Test.zip"):
        pins.font_path(wrong, tmp_path, download=web)
    absent = {**row, "file": "Absent-1.ttf", "archive": {"sha256": sha(data), "member": "Absent.ttf"}}
    with pytest.raises(pins.PinError, match="holds no Absent.ttf"):
        pins.font_path(absent, tmp_path, download=web)
    assert not (tmp_path / "fonts" / "Wrong-1.ttf").exists() and not (tmp_path / "fonts" / "Absent-1.ttf").exists()
    (kept,) = (tmp_path / "fonts").glob("*.zip")
    assert kept.name == f"{sha(data)[:16]}-Test.zip"
    kept.write_bytes(b"not the archive")
    with pytest.raises(pins.PinError, match="does not match its pinned SHA-256"):
        pins.font_path(wrong, tmp_path, download=web)


def test_a_font_comes_from_its_mirror_once_its_address_serves_a_newer_version(tmp_path: Path) -> None:
    mirror = "https://mirror.example/Test-1.ttf"
    web = Web({"https://fonts.example/Test.ttf": b"version 2", mirror: b"font"})
    path = pins.font_path(font_row(b"font", mirrors=[mirror]), tmp_path, download=web)
    assert path.read_bytes() == b"font" and web.asked == ["https://fonts.example/Test.ttf", mirror]
    stale = Web({"https://fonts.example/Test.ttf": b"version 2", mirror: b"version 3"})
    with pytest.raises(pins.PinError) as failure:
        pins.font_path(font_row(b"font", file="Stale-1.ttf", mirrors=[mirror]), tmp_path, download=stale)
    assert all(f"{url}: SHA-256" in str(failure.value) for url in ("https://fonts.example/Test.ttf", mirror))
    assert not (tmp_path / "fonts" / "Stale-1.ttf").exists() and not list(tmp_path.rglob("*.part"))


def test_an_archive_comes_from_its_mirror(tmp_path: Path) -> None:
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as archive:
        archive.writestr("Test.ttf", b"font")
    data = packed.getvalue()
    web = Web({"https://mirror.example/Test.zip": data})
    row = font_row(b"font", url="https://fonts.example/Test.zip", archive={"sha256": sha(data), "member": "Test.ttf"})
    row = {**row, "mirrors": ["https://mirror.example/Test.zip"]}
    assert pins.font_path(row, tmp_path, download=web).read_bytes() == b"font"
    assert web.asked == ["https://fonts.example/Test.zip", "https://mirror.example/Test.zip"]


def test_a_mirror_serves_what_the_first_address_no_longer_does(tmp_path: Path) -> None:
    mirror = "https://archive.example/table.txt"
    web = Web({"https://tables.example/table.txt": b"a newer edition", mirror: b"table"})
    paths = pins.source_paths(source_row(b"table", [mirror]), tmp_path, download=web)
    assert paths["table.txt"] == tmp_path / "sources" / "table" / "table.txt"
    assert paths["table.txt"].read_bytes() == b"table"
    assert web.asked == ["https://tables.example/table.txt", mirror]


def test_every_address_is_named_when_none_serves_the_pin(tmp_path: Path) -> None:
    web = Web({"https://tables.example/table.txt": b"a newer edition"})
    with pytest.raises(pins.PinError) as raised:
        pins.source_paths(source_row(b"table", ["https://archive.example/table.txt"]), tmp_path, download=web)
    assert "https://tables.example/table.txt: SHA-256" in str(raised.value)
    assert "https://archive.example/table.txt: 404" in str(raised.value)


@pytest.mark.parametrize("name", ["../escape.ttf", "/abs/escape.ttf", "sub/escape.ttf", "..", ""])
def test_a_file_name_stays_inside_the_cache(tmp_path: Path, name: str) -> None:
    web = Web({"https://fonts.example/Test.ttf": b"font", "https://tables.example/table.txt": b"table"})
    with pytest.raises(pins.PinError, match="is not a file name"):
        pins.font_path({**font_row(b"font"), "file": name}, tmp_path / "cache", download=web)
    table = source_row(b"table", [])
    table["files"][0]["file"] = name
    with pytest.raises(pins.PinError, match="is not a file name"):
        pins.source_paths(table, tmp_path / "cache", download=web)
    assert not list(tmp_path.rglob("escape.ttf")) and web.asked == []


def test_a_failed_write_leaves_no_partial_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(self: Path, target: Path) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        pins.font_path(font_row(b"font"), tmp_path, download=Web({"https://fonts.example/Test.ttf": b"font"}))
    assert not [path for path in tmp_path.rglob("*") if path.is_file()]


def _registries(monkeypatch: pytest.MonkeyPatch) -> Web:
    """Stand in two small registries, one font and two tables, and the web that serves them."""
    font = font_row(b"font")
    good, gone = source_row(b"table", []), source_row(b"lost", [])
    gone.update(id="gone", files=[{**gone["files"][0], "url": "https://tables.example/gone.txt"}])
    monkeypatch.setattr(pins, "fonts", lambda: {"fonts": [font], "designs": []})
    monkeypatch.setattr(pins, "sources", lambda: {"sources": [gone, good]})
    return Web({"https://fonts.example/Test.ttf": b"font", "https://tables.example/table.txt": b"table"})


def test_one_failure_does_not_stop_the_other_pins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    web = _registries(monkeypatch)
    fetched = []
    with pytest.raises(pins.PinError, match="gone: No address serves the pinned bytes of table.txt") as raised:
        for identifier, path in pins.fetch_all(cache=tmp_path, download=web):
            fetched.append((identifier, path.read_bytes()))
    assert fetched == [("test@1", b"font"), ("table", b"table")]
    assert "https://tables.example/gone.txt: 404" in str(raised.value)
    assert [name for name, _ in pins.fetch_all({"table"}, tmp_path, web)] == ["table"]


def test_the_fetch_command_lists_what_it_fetched_and_what_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    web = _registries(monkeypatch)
    monkeypatch.setattr(pins, "_download", web)
    monkeypatch.setattr(pins.fetch_all, "__defaults__", (None, None, web))
    result = CliRunner().invoke(app, ["fetch", "--cache", str(tmp_path)])
    assert result.exit_code == 1
    assert f"test@1\t{tmp_path / 'fonts' / 'Test-1.ttf'}" in result.output
    assert "gone: No address serves the pinned bytes of table.txt" in result.output
    assert CliRunner().invoke(app, ["fetch", "test@1", "table", "--cache", str(tmp_path)]).exit_code == 0


def test_the_downloader_reports_an_address_that_does_not_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    def answer(url: str, **options: object) -> httpx.Response:
        return httpx.Response(200 if url.endswith("/ok") else 404, content=b"bytes", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", answer)
    assert pins._download("https://tables.example/ok") == b"bytes"
    with pytest.raises(pins.DownloadError, match="404"):
        pins._download("https://tables.example/gone")


def test_citations_leave_out_what_a_row_does_not_state() -> None:
    font = {"id": "test@1", "name": "Test", "version": "1", "url": "https://fonts.example/Test.ttf", "sha256": "0" * 64}
    font.update(upem="1000", licence="OFL-1.1", copyright="Copyright Test", design="test", grain="piece")
    source = {"id": "table", "name": "Table", "url": "https://tables.example/", "role": "description", "pin": "v1"}
    source.update(retrieved="2026-11-15", licence="MIT", attribution="Table authors")
    text = pins.citations({"fonts": [font], "designs": []}, {"sources": [source]})
    assert "- Font: Test 1, 1000 units per em.\n" in text
    assert "- Licence: OFL-1.1\n" in text and "- Licence: MIT\n" in text
    assert "| File |" not in text


def test_the_licensing_page_names_every_licence_of_an_outline() -> None:
    text = (ROOT / "docs" / "licensing.md").read_text(encoding="utf-8")
    named = set(re.findall(r"^\| [^|]*\(`([^`]+)`\) \|", text, re.MULTILINE))
    used = {row["licence"] for row in pins.fonts()["fonts"]}
    # GlyphWiki's licence is named for the font the dump becomes (phase 8).
    assert named - used == {"LicenseRef-GlyphWiki"} and used == named - {"LicenseRef-GlyphWiki"}


def test_the_registries_follow_the_format() -> None:
    fonts, sources = pins.fonts(), pins.sources()
    identifiers = [row["id"] for row in fonts["fonts"]]
    assert len(set(identifiers)) == len(identifiers)
    assert len({row["file"] for row in fonts["fonts"]}) == len(identifiers)
    designs = [row["id"] for row in fonts["designs"]]
    assert len(set(designs)) == len(designs)
    for design in fonts["designs"]:
        assert set(design["chain"]) <= set(identifiers), design["id"]
        assert {pins.font(member)["design"] for member in design["chain"]} <= {design["id"]}, design["id"]
        assert {pins.font(member)["style"] for member in design["chain"]} <= {design["style"]}, design["id"]
        assert design["members"] and all(member["evidence"] for member in design["members"]), design["id"]
        assert set(design["chain"]) <= {member["font"] for member in design["members"]}, design["id"]
    assert {design["id"] for design in fonts["designs"] if not design["chain"]} == {"glyphwiki", "ipamj"}
    assert sorted(identifiers) == sorted(member for design in fonts["designs"] for member in design["chain"])
    assert [row["id"] for row in pins.chain("plangothic")] == pins.design("plangothic")["chain"]
    assert len({row["id"] for row in sources["sources"]}) == len(sources["sources"])
    for row in fonts["fonts"]:
        assert row["id"] == f"{row['id'].split('@')[0]}@{row['version']}"
        assert row["version"] in row["file"]
        assert row.get("licenceEvidence"), row["id"]
        assert row["grain"] == ("contour" if "instance" in row else "piece"), row["id"]
    for row in sources["sources"]:
        assert row["files"], row["id"]
        assert row.get("licenceEvidence"), row["id"]


def test_unknown_names() -> None:
    with pytest.raises(KeyError):
        pins.font("noto-sans-cjk-jp@9")
    with pytest.raises(KeyError):
        pins.source("oracle")
    with pytest.raises(KeyError):
        pins.chain("kaisho")
    with pytest.raises(KeyError):
        pins.design("sans")
    with pytest.raises(KeyError):
        list(pins.fetch_all({"jigmo2@20250912"}))


def test_the_readme_cites_every_pin() -> None:
    text = (ROOT / "pins" / "README.md").read_text(encoding="utf-8")
    assert text == pins.citations()
    assert CliRunner().invoke(app, ["citations"]).stdout == text
    for row in pins.fonts()["fonts"]:
        for value in (row["id"], row["sha256"], row["licence"], row["copyright"]):
            assert value in text, (row["id"], value)
    for row in pins.sources()["sources"]:
        for value in (row["id"], row["licence"], row["attribution"], *(file["sha256"] for file in row["files"])):
            assert value in text, (row["id"], value)


def test_the_cache_follows_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(pins.ENV_CACHE, str(tmp_path / "set"))
    assert pins.cache_root() == tmp_path / "set"
    monkeypatch.delenv(pins.ENV_CACHE)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert pins.cache_root() == tmp_path / "xdg" / "han-decompose"


def test_fetch_reports_a_name_that_is_not_pinned(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["fetch", "jigmo2@20250912", "--cache", str(tmp_path)])
    assert result.exit_code == 1 and "Not pinned: jigmo2@20250912." in result.output
