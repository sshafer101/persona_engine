from __future__ import annotations

from typing import Set

from .models import Persona


def score_compatibility(judge: Persona, candidate: Persona) -> float:
    """
    Lightweight deterministic compatibility heuristic.

    Higher is "more compatible" for long-term preference.
    """
    jd = judge.to_dict()
    cd = candidate.to_dict()

    score = 0.0

    j_interests: Set[str] = set(jd.get("interests") or [])
    c_interests: Set[str] = set(cd.get("interests") or [])
    score += 2.5 * len(j_interests.intersection(c_interests))

    j_traits: Set[str] = set(jd.get("personality_traits") or [])
    c_traits: Set[str] = set(cd.get("personality_traits") or [])
    score += 1.5 * len(j_traits.intersection(c_traits))

    for key, w in [
        ("communication_style", 1.0),
        ("political_leaning", 0.7),
        ("religion", 0.6),
        ("risk_tolerance", 0.8),
        ("financial_attitude", 0.8),
        ("time_orientation", 0.8),
    ]:
        if jd.get(key) and jd.get(key) == cd.get(key):
            score += w

    # Mild preference for closer age.
    try:
        score += max(0.0, 1.0 - (abs(int(jd["age"]) - int(cd["age"])) / 50.0))
    except Exception:
        pass

    return score


def score_mutual(a: Persona, b: Persona) -> float:
    return 0.5 * (score_compatibility(a, b) + score_compatibility(b, a))

