# persona_engine/generator.py
import random
from typing import Dict, List, Optional

from .libraries import LibraryStore
from .models import Persona, MBTIScores


_FALLBACK = {
    "genders": ["male", "female", "nonbinary", "unspecified"],
    "first_names_male": [
        "James",
        "John",
        "Robert",
        "Michael",
        "David",
        "Daniel",
        "Christopher",
        "Matthew",
        "Anthony",
        "Andrew",
    ],
    "first_names_female": ["Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Jessica", "Sarah", "Karen", "Nancy", "Lisa"],
    "last_names": ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"],
    "occupations": [
        "software engineer",
        "teacher",
        "nurse",
        "sales manager",
        "student",
        "freelance designer",
        "data analyst",
        "mechanic",
        "small business owner",
        "customer support specialist",
    ],
    "interests": [
        "video games",
        "hiking",
        "reading sci fi",
        "cooking",
        "watching sports",
        "fitness",
        "DIY projects",
        "board games",
        "photography",
        "learning languages",
    ],
    "personality_traits": [
        "introverted",
        "extroverted",
        "detail oriented",
        "big picture thinker",
        "risk averse",
        "impulsive",
        "empathetic",
        "logical",
        "conflict avoidant",
        "direct and blunt",
    ],
    "communication_styles": ["short and direct", "friendly and chatty", "formal and precise", "sarcastic but good natured", "supportive and encouraging"],
    "life_goals": ["advance their career", "spend more time with family", "start a side business", "pay off debt", "travel more", "get healthier"],
    "main_concerns": ["job security", "work life balance", "money and debt", "health issues", "time management", "imposter syndrome"],
    "countries": ["United States", "Canada", "United Kingdom", "Germany", "India"],
    "cities": ["New York", "London", "Berlin", "Toronto", "Mumbai", "Austin", "Seattle"],
    "education_levels": ["high school diploma", "some college", "associate degree", "bachelor degree", "master degree", "PhD or doctorate", "self taught"],
    "tech_savvy_levels": [
        "very low - struggles with basic apps",
        "low - uses email and web but not much else",
        "medium - comfortable with most consumer tech",
        "high - power user who configures their own tools",
        "very high - builds or automates their own tools",
    ],
    "political_leanings": [
        "apolitical and generally disengaged",
        "moderate and avoids extremes",
        "leans conservative",
        "leans liberal",
        "strongly conservative",
        "strongly liberal",
        "libertarian",
        "socially liberal but fiscally conservative",
    ],
    "religions": ["none and secular", "spiritual but not religious", "Christian", "Muslim", "Jewish", "Hindu", "Buddhist", "agnostic", "atheist"],
    "risk_tolerance_levels": ["very risk averse", "somewhat cautious", "moderate risk taker", "likes taking risks", "very high risk taker"],
    "financial_attitudes": ["frugal and focused on saving", "balanced spender and saver", "impulsive spender", "investing focused and wealth oriented", "avoids thinking about money"],
    "time_orientations": [
        "very present focused and spontaneous",
        "mostly present focused with some planning",
        "balanced between present and future",
        "future focused planner",
        "long term strategist who thinks in decades",
    ],
    "names": [],
}

# Allow users to name their library files either plural (preferred) or singular (common mistake).
# Example: education_level.json should still satisfy education_levels.
_KEY_ALIASES: Dict[str, List[str]] = {
    "communication_styles": ["communication_style"],
    "life_goals": ["life_goal"],
    "main_concerns": ["main_concern"],
    "education_levels": ["education_level"],
    "tech_savvy_levels": ["tech_savvy_level", "tech_savvy"],
    "political_leanings": ["political_leaning"],
    "religions": ["religion"],
    "risk_tolerance_levels": ["risk_tolerance", "risk_tolerance_level"],
    "financial_attitudes": ["financial_attitude"],
    "time_orientations": ["time_orientation"],
    "occupations": ["occupation"],
    "genders": ["gender"],
    "countries": ["country"],
    "cities": ["city"],
}


