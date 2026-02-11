from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Sequence, Tuple

from ..generator import generate_persona, persona_to_prompt
from ..models import Persona
from ..scoring import score_compatibility


Choice = Literal["marry", "hookup", "eliminate"]
Decider = Literal["heuristic", "openai"]


@dataclass(frozen=True)
class KMFMatch:
    round_index: int
    match_index: int
    judge: Persona
    candidates: List[Persona]


@dataclass(frozen=True)
class KMFDecision:
    marry: Persona
    hookup: Optional[Persona]
    eliminate: Optional[Persona]
    raw: Optional[str] = None
    method: str = "heuristic"


def _persona_card(p: Persona) -> Dict[str, object]:
    d = p.to_dict()
    # Keep the LLM context small and game-relevant.
    return {
        "name": d["name"],
        "age": d["age"],
        "gender": d["gender"],
        "location": d["location"],
        "occupation": d["occupation"],
        "interests": d["interests"],
        "personality_traits": d["personality_traits"],
        "communication_style": d["communication_style"],
        "political_leaning": d["political_leaning"],
        "religion": d["religion"],
        "risk_tolerance": d["risk_tolerance"],
        "financial_attitude": d["financial_attitude"],
        "time_orientation": d["time_orientation"],
        "seed": d["seed"],
    }


def _heuristic_decide(judge: Persona, candidates: List[Persona]) -> KMFDecision:
    ranked = sorted(candidates, key=lambda c: score_compatibility(judge, c), reverse=True)
    marry = ranked[0]
    hookup = ranked[1] if len(ranked) >= 2 else None
    eliminate = ranked[2] if len(ranked) >= 3 else (ranked[-1] if len(ranked) == 2 else None)
    return KMFDecision(marry=marry, hookup=hookup, eliminate=eliminate, raw=None, method="heuristic")


def _extract_json_object(text: str) -> Dict[str, object]:
    # Best-effort: find the first {...} blob and parse it.
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError("No JSON object found in model output")
    blob = m.group(0)
    return json.loads(blob)


def _openai_decide(
    judge: Persona,
    candidates: List[Persona],
    *,
    model: str,
    temperature: float = 0.2,
    api_base_url: Optional[str] = None,
    api_key_env: str = "OPENAI_API_KEY",
) -> KMFDecision:
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

    judge_prompt = persona_to_prompt(judge)
    roster = [{"id": i, **_persona_card(p)} for i, p in enumerate(candidates)]

    sys = (
        judge_prompt
        + " You are playing a bracket game. Given a list of adult candidates, pick exactly one to MARRY (best long-term), "
        + "one to HOOKUP (short-term, consensual, non-graphic), and one to ELIMINATE (remove from bracket; no violence). "
        + "Be decisive and base your choices on your persona preferences."
    )
    user = (
        "Return ONLY valid JSON with keys: marry_id, hookup_id, eliminate_id.\n"
        "Constraints:\n"
        "- IDs must be distinct.\n"
        "- Choose from the provided IDs.\n"
        f"Candidates:\n{json.dumps(roster, ensure_ascii=False)}"
    )

    # Use Responses API if available; fall back to Chat Completions style if not.
    raw_text: Optional[str] = None
    try:
        resp = client.responses.create(
            model=model,
            temperature=temperature,
            input=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
        )
        raw_text = getattr(resp, "output_text", None) or ""
    except Exception:
        # Some environments pin older openai versions; support that without adding hard deps.
        resp = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
        )
        raw_text = resp.choices[0].message.content or ""

    data = _extract_json_object(raw_text)
    marry_id = int(data["marry_id"])
    hookup_id = int(data["hookup_id"])
    eliminate_id = int(data["eliminate_id"])

    if len({marry_id, hookup_id, eliminate_id}) != 3:
        raise ValueError("Model returned non-distinct ids")
    by_id = {i: p for i, p in enumerate(candidates)}
    return KMFDecision(
        marry=by_id[marry_id],
        hookup=by_id[hookup_id],
        eliminate=by_id[eliminate_id],
        raw=raw_text,
        method=f"openai:{model}",
    )


def _chunk3(items: List[Persona]) -> List[List[Persona]]:
    return [items[i : i + 3] for i in range(0, len(items), 3)]


