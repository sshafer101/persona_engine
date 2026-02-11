from persona_engine.games.kmf_bracket import run_kmf_bracket


def test_kmf_bracket_deterministic_heuristic():
    a = run_kmf_bracket(candidates_n=12, judge_seed=7, seed=99, decider="heuristic")
    b = run_kmf_bracket(candidates_n=12, judge_seed=7, seed=99, decider="heuristic")
    assert a["champion"]["seed"] == b["champion"]["seed"]
    assert a["champion"]["name"] == b["champion"]["name"]
    assert a["rounds"] == b["rounds"]
    assert a["stats"] == b["stats"]


def test_kmf_bracket_finishes():
    out = run_kmf_bracket(candidates_n=9, judge_seed=42, seed=123, decider="heuristic")
    assert out["champion"]["name"]
    assert len(out["rounds"]) >= 1
    assert 0.0 <= out["stats"]["eliminate_rate"] <= 1.0
