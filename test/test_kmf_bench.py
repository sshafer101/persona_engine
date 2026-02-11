from persona_engine.games.kmf_bench import run_kmf_bracket_bench


def test_kmf_bracket_bench_heuristic_runs():
    out = run_kmf_bracket_bench(models=["a", "b"], runs=3, base_seed=10, judge_seed=7, candidates_n=12, decider="heuristic")
    assert out["bench"] == "kmf_bracket"
    assert len(out["results"]) == 2
    for row in out["results"]:
        assert row["runs"] == 3
        assert 0.0 <= row["eliminate_rate"] <= 1.0
        assert 0.0 <= row["promiscuous_rate"] <= 1.0
        assert 0.0 <= row["marry_rate"] <= 1.0

