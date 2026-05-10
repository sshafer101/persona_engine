# persona_engine

`persona_engine` is a deterministic persona generator for LLM role-play,
prompt building, test fixtures, and simulation-style workflows.

Give it a seed and a set of JSON libraries, and it produces the same persona
every time. That makes generated people easy to replay in tests, compare across
model changes, or use as stable fixtures in product experiments.

The package focuses on reusable persona data and modeling primitives. App UIs,
game loops, and project-specific simulations should live in separate repos.

## What It Generates

A persona is a structured profile with demographic, behavioral, and preference
fields:

- name, age, gender, and location
- occupation and education level
- interests and personality traits
- communication style
- tech savviness
- political leaning and religion/worldview
- risk tolerance, financial attitude, and time orientation
- main life goal and main concern
- MBTI-style axis scores and four-letter type code
- `seed` and `library_hash` for reproducibility
- `extras` from any custom libraries that are not part of the core schema

The same seed plus the same library data produces the same profile. If a library
changes, the `library_hash` changes too, so fixtures can tell whether the input
data changed even when the seed did not.

## MBTI Scores

Each persona includes four MBTI-style numeric axes:

```json
{
  "ie": 61,
  "ns": 85,
  "tf": 36,
  "pj": 20,
  "type_code": "INFJ"
}
```

The numbers are 0-100 scores. A score of `50` or higher selects the first letter
in the axis name; a score below `50` selects the second letter:

- `ie`: `I` for introversion at 50+, `E` for extraversion below 50
- `ns`: `N` for intuition at 50+, `S` for sensing below 50
- `tf`: `T` for thinking at 50+, `F` for feeling below 50
- `pj`: `P` for perceiving at 50+, `J` for judging below 50

Scores near 50 represent a mild preference. Scores farther from 50 represent a
stronger preference. For example, `ie=61` is moderately introverted, while
`ns=85` is strongly intuitive.

These scores affect the persona profile by determining the `type_code` and by
being included in the generated LLM prompt. The prompt gives the model both the
letter code and the raw axis strengths, so it can shade the role-play:
introverted versus extraverted, abstract versus concrete, analytical versus
values-driven, flexible versus schedule-oriented.

Important implementation note: MBTI currently acts as part of the personality
description and prompt guidance. It does not yet constrain the random selection
of occupation, interests, or the separate `personality_traits` list.

## Install

```bash
pip install -e .
```

## CLI

Show commands:

```bash
persona-engine -h
```

```text
usage: persona-engine [-h] {generate,prompt,validate-pack} ...

Deterministic persona generator

positional arguments:
  {generate,prompt,validate-pack}
    generate            Generate persona JSON
    prompt              Generate the LLM system prompt for a persona
    validate-pack       Validate relationship-aware libraries in a pack or
                        directory
```

Generate persona JSON:

```bash
persona-engine generate --seed 123
```

Example output:

```json
{
  "age": 64,
  "communication_style": "formal and precise",
  "education_level": "postgraduate certificate",
  "extras": {},
  "financial_attitude": "frugal and focused on saving",
  "gender": "male",
  "interests": [
    "watching sports",
    "coffee brewing",
    "concerts"
  ],
  "library_hash": "df7ed05c758edfe3e6e59c04c447f11c5f10a13dfb2015713674a126d18f4d40",
  "life_goal": "travel more",
  "location": "Naples, Italy",
  "main_concern": "childcare costs",
  "mbti": {
    "ie": 61,
    "ns": 85,
    "pj": 20,
    "tf": 36,
    "type_code": "INFJ"
  },
  "name": "Hunter Bryant",
  "occupation": "cybersecurity analyst",
  "personality_traits": [
    "serious",
    "stubborn",
    "big picture thinker"
  ],
  "political_leaning": "traditionalist",
  "religion": "Catholic",
  "risk_tolerance": "somewhat cautious",
  "seed": 123,
  "tech_savvy": "high - power user who configures their own tools",
  "time_orientation": "routine-oriented and schedule anchored"
}
```

Generate an LLM role-play prompt:

```bash
persona-engine prompt --seed 123
```

Example output:

```text
You are role playing as Hunter Bryant, a 64-year-old male from Naples, Italy. They work as a cybersecurity analyst and have a postgraduate certificate. Personality traits: serious, stubborn, big picture thinker. Interests: watching sports, coffee brewing, concerts. Communication style: formal and precise. Tech savviness: high - power user who configures their own tools. Political leaning: traditionalist. Religion or worldview: Catholic. Risk tolerance: somewhat cautious. Financial attitude: frugal and focused on saving. Time orientation: routine-oriented and schedule anchored. Main life goal: travel more. Main concern: childcare costs. MBTI profile: INFJ (I/E=61, N/S=85, T/F=36, P/J=20). Stay in character as this persona when responding.
```

Validate a pack or custom library overrides:

```bash
persona-engine validate-pack --pack default
persona-engine validate-pack --lib-dir ./my_libs
persona-engine validate-pack --lib occupations=./my_libs/occupations.json
```

## Library Data

Built-in data lives in `persona_engine/data/default/`.

Libraries are JSON files named after the field they feed. A basic library can be
a list of strings:

```json
[
  "teacher",
  "cybersecurity analyst",
  "small business owner"
]
```

Or a weighted list:

```json
[
  { "value": "teacher", "weight": 3 },
  { "value": "cybersecurity analyst", "weight": 1 }
]
```

Relationship-aware files use `child@parent.json` naming. For example,
`cities@countries.json` lets the generator pick a country first, then pick a
city that belongs to that country.

You can layer custom data using:

- `--lib-dir` for a directory of JSON files
- `--lib key=path` for targeted overrides

Unknown custom libraries are preserved in the generated persona under `extras`.

## Python API

```python
from persona_engine import generate_persona, persona_to_prompt

p = generate_persona(seed=42)
print(p.to_dict())
print(persona_to_prompt(p))
```

Override built-in data:

```python
from persona_engine import generate_persona

p = generate_persona(
    seed=42,
    lib_dir="./my_libs",
    lib_files={"occupations": "./custom/occupations.json"},
)
```

## Development

Run the tests:

```bash
pytest
```
