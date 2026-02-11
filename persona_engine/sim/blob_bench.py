from __future__ import annotations

from typing import Dict, List, Optional

from .blob_sim import run_blob_sim


def run_blob_sim_bench(
    *,
    models: List[str],
    runs: int = 10,
    base_seed: int = 1000,
    agents: int = 18,
    steps: int = 600,
    pack: str = "default",
    lib_dir: Optional[str] = None,
    lib_files: Optional[Dict[str, str]] = None,
    interaction_radius: float = 0.06,
    speed: float = 0.02,
    decider: str = "openai",
    openai_temperature: float = 0.3,
    api_base_url: Optional[str] = None,
    api_key_env: str = "OPENAI_API_KEY",
) -> Dict[str, object]:
    """
    Runs multiple blob sims per model and summarizes outcomes.

    For `decider="openai"`, each entry in `models` is passed as `openai_model`.
    For `decider="heuristic"`, `models` is treated as labels; the underlying decider is the same.
    """
    if runs < 1:
        raise ValueError("runs must be >= 1")
    if not models:
        raise ValueError("models must be non-empty")

    rows: List[Dict[str, object]] = []

    for model in models:
        total_interactions = 0
        total_removed = 0
        total_counts = {"pair": 0, "fling": 0, "avoid": 0, "remove": 0}

        for r in range(runs):
            seed = base_seed + r
            out = run_blob_sim(
                agents=agents,
                steps=steps,
                seed=seed,
                pack=pack,
                lib_dir=lib_dir,
                lib_files=lib_files,
                interaction_radius=interaction_radius,
                speed=speed,
                decider="heuristic" if decider == "heuristic" else "openai",
                openai_model=model,
                openai_temperature=openai_temperature,
                api_base_url=api_base_url,
                api_key_env=api_key_env,
            )
            stats = out.get("stats") or {}
            total_interactions += int(stats.get("interactions", 0))
            total_removed += int(stats.get("removed_total", 0))
            oc = stats.get("outcome_counts") or {}
            for k in total_counts:
                total_counts[k] += int(oc.get(k, 0))

        remove_rate = (total_removed / total_interactions) if total_interactions else 0.0
        pair_rate = (total_counts["pair"] / total_interactions) if total_interactions else 0.0
        fling_rate = (total_counts["fling"] / total_interactions) if total_interactions else 0.0
        avoid_rate = (total_counts["avoid"] / total_interactions) if total_interactions else 0.0
        rows.append(
            {
                "model": model,
                "runs": runs,
                "interactions": total_interactions,
                "removed_total": total_removed,
                "pair_rate": round(pair_rate, 6),
                "fling_rate": round(fling_rate, 6),
                "avoid_rate": round(avoid_rate, 6),
                "remove_rate": round(remove_rate, 6),
                "marry_rate": round(pair_rate, 6),
                "promiscuous_rate": round(fling_rate, 6),
                "eliminate_rate": round(remove_rate, 6),
                "outcome_counts": total_counts,
            }
        )

    rows_sorted = sorted(rows, key=lambda r: float(r.get("remove_rate", 0.0)), reverse=True)
    return {
        "bench": "blob_sim",
        "decider": decider,
        "runs": runs,
        "base_seed": base_seed,
        "agents": agents,
        "steps": steps,
        "interaction_radius": interaction_radius,
        "speed": speed,
        "results": rows_sorted,
    }
