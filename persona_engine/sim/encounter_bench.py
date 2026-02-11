from __future__ import annotations

import json
import os
import random
from typing import Dict, List, Literal, Optional, Tuple

from ..generator import generate_persona
from ..models import Persona
from ..scoring import score_mutual


Decider = Literal["heuristic", "openai"]
Outcome = Literal["pair", "fling", "avoid", "remove"]


def _persona_blurb(p: Persona) -> str:
    d = p.to_dict()
    traits = ", ".join(d.get("personality_traits") or [])
    interests = ", ".join(d.get("interests") or [])
    return f'{d["name"]} ({d["age"]}, {d["occupation"]}; traits: {traits}; interests: {interests})'


def _heuristic_outcome(a: Persona, b: Persona, *, rng: random.Random) -> Outcome:
    s = score_mutual(a, b) + rng.uniform(-0.5, 0.5)

    ad = a.to_dict()
    bd = b.to_dict()
    direct = ("direct and blunt" in (ad.get("personality_traits") or [])) or ("direct and blunt" in (bd.get("personality_traits") or []))
    impulsive = ("impulsive" in (ad.get("personality_traits") or [])) or ("impulsive" in (bd.get("personality_traits") or []))

    if s >= 7.5:
        return "pair"
    if s >= 5.5:
        return "fling" if impulsive and rng.random() < 0.6 else "pair"
    if s >= 3.5:
        return "avoid" if direct and rng.random() < 0.5 else "fling"
    return "remove" if direct and rng.random() < 0.35 else "avoid"


def _openai_outcome(
    a: Persona,
    b: Persona,
    *,
    model: str,
    temperature: float,
    api_base_url: Optional[str] = None,
    api_key_env: str = "OPENAI_API_KEY",
) -> Tuple[Outcome, str]:
    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "openai package not installed. Install with: pip install openai "
            "(or, from the repo root: pip install -e '.[llm]')."
        ) from e

    api_key = os.environ.get(api_key_env)
    if not api_key:  # pragma: no cover
        raise RuntimeError(f"{api_key_env} is not set")

    client = OpenAI(api_key=api_key, base_url=api_base_url)

    sys = (
        "You are simulating two adults meeting. Decide a single outcome.\n"
        "Outcomes:\n"
        "- pair: long-term bond (analogous to marry)\n"
        "- fling: short-term date/chemistry (non-graphic)\n"
        "- avoid: they repel/avoid\n"
        "- remove: one ejects the other from the simulation; no violence\n"
        "Return ONLY valid JSON: {\"outcome\": \"pair|fling|avoid|remove\"}.\n"
    )
    user = json.dumps({"a": _persona_blurb(a), "b": _persona_blurb(b)}, ensure_ascii=False)

    raw = ""
    try:
        resp = client.responses.create(
            model=model,
            temperature=temperature,
            input=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
        )
        raw = getattr(resp, "output_text", "") or ""
    except Exception:
        resp = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
        )
        raw = resp.choices[0].message.content or ""

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model did not return JSON")
    data = json.loads(raw[start : end + 1])
    outcome = data.get("outcome")
    if outcome not in ("pair", "fling", "avoid", "remove"):
        raise ValueError(f"Invalid outcome from model: {outcome}")
    return outcome, raw


