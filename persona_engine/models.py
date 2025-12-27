from dataclasses import dataclass, asdict
from typing import List, Dict, Any


@dataclass
class MBTIScores:
    type_code: str
    ie: int  # I vs E
    ns: int  # N vs S
    tf: int  # T vs F
    pj: int  # P vs J


@dataclass
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

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["mbti"] = asdict(self.mbti)
        return d
