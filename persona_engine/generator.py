import random
from typing import List

from .models import Persona, MBTIScores


FIRST_NAMES_MALE = [
    "James", "John", "Robert", "Michael", "David",
    "Daniel", "Christopher", "Matthew", "Anthony", "Andrew",
]

FIRST_NAMES_FEMALE = [
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth",
    "Jessica", "Sarah", "Karen", "Nancy", "Lisa",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones",
    "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
]

GENDERS = ["male", "female", "nonbinary", "unspecified"]

OCCUPATIONS = [
    "software engineer", "teacher", "nurse", "sales manager",
    "student", "freelance designer", "data analyst", "mechanic",
    "small business owner", "customer support specialist",
]

INTERESTS = [
    "video games", "hiking", "reading sci fi", "cooking",
    "watching sports", "fitness", "DIY projects", "board games",
    "photography", "learning languages",
]

PERSONALITY_TRAITS = [
    "introverted", "extroverted", "detail oriented", "big picture thinker",
    "risk averse", "impulsive", "empathetic", "logical",
    "conflict avoidant", "direct and blunt",
]

COMMUNICATION_STYLES = [
    "short and direct",
    "friendly and chatty",
    "formal and precise",
    "sarcastic but good natured",
    "supportive and encouraging",
]

LIFE_GOALS = [
    "advance their career",
    "spend more time with family",
    "start a side business",
    "pay off debt",
    "travel more",
    "get healthier",
]

MAIN_CONCERNS = [
    "job security",
    "work life balance",
    "money and debt",
    "health issues",
    "time management",
    "imposter syndrome",
]

COUNTRIES = ["United States", "Canada", "United Kingdom", "Germany", "India"]
CITIES = ["New York", "London", "Berlin", "Toronto", "Mumbai", "Austin", "Seattle"]

EDUCATION_LEVELS = [
    "high school diploma",
    "some college",
    "associate degree",
    "bachelor degree",
    "master degree",
    "PhD or doctorate",
    "self taught",
]

TECH_SAVVY_LEVELS = [
    "very low - struggles with basic apps",
    "low - uses email and web but not much else",
    "medium - comfortable with most consumer tech",
    "high - power user who configures their own tools",
    "very high - builds or automates their own tools",
]

POLITICAL_LEANINGS = [
    "apolitical and generally disengaged",
    "moderate and avoids extremes",
    "leans conservative",
    "leans liberal",
    "strongly conservative",
    "strongly liberal",
    "libertarian",
    "socially liberal but fiscally conservative",
]

RELIGIONS = [
    "none and secular",
    "spiritual but not religious",
    "Christian",
    "Muslim",
    "Jewish",
    "Hindu",
    "Buddhist",
    "agnostic",
    "atheist",
]

RISK_TOLERANCE_LEVELS = [
    "very risk averse",
    "somewhat cautious",
    "moderate risk taker",
    "likes taking risks",
    "very high risk taker",
]

FINANCIAL_ATTITUDES = [
    "frugal and focused on saving",
    "balanced spender and saver",
    "impulsive spender",
    "investing focused and wealth oriented",
    "avoids thinking about money",
]

TIME_ORIENTATIONS = [
    "very present focused and spontaneous",
    "mostly present focused with some planning",
    "balanced between present and future",
    "future focused planner",
    "long term strategist who thinks in decades",
]


def _random_age(min_age: int = 18, max_age: int = 80) -> int:
    return random.randint(min_age, max_age)


def _random_gender() -> str:
    return random.choice(GENDERS)


def _random_name(gender: str) -> str:
    if gender == "male":
        first = random.choice(FIRST_NAMES_MALE)
    elif gender == "female":
        first = random.choice(FIRST_NAMES_FEMALE)
    else:
        first = random.choice(FIRST_NAMES_MALE + FIRST_NAMES_FEMALE)
    last = random.choice(LAST_NAMES)
    return f"{first} {last}"


def _random_location() -> str:
    city = random.choice(CITIES)
    country = random.choice(COUNTRIES)
    return f"{city}, {country}"


def _axis_score() -> int:
    base = random.randint(20, 80)
    jitter = random.randint(-10, 10)
    return max(0, min(100, base + jitter))


def _pick_letter(score: int, first: str, second: str) -> str:
    return first if score >= 50 else second


def _random_mbti() -> MBTIScores:
    ie = _axis_score()
    ns = _axis_score()
    tf = _axis_score()
    pj = _axis_score()

    code = "".join([
        _pick_letter(ie, "I", "E"),
        _pick_letter(ns, "N", "S"),
        _pick_letter(tf, "T", "F"),
        _pick_letter(pj, "P", "J"),
    ])

    return MBTIScores(
        type_code=code,
        ie=ie,
        ns=ns,
        tf=tf,
        pj=pj,
    )


def _sample_list(items: List[str], k: int) -> List[str]:
    k = min(k, len(items))
    return random.sample(items, k)


def generate_persona(seed: int | None = None) -> Persona:
    """
    Core generator.
    If seed is given, same seed gives the same persona.
    """
    if seed is not None:
        random.seed(seed)

    gender = _random_gender()

    return Persona(
        name=_random_name(gender),
        age=_random_age(),
        gender=gender,
        location=_random_location(),
        occupation=random.choice(OCCUPATIONS),
        interests=_sample_list(INTERESTS, 3),
        personality_traits=_sample_list(PERSONALITY_TRAITS, 3),
        communication_style=random.choice(COMMUNICATION_STYLES),
        life_goal=random.choice(LIFE_GOALS),
        main_concern=random.choice(MAIN_CONCERNS),
        mbti=_random_mbti(),
        education_level=random.choice(EDUCATION_LEVELS),
        tech_savvy=random.choice(TECH_SAVVY_LEVELS),
        political_leaning=random.choice(POLITICAL_LEANINGS),
        religion=random.choice(RELIGIONS),
        risk_tolerance=random.choice(RISK_TOLERANCE_LEVELS),
        financial_attitude=random.choice(FINANCIAL_ATTITUDES),
        time_orientation=random.choice(TIME_ORIENTATIONS),
    )


def persona_to_prompt(persona: Persona) -> str:
    p = persona.to_dict()
    traits = ", ".join(p["personality_traits"])
    interests = ", ".join(p["interests"])

    mbti = p["mbti"]
    mbti_desc = (
        f'{mbti["type_code"]} '
        f'(I/E={mbti["ie"]}, N/S={mbti["ns"]}, '
        f'T/F={mbti["tf"]}, P/J={mbti["pj"]})'
    )

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
        f"MBTI profile: {mbti_desc}. "
        f"Stay in character as this persona when responding."
    )
