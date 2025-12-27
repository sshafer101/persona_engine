# Persona Engine

Deterministic persona generator SDK for LLMs, games, simulations, and training.

Given a seed, it returns a rich fake person (MBTI style personality, traits, interests, risk profile, etc) plus a ready to use LLM system prompt. Same seed, same persona.

> Status: early MVP, API may change. Suitable for experiments and prototypes.

---

## Features

- Seed based personas  
- MBTI scores that drive personality descriptions  
- Extra knobs:
  - occupation
  - interests
  - tech savviness
  - political leaning
  - religion or worldview
  - risk tolerance
  - financial attitude
  - time orientation
- LLM ready:
  - `persona_to_prompt` builds a system prompt string
  - model agnostic, works with any LLM or API
- CLI and Python API
- Deterministic:
  - same seed and same inputs give the same persona JSON

---

## Project structure

```text
persona_engine/
├── cli.py
├── persona_engine/
│   ├── __init__.py
│   ├── models.py
│   └── generator.py
└── tests/
    └── test_repeatable.py
```

- `models.py` defines the `Persona` and `MBTIScores` dataclasses  
- `generator.py` contains `generate_persona` and `persona_to_prompt`  
- `cli.py` provides a small command line interface  
- `tests/` contains basic repeatability tests

---

## Installation (local dev)

Clone the repo, then:

```bash
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On macOS / Linux:
source .venv/bin/activate

pip install -e .
```

This installs the package in editable mode so local changes are picked up.

---

## Python usage

Basic example:

```python
from persona_engine import generate_persona, persona_to_prompt

# Generate a repeatable persona
persona = generate_persona(seed=42)
data = persona.to_dict()
print(data)

# Build an LLM system prompt
system_prompt = persona_to_prompt(persona)
print(system_prompt)
```

You can send `system_prompt` as the system message to your model of choice and then chat with the persona.

---

## CLI usage

From the project root, with the virtual environment active:

Generate persona JSON:

```bash
python cli.py generate --seed 42
```

Generate an LLM system prompt:

```bash
python cli.py prompt --seed 42
```

If you omit `--seed`, a random persona is generated.

---

## Design notes

- **Deterministic by seed**  
  `generate_persona(seed=42)` will always return the same persona as long as the generator code and version are unchanged.

- **MBTI driven traits**  
  The generator first rolls MBTI axis scores (I/E, N/S, T/F, P/J), then:
  - derives the 4 letter MBTI type
  - converts scores into human readable traits such as:
    - slightly introverted
    - strongly extroverted
    - balanced between intuitive and big picture oriented and practical and detail oriented

- **Override and extension hooks**  
  `generate_persona` supports:
  - `overrides`: a dict of field names to forced values
  - `extra_traits`: a list of extra personality trait strings to append

Example:

```python
persona = generate_persona(
    seed=1234,
    overrides={
        "occupation": "blacksmith",
        "tech_savvy": "very low - no modern technology",
        "location": "Kingsbridge, Northern Kingdom",
        "education_level": "no formal schooling",
    },
    extra_traits=[
        "skilled with metalworking",
        "loyal to the local lord",
    ],
)
```

This allows game or scenario specific roles while still keeping the base personality driven by the seed.

---

## Use cases

Some ways to use Persona Engine:

- Sales practice  
  - Generate random buyer personas and feed them into an LLM powered roleplay bot  
  - Reuse the same persona later by saving its seed

- Training and coaching  
  - Create a fixed set of personas for repeated drills and performance tracking

- Games and NPCs  
  - Give each NPC a seed based personality that you can regenerate from its ID  
  - Map personality traits to simple behavior rules in your game world

- Testing and QA  
  - Use personas as deterministic fixtures for LLM based flows

---

## Roadmap

Planned feature ideas:

- Presets for different roles:
  - enterprise IT buyer
  - consumer gamer
  - student
- Era or time setting knob (modern, medieval, scifi) that biases roles and tech level
- Larger banks of occupations, interests, and traits loaded from data files
- Small HTTP API wrapper for easy integration in non Python stacks
- Versioning and snapshot tests for persona schemas and default presets

---

## Contributing

This is an early stage project. Suggestions, issues, and PRs are welcome, especially around:

- new presets and trait banks
- better MBTI to trait mapping
- additional fields that are broadly useful for LLM sims

Before submitting a PR:

1. Run tests:

   ```bash
   pytest
   ```

2. Add or update tests for any new behavior.

---

## License
Apache License 2.0. See `LICENSE` for details.
