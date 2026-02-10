from persona_engine.libraries import LibraryStore


def test_validate_catches_invalid_weights(tmp_path):
    lib_dir = tmp_path / "libs"
    lib_dir.mkdir()
    (lib_dir / "items.json").write_text(
        '[{"value": "A", "weight": "bad"}, {"value": "B", "weight": -1}]\n',
        encoding="utf-8",
    )

    libs = LibraryStore(pack="missingpack", lib_dir=str(lib_dir), lenient_json=True)
    errors = libs.validate_all()

    assert any("invalid weight" in e for e in errors)
    assert any("non-positive weight" in e for e in errors)


def test_validate_catches_empty_list(tmp_path):
    lib_dir = tmp_path / "libs"
    lib_dir.mkdir()
    (lib_dir / "items.json").write_text("[]\n", encoding="utf-8")

    libs = LibraryStore(pack="missingpack", lib_dir=str(lib_dir), lenient_json=True)
    errors = libs.validate_all()

    assert any("empty list" in e for e in errors)


def test_validate_missing_required_keys(tmp_path):
    libs = LibraryStore(pack="missingpack", lib_dir=str(tmp_path), lenient_json=True)
    errors = libs.validate_all(required_keys=["occupations"])

    assert any("missing required library: occupations" in e for e in errors)
