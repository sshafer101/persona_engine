from persona_engine.sim.blob_sim import iter_blob_sim, run_blob_sim
from persona_engine.sim.blob_bench import run_blob_sim_bench


def test_blob_sim_deterministic_heuristic():
    a = run_blob_sim(agents=10, steps=200, seed=123, decider="heuristic")
    b = run_blob_sim(agents=10, steps=200, seed=123, decider="heuristic")
    assert a["events"] == b["events"]
    assert a["stats"] == b["stats"]
    assert a["survivors"] == b["survivors"]


def test_blob_sim_stats_sane():
    out = run_blob_sim(agents=12, steps=200, seed=1, decider="heuristic")
    stats = out["stats"]
    assert stats["interactions"] == len(out["events"])
    elim_events = sum(1 for e in out["events"] if (e.get("detail") or {}).get("reason") == "avoid_elimination")
    assert stats["removed_total"] == elim_events
    assert 0.0 <= stats["remove_rate"] <= 1.0
    assert 0.0 <= stats["promiscuous_rate"] <= 1.0
    assert 0.0 <= stats["marry_rate"] <= 1.0


def test_iter_blob_sim_yields_frames():
    frames = list(iter_blob_sim(agents=8, steps=30, seed=7, decider="heuristic"))
    assert frames
    assert "t" in frames[0]
    assert "blobs" in frames[0]


def test_iter_blob_sim_max_messages_cap():
    # Heuristic chat is small, but this ensures the arg is wired and doesn't error.
    frames = list(iter_blob_sim(agents=8, steps=60, seed=7, decider="heuristic", max_messages=1))
    assert frames


def test_iter_blob_sim_multi_interactions_tick():
    frames = list(
        iter_blob_sim(
            agents=20,
            steps=80,
            seed=5,
            decider="heuristic",
            max_interactions_per_tick=4,
            pair_cache_size=100,
        )
    )
    assert frames


def test_blob_sim_bench_heuristic_runs():
    out = run_blob_sim_bench(models=["a", "b"], runs=3, base_seed=10, decider="heuristic", agents=10, steps=120)
    assert out["bench"] == "blob_sim"
    assert len(out["results"]) == 2
    for row in out["results"]:
        assert row["runs"] == 3
        assert row["interactions"] >= 0