def run_kmf_bracket(
    *,
    candidates_n: int = 24,
    judge_seed: int = 2024,
    seed: int = 123,
    pack: str = "default",
    lib_dir: Optional[str] = None,
    lib_files: Optional[Dict[str, str]] = None,
    decider: Decider = "heuristic",
    openai_model: str = "gpt-4o-mini",
    openai_temperature: float = 0.2,
    api_base_url: Optional[str] = None,
    api_key_env: str = "OPENAI_API_KEY",
) -> Dict[str, object]:
    """
    Runs an AI-only bracketed "marry / hookup / eliminate" tournament.

    Returns a JSON-serializable dict including round-by-round logs.
    """
    if candidates_n < 3:
        raise ValueError("candidates_n must be >= 3")

    rng = random.Random(seed)

    # Generate a stable roster of adult personas.
    candidate_seeds = [rng.randint(0, 2**31 - 1) for _ in range(candidates_n)]
    candidates = [
        generate_persona(seed=s, pack=pack, lib_dir=lib_dir, lib_files=lib_files)
        for s in candidate_seeds
    ]
    judge = generate_persona(seed=judge_seed, pack=pack, lib_dir=lib_dir, lib_files=lib_files)

    rounds: List[Dict[str, object]] = []
    stats = {
        "matches": 0,
        "byes": 0,
        "marry_picks": 0,
        "hookup_picks": 0,
        "eliminate_picks": 0,
    }

    alive = list(candidates)
    round_index = 1
    while len(alive) > 1:
        rng.shuffle(alive)
        groups = _chunk3(alive)

        round_log: List[Dict[str, object]] = []
        next_alive: List[Persona] = []

        for match_index, group in enumerate(groups, start=1):
            # Handle byes for last group of size 1 or 2.
            if len(group) == 1:
                stats["byes"] += 1
                next_alive.append(group[0])
                round_log.append(
                    {
                        "match": match_index,
                        "candidates": [_persona_card(group[0])],
                        "decision": {"marry": group[0].name, "hookup": None, "eliminate": None},
                        "method": "bye",
                    }
                )
                continue
            if len(group) == 2:
                # Decide a winner and eliminate the other; leave hookup empty.
                stats["matches"] += 1
                if decider == "openai":
                    # Ask the model anyway, but with a duplicated candidate to keep the schema.
                    padded = [group[0], group[1], group[1]]
                    d = _openai_decide(
                        judge,
                        padded,
                        model=openai_model,
                        temperature=openai_temperature,
                        api_base_url=api_base_url,
                        api_key_env=api_key_env,
                    )
                    marry = d.marry
                    eliminate = group[0] if marry is group[1] else group[1]
                    decision = KMFDecision(marry=marry, hookup=None, eliminate=eliminate, raw=d.raw, method=d.method)
                else:
                    # Heuristic: score and pick winner.
                    ranked = sorted(group, key=lambda c: score_compatibility(judge, c), reverse=True)
                    decision = KMFDecision(marry=ranked[0], hookup=None, eliminate=ranked[1], raw=None, method="heuristic")

                next_alive.append(decision.marry)
                stats["marry_picks"] += 1
                stats["eliminate_picks"] += 1
                round_log.append(
                    {
                        "match": match_index,
                        "candidates": [_persona_card(p) for p in group],
                        "decision": {"marry": decision.marry.name, "hookup": None, "eliminate": decision.eliminate.name if decision.eliminate else None},
                        "method": decision.method,
                    }
                )
                continue

            stats["matches"] += 1
            if decider == "openai":
                decision = _openai_decide(
                    judge,
                    group,
                    model=openai_model,
                    temperature=openai_temperature,
                    api_base_url=api_base_url,
                    api_key_env=api_key_env,
                )
            else:
                decision = _heuristic_decide(judge, group)

            next_alive.append(decision.marry)
            stats["marry_picks"] += 1
            if decision.hookup is not None:
                stats["hookup_picks"] += 1
            if decision.eliminate is not None:
                stats["eliminate_picks"] += 1
            round_log.append(
                {
                    "match": match_index,
                    "candidates": [_persona_card(p) for p in group],
                    "decision": {
                        "marry": decision.marry.name,
                        "hookup": decision.hookup.name if decision.hookup else None,
                        "eliminate": decision.eliminate.name if decision.eliminate else None,
                    },
                    "method": decision.method,
                }
            )

        rounds.append(
            {
                "round": round_index,
                "alive_in": len(alive),
                "alive_out": len(next_alive),
                "matches": round_log,
            }
        )

        alive = next_alive
        round_index += 1

        # Safety stop in case of logic regressions.
        if round_index > 1000:  # pragma: no cover
            raise RuntimeError("round limit exceeded")

    champion = alive[0]

    matches = int(stats["matches"])
    marry_rate = (stats["marry_picks"] / matches) if matches else 0.0
    hookup_rate = (stats["hookup_picks"] / matches) if matches else 0.0
    eliminate_rate = (stats["eliminate_picks"] / matches) if matches else 0.0

    return {
        "game": "kmf_bracket",
        "seed": seed,
        "pack": pack,
        "candidates_n": candidates_n,
        "judge": _persona_card(judge),
        "stats": {
            **stats,
            "marry_rate": round(marry_rate, 6),
            "promiscuous_rate": round(hookup_rate, 6),
            "eliminate_rate": round(eliminate_rate, 6),
        },
        "rounds": rounds,
        "champion": _persona_card(champion),
    }
