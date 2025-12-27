# Persona Engine

Deterministic persona generator for LLMs, games, simulations, and training.

Give it a seed, get a rich fake person plus a ready to use system prompt. Same seed, same persona.

> Status: early MVP. API may change.

## Install

```bash
pip install persona-engine
```

## 60 second quickstart

Generate persona JSON:

```bash
persona-engine generate --seed 42
```

Generate an LLM system prompt:

```bash
persona-engine prompt --seed 42
```

No seed picks a random one (and prints the chosen seed in the JSON):

```bash
persona-engine generate --include-seed
```

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

## Python usage

```python
from persona_engine import generate_persona, persona_to_prompt

persona = generate_persona(seed=42)
print(persona.to_dict())

system_prompt = persona_to_prompt(persona)
print(system_prompt)
```

## CLI usage

Generate persona JSON:

```bash
persona-engine generate --seed 42
```

Generate an LLM system prompt:

```bash
persona-engine prompt --seed 42
```

If you omit `--seed`, a random persona is generated. Use `--include-seed` to print the chosen seed inside the JSON output.

## Design notes

- Deterministic by seed  
  `generate_persona(seed=42)` will always return the same persona as long as the generator code and version are unchanged.

- MBTI driven traits  
  The generator first rolls MBTI axis scores (I/E, N/S, T/F, P/J), then:
  - derives the 4 letter MBTI type
  - converts scores into human readable traits

- Override and extension hooks  
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

## Use cases

- LLM roleplay
  - Use `persona_to_prompt(persona)` as your system message
  - Keep the seed in logs so you can reproduce the same persona later

- Training and coaching
  - Create a fixed set of personas for repeated drills and performance tracking

- Games and NPCs
  - Store a seed per NPC and regenerate the full profile on load

- Testing and QA
  - Use personas as deterministic fixtures for LLM based flows

## Roadmap

- Presets for different roles (enterprise IT buyer, consumer gamer, student)
- Larger banks of occupations, interests, and traits loaded from data files
- Versioning and snapshot tests for persona schemas and default presets

## Development install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Contributing

Suggestions, issues, and PRs are welcome, especially around:
- new presets and trait banks
- better MBTI to trait mapping
- additional fields that are broadly useful for LLM sims

Before submitting a PR:

1. Run tests:

   ```bash
   pytest
   ```

2. Add or update tests for any new behavior.

## License

Apache License 2.0. See `LICENSE` for details.