def _resolve_key(store: LibraryStore, key: str) -> str:
    if store.has(key):
        return key
    for alt in _KEY_ALIASES.get(key, []):
        if store.has(alt):
            return alt
    return key


def _axis_score(rng: random.Random) -> int:
    base = rng.randint(20, 80)
    jitter = rng.randint(-10, 10)
    score = base + jitter
    if score < 0:
        return 0
    if score > 100:
        return 100
    return score


def _pick_letter(score: int, first: str, second: str) -> str:
    return first if score >= 50 else second


def _random_mbti(rng: random.Random) -> MBTIScores:
    ie = _axis_score(rng)
    ns = _axis_score(rng)
    tf = _axis_score(rng)
    pj = _axis_score(rng)

    code = "".join(
        [
            _pick_letter(ie, "I", "E"),
            _pick_letter(ns, "N", "S"),
            _pick_letter(tf, "T", "F"),
            _pick_letter(pj, "P", "J"),
        ]
    )

    return MBTIScores(type_code=code, ie=ie, ns=ns, tf=tf, pj=pj)


def _pick_fallback(rng: random.Random, key: str) -> str:
    vals = _FALLBACK.get(key, [])
    if not vals:
        return ""
    return rng.choice(vals)


def _pick_unique_fallback(rng: random.Random, key: str, k: int) -> List[str]:
    vals = list(_FALLBACK.get(key, []))
    if not vals:
        return []
    k = min(k, len(vals))
    return rng.sample(vals, k)


def _pick(store: LibraryStore, rng: random.Random, key: str) -> str:
    rk = _resolve_key(store, key)
    if store.has(rk):
        return store.pick(rng, rk)
    return _pick_fallback(rng, key)


def _pick_unique(store: LibraryStore, rng: random.Random, key: str, k: int) -> List[str]:
    rk = _resolve_key(store, key)
    if store.has(rk):
        return store.pick_unique(rng, rk, k)
    return _pick_unique_fallback(rng, key, k)


def _build_name(store: LibraryStore, rng: random.Random, gender: str) -> str:
    if store.has("names"):
        return store.pick(rng, "names")

    if gender == "male":
        first = _pick(store, rng, "first_names_male")
    elif gender == "female":
        first = _pick(store, rng, "first_names_female")
    else:
        if store.has("first_names_any"):
            first = store.pick(rng, "first_names_any")
        else:
            first = rng.choice((_FALLBACK["first_names_male"] + _FALLBACK["first_names_female"]))

    last = _pick(store, rng, "last_names")
    if first and last:
        return f"{first} {last}"
    if first:
        return first
    if last:
        return last
    return "Unknown"


