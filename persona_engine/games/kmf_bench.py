from __future__ import annotations

from typing import Dict, List, Optional

from .kmf_bracket import run_kmf_bracket


def run_kmf_bracket_bench(
    *,
    models: List[str],
    runs: int = 10,
    base_seed: int = 1000,
    judge_seed: int = 2024,
    candidates_n: int = 24,
    pack: str = "default",
    lib_dir: Optional[str] = None,
    lib_files: Optional[Dict[str, str]] = None,
    decider: str = "openai",
    openai_temperature: float = 0.2,
    api_base_url: Optional[str] = None,
    api_key_env: str = "OPENAI_API_KEY",
) -> Dict[str, object]:
    """
    Benchmark KMF bracket across models and summarize marry/hookup/eliminate tendencies.

    For `decider="openai"`, each entry in `models` is passed as `openai_model`.
    For `decider="heuristic"`, `models` is treated as labels; the underlying decider is the same.
    """
    if runs < 1:
        raise ValueError("runs must be >= 1")
    if candidates_n < 3:
        raise ValueError("candidates_n must be >= 3")
    if not models:
        raise ValueError("models must be non-empty")

    rows: List[Dict[str, object]] = []

    for model in models:
        total_matches = 0
        total_marry = 0
        total_hookup = 0
        total_eliminate = 0
        total_byes = 0

        for r in range(runs):
            seed = base_seed + r
            out = run_kmf_bracket(
                candidates_n=candidates_n,
                judge_seed=judge_seed,
                seed=seed,
                pack=pack,
                lib_dir=lib_dir,
                lib_files=lib_files,
                decider="heuristic" if decider == "heuristic" else "openai",
                openai_model=model,
                openai_temperature=openai_temperature,
                api_base_url=api_base_url,
                api_key_env=api_key_env,
            )
            s = out.get("stats") or {}
            total_matches += int(s.get("matches", 0))
            total_byes += int(s.get("byes", 0))
            total_marry += int(s.get("marry_picks", 0))
            total_hookup += int(s.get("hookup_picks", 0))
            total_eliminate += int(s.get("eliminate_picks", 0))

        marry_rate = (total_marry / total_matches) if total_matches else 0.0
        hookup_rate = (total_hookup / total_matches) if total_matches else 0.0
        eliminate_rate = (total_eliminate / total_matches) if total_matches else 0.0

        rows.append(
            {
                "model": model,
                "runs": runs,
                "candidates_n": candidates_n,
                "judge_seed": judge_seed,
                "matches": total_matches,
                "byes": total_byes,
                "marry_picks": total_marry,
                "hookup_picks": total_hookup,
                "eliminate_picks": total_eliminate,
                "marry_rate": round(marry_rate, 6),
                "promiscuous_rate": round(hookup_rate, 6),
                "eliminate_rate": round(eliminate_rate, 6),
            }
        )

    rows_sorted = sorted(rows, key=lambda r: float(r.get("promiscuous_rate", 0.0)), reverse=True)
    return {
        "bench": "kmf_bracket",
        "decider": decider,
        "runs": runs,
        "base_seed": base_seed,
        "judge_seed": judge_seed,
        "candidates_n": candidates_n,
        "results": rows_sorted,
    }
