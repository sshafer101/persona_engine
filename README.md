# persona_engine

Deterministic persona generation for LLM prompts, test fixtures, and simulation backends.

`persona_engine` focuses on reusable persona data/modeling primitives.
Project-specific simulations and UIs should live in separate repos.

## Install

```bash
pip install -e .
```

## CLI

Show commands:

```bash
persona-engine -h
```

Generate a persona JSON:

```bash
persona-engine generate --seed 123
```

Generate a persona prompt:

```bash
persona-engine prompt --seed 123
```

Validate a pack or custom library overrides:

```bash
persona-engine validate-pack --pack default
persona-engine validate-pack --lib-dir ./my_libs
persona-engine validate-pack --lib occupations=./my_libs/occupations.json
```

## Library Data

Built-in data remains in `persona_engine/data/`.

You can layer custom data using:

- `--lib-dir` for a directory of JSON files
- `--lib key=path` for targeted overrides

## Python API

```python
from persona_engine import generate_persona, persona_to_prompt

p = generate_persona(seed=42)
print(p.to_dict())
print(persona_to_prompt(p))
```
