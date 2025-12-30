# persona_engine/models.py
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class MBTIScores:
    type_code: str
    ie: int
    ns: int
    tf: int
    pj: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Persona:
    name: str
    age: int
    gender: str
    location: str
    occupation: str
    interests: List[str]
    personality_traits: List[str]
    communication_style: str
    life_goal: str
    main_concern: str
    mbti: MBTIScores
    education_level: str
    tech_savvy: str
    political_leaning: str
    religion: str
    risk_tolerance: str
    financial_attitude: str
    time_orientation: str

    seed: int = 0
    library_hash: str = ""
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["mbti"] = self.mbti.to_dict()
        return d
