from persona_engine import generate_persona

def test_same_seed_same_persona():
    p1 = generate_persona(seed=42).to_dict()
    p2 = generate_persona(seed=42).to_dict()
    assert p1 == p2