def generate_persona(
    seed: int | None = None,
    pack: str = "default",
    lib_dir: Optional[str] = None,
    lib_files: Optional[Dict[str, str]] = None,
) -> Persona:
    if seed is None:
        seed = random.SystemRandom().randint(0, 2**31 - 1)

    rng = random.Random(seed)
    libs = LibraryStore(pack=pack, lib_dir=lib_dir, lib_files=lib_files, lenient_json=True)
    lib_hash = libs.library_hash()

    gender = _pick(libs, rng, "genders") or "unspecified"
    name = _build_name(libs, rng, gender)

    location = ""

    if libs.has_chain(("streets", "cities", "countries")):
        picked = libs.pick_chain(rng, ("streets", "cities", "countries"))
        street = picked.get("streets", "")
        city = picked.get("cities", "")
        country = picked.get("countries", "")
        parts = [p for p in [street, city, country] if p]
        location = ", ".join(parts)

    elif libs.has_chain(("cities", "countries")):
        picked = libs.pick_chain(rng, ("cities", "countries"))
        city = picked.get("cities", "")
        country = picked.get("countries", "")
        parts = [p for p in [city, country] if p]
        location = ", ".join(parts)

    else:
        country = _pick(libs, rng, "countries")
        if libs.has_dep("cities", "countries") and country:
            city = libs.pick_dep(rng, "cities", "countries", country, fallback_child=_resolve_key(libs, "cities"))
        else:
            city = _pick(libs, rng, "cities")
        location = f"{city}, {country}".strip(", ").strip()

    occupation = _pick(libs, rng, "occupations")
    interests = _pick_unique(libs, rng, "interests", 3)
    personality_traits = _pick_unique(libs, rng, "personality_traits", 3)
    communication_style = _pick(libs, rng, "communication_styles")
    life_goal = _pick(libs, rng, "life_goals")
    main_concern = _pick(libs, rng, "main_concerns")
    education_level = _pick(libs, rng, "education_levels")
    tech_savvy = _pick(libs, rng, "tech_savvy_levels")
    political_leaning = _pick(libs, rng, "political_leanings")
    religion = _pick(libs, rng, "religions")
    risk_tolerance = _pick(libs, rng, "risk_tolerance_levels")
    financial_attitude = _pick(libs, rng, "financial_attitudes")
    time_orientation = _pick(libs, rng, "time_orientations")

    mbti = _random_mbti(rng)

    mapped = {
        "names",
        "first_names_male",
        "first_names_female",
        "first_names_any",
        "last_names",
        "genders",
        "countries",
        "cities",
        "occupations",
        "interests",
        "personality_traits",
        "communication_styles",
        "life_goals",
        "main_concerns",
        "education_levels",
        "tech_savvy_levels",
        "political_leanings",
        "religions",
        "risk_tolerance_levels",
        "financial_attitudes",
        "time_orientations",
    }

    # Also treat singular aliases as mapped so they do not leak into extras.
    for alts in _KEY_ALIASES.values():
        for a in alts:
            mapped.add(a)

    extras: Dict[str, object] = {}
    for key in libs.keys():
        if key in mapped:
            continue
        try:
            extras[key] = libs.pick(rng, key)
        except Exception:
            continue

    return Persona(
        name=name,
        age=rng.randint(18, 80),
        gender=gender,
        location=location,
        occupation=occupation,
        interests=interests,
        personality_traits=personality_traits,
        communication_style=communication_style,
        life_goal=life_goal,
        main_concern=main_concern,
        mbti=mbti,
        education_level=education_level,
        tech_savvy=tech_savvy,
        political_leaning=political_leaning,
        religion=religion,
        risk_tolerance=risk_tolerance,
        financial_attitude=financial_attitude,
        time_orientation=time_orientation,
        seed=seed,
        library_hash=lib_hash,
        extras=extras,
    )


def persona_to_prompt(persona: Persona) -> str:
    p = persona.to_dict()
    traits = ", ".join(p["personality_traits"])
    interests = ", ".join(p["interests"])

    mbti = p["mbti"]
    mbti_desc = f'{mbti["type_code"]} (I/E={mbti["ie"]}, N/S={mbti["ns"]}, T/F={mbti["tf"]}, P/J={mbti["pj"]})'

    extras = p.get("extras") or {}
    extras_bits = ""
    if extras:
        pairs = [f"{k}: {v}" for k, v in sorted(extras.items())]
        extras_bits = " Extra attributes: " + "; ".join(pairs) + "."

    return (
        f"You are role playing as {p['name']}, a {p['age']}-year-old "
        f"{p['gender']} from {p['location']}. "
        f"They work as a {p['occupation']} and have a {p['education_level']}. "
        f"Personality traits: {traits}. "
        f"Interests: {interests}. "
        f"Communication style: {p['communication_style']}. "
        f"Tech savviness: {p['tech_savvy']}. "
        f"Political leaning: {p['political_leaning']}. "
        f"Religion or worldview: {p['religion']}. "
        f"Risk tolerance: {p['risk_tolerance']}. "
        f"Financial attitude: {p['financial_attitude']}. "
        f"Time orientation: {p['time_orientation']}. "
        f"Main life goal: {p['life_goal']}. "
        f"Main concern: {p['main_concern']}. "
        f"MBTI profile: {mbti_desc}."
        f"{extras_bits} "
        "Stay in character as this persona when responding."
    )
