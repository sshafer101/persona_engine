import pytest

from persona_engine import generate_persona

def test_same_seed_same_persona():
    p1 = generate_persona(seed=42).to_dict()
    p2 = generate_persona(seed=42).to_dict()
    assert p1 == p2

@pytest.fixture
def fixed_seed():
    return 42

def test_replay(fixed_seed):
    p1 = generate_persona(seed=fixed_seed)
    p2 = generate_persona(seed=fixed_seed)
    assert p1 == p2
    assert p1.library_hash == p2.library_hash


def test_library_hash_changes_with_override(tmp_path):
    default = generate_persona(seed=123)

    lib_dir = tmp_path / "libs"
    lib_dir.mkdir()
    (lib_dir / "countries.json").write_text('["Testland"]\n', encoding="utf-8")

    overridden = generate_persona(seed=123, lib_dir=str(lib_dir))

    assert default.library_hash != overridden.library_hash