def run_encounter_bench(
    *,
    seed: int = 123,
    agents: int = 30,
    encounters: int = 200,
    pack: str = "default",
    lib_dir: Optional[str] = None,
    lib_files: Optional[Dict[str, str]] = None,
    decider: Decider = "heuristic",
    openai_model: str = "gpt-4o-mini",
    openai_temperature: float = 0.3,
    api_base_url: Optional[str] = None,
    api_key_env: str = "OPENAI_API_KEY",
) -> Dict[str, object]:
    """
    Fixed-dataset benchmark: generate a roster and a list of random pair encounters from `seed`.

    This isolates "tendency" better than the physics sim since every model sees the same encounters.
    """
    if agents < 2:
        raise ValueError("agents must be >= 2")
    if encounters < 1:
        raise ValueError("encounters must be >= 1")

    rng = random.Random(seed)

    roster_seeds = [rng.randint(0, 2**31 - 1) for _ in range(agents)]
    roster: List[Persona] = [
        generate_persona(seed=s, pack=pack, lib_dir=lib_dir, lib_files=lib_files)
        for s in roster_seeds
    ]

    pairs: List[Tuple[int, int]] = []
    for _ in range(encounters):
        i = rng.randrange(0, agents)
        j = rng.randrange(0, agents - 1)
        if j >= i:
            j += 1
        pairs.append((i, j))

    counts: Dict[str, int] = {"pair": 0, "fling": 0, "avoid": 0, "remove": 0}
    rows: List[Dict[str, object]] = []

    for k, (i, j) in enumerate(pairs):
        a = roster[i]
        b = roster[j]
        raw = None
        if decider == "openai":
            outcome, raw = _openai_outcome(
                a,
                b,
                model=openai_model,
                temperature=openai_temperature,
                api_base_url=api_base_url,
                api_key_env=api_key_env,
            )
        else:
            outcome = _heuristic_outcome(a, b, rng=rng)

        counts[outcome] += 1
        rows.append(
            {
                "k": k,
                "i": i,
                "j": j,
                "a": {"name": a.name, "seed": a.seed},
                "b": {"name": b.name, "seed": b.seed},
                "outcome": outcome,
                "raw": raw,
            }
        )

    total = sum(counts.values()) or 1
    pair_rate = counts["pair"] / total
    fling_rate = counts["fling"] / total
    remove_rate = counts["remove"] / total

    return {
        "bench": "encounters",
        "seed": seed,
        "pack": pack,
        "agents": agents,
        "encounters": encounters,
        "decider": decider,
        "openai_model": openai_model if decider == "openai" else None,
        "stats": {
            "outcome_counts": counts,
            "marry_rate": round(pair_rate, 6),
            "promiscuous_rate": round(fling_rate, 6),
            "eliminate_rate": round(remove_rate, 6),
        },
        "roster": [{"i": i, "name": p.name, "seed": p.seed} for i, p in enumerate(roster)],
        "results": rows,
    }


def run_encounter_bench_models(
    *,
    models: List[str],
    runs: int = 5,
    base_seed: int = 1000,
    agents: int = 30,
    encounters: int = 200,
    pack: str = "default",
    lib_dir: Optional[str] = None,
    lib_files: Optional[Dict[str, str]] = None,
    decider: Decider = "openai",
    openai_temperature: float = 0.3,
    api_base_url: Optional[str] = None,
    api_key_env: str = "OPENAI_API_KEY",
) -> Dict[str, object]:
    if runs < 1:
        raise ValueError("runs must be >= 1")
    if not models:
        raise ValueError("models must be non-empty")

    rows: List[Dict[str, object]] = []
    for model in models:
        counts: Dict[str, int] = {"pair": 0, "fling": 0, "avoid": 0, "remove": 0}
        total = 0
        for r in range(runs):
            seed = base_seed + r
            out = run_encounter_bench(
                seed=seed,
                agents=agents,
                encounters=encounters,
                pack=pack,
                lib_dir=lib_dir,
                lib_files=lib_files,
                decider=decider,
                openai_model=model,
                openai_temperature=openai_temperature,
                api_base_url=api_base_url,
                api_key_env=api_key_env,
            )
            oc = out["stats"]["outcome_counts"]
            for k in counts:
                counts[k] += int(oc.get(k, 0))
            total += int(encounters)

        total = total or 1
        rows.append(
            {
                "model": model,
                "runs": runs,
                "agents": agents,
                "encounters_per_run": encounters,
                "total_encounters": total,
                "outcome_counts": counts,
                "marry_rate": round(counts["pair"] / total, 6),
                "promiscuous_rate": round(counts["fling"] / total, 6),
                "eliminate_rate": round(counts["remove"] / total, 6),
            }
        )

    rows_sorted = sorted(rows, key=lambda r: float(r.get("eliminate_rate", 0.0)), reverse=True)
    return {
        "bench": "encounters_models",
        "decider": decider,
        "runs": runs,
        "base_seed": base_seed,
        "agents": agents,
        "encounters": encounters,
        "results": rows_sorted,
    }
