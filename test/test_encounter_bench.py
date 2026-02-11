from persona_engine.sim.encounter_bench import run_encounter_bench, run_encounter_bench_models


def test_encounter_bench_deterministic_heuristic():
    a = run_encounter_bench(seed=123, agents=20, encounters=50, decider="heuristic")
    b = run_encounter_bench(seed=123, agents=20, encounters=50, decider="heuristic")
    assert a["stats"] == b["stats"]
    assert a["results"] == b["results"]
    assert a["roster"] == b["roster"]


def test_encounter_bench_models_heuristic_runs():
    out = run_encounter_bench_models(models=["m1", "m2"], runs=3, base_seed=10, agents=20, encounters=40, decider="heuristic")
    assert out["bench"] == "encounters_models"
    assert len(out["results"]) == 2
    for row in out["results"]:
        assert 0.0 <= row["eliminate_rate"] <= 1.0
        assert 0.0 <= row["promiscuous_rate"] <= 1.0
        assert 0.0 <= row["marry_rate"] <= 1.0

