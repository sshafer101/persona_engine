# Persona Engine

Deterministic persona generator for LLMs, games, simulations, and training.

Give it a seed, get a rich fake person plus a ready to use system prompt.
Same seed plus same libraries equals same persona.

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

Python usage:

```python
from persona_engine import generate_persona, persona_to_prompt

persona = generate_persona(seed=42)
print(persona.to_dict())

system_prompt = persona_to_prompt(persona)
print(system_prompt)
```

## Key idea

Persona Engine is library driven.

Most persona fields come from JSON libraries such as:

- occupations
- interests
- cities
- countries
- political_leanings
- religions

You can use the built in default pack, or point the generator at your own library directory.

## Library format

A library file is JSON.

Simple list:

```json
["A", "B", "C"]
```

Weighted list:

```json
[
  {"value": "A", "weight": 3},
  {"value": "B", "weight": 1}
]
```

Important:
- JSON must be valid JSON. No trailing commas.
- The default loader is lenient and will ignore full line comments that start with `//`.

## Using your own libraries

Use `--lib-dir` to load JSON files from a directory.

```bash
persona-engine prompt --seed 2 --lib-dir ./my_libs
```

Rules:
- Each `*.json` file in the directory becomes a library key.
- The filename (without `.json`) is the key.
  Example: `occupations.json` becomes `occupations`.
- If a file matches a known core key, it will drive that field.
- Extra files are sampled and included under `extras` in the persona JSON.
  They can also be included in the prompt output.

You can also override a single library by key:

```bash
persona-engine prompt --seed 2 --lib occupations=./my_libs/occupations.json
```

## CLI reference

```bash
persona-engine generate [--seed N] [--pack NAME] [--lib-dir DIR] [--lib key=path]
persona-engine prompt   [--seed N] [--pack NAME] [--lib-dir DIR] [--lib key=path]
```

Notes:
- `--pack` selects the built in pack (default is `default`).
- `--lib-dir` layers on top of the built in pack.
- `--lib key=path` is a per key override.

## Determinism and versioning

Determinism holds when these are the same:
- seed
- generator version
- the set of library files used

The persona JSON includes:
- `seed`
- `library_hash`

If you change any library file, `library_hash` changes.

## Roadmap

- Larger default libraries (names, jobs, interests, traits)
- Relationship aware libraries (example: city depends on country)
- Optional schema and validation helpers for packs
- More examples and demos

## Development install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

Apache License 2.0. See `LICENSE` for details.
