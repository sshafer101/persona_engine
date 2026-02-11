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

## Demo

Generate a few varied personas (JSON summary):

```bash
python scripts/demo.py
```

Generate a single persona prompt:

```bash
persona-engine prompt --seed 42
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
persona-engine kmf-bracket [--seed N] [--judge-seed N] [--candidates N] [--decider heuristic|openai]
persona-engine blob-sim [--seed N] [--agents N] [--steps N] [--decider heuristic|openai]
persona-engine blob-sim-bench --models a,b,c [--runs N] [--base-seed N] [--decider openai|heuristic]
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

## Example: AI-only bracket game

Run a bracketed "marry / hookup / eliminate" simulation with no human input (deterministic heuristic decider by default):

```bash
persona-engine kmf-bracket --seed 1 --judge-seed 2 --candidates 24
```

To let an OpenAI model make the decisions instead of the heuristic:

```bash
pip install "persona-engine[llm]"
export OPENAI_API_KEY="..."
persona-engine kmf-bracket --decider openai --openai-model gpt-4o-mini
```

## Example: Bouncing blob sim + model comparison

Run a headless "blobs bounce and chat" simulation (outputs an event log + summary stats):

```bash
persona-engine blob-sim --seed 1 --agents 18 --steps 600
```

Benchmark multiple models by how often they choose `remove`:

```bash
pip install "persona-engine[llm]"
export OPENAI_API_KEY="..."
persona-engine blob-sim-bench --decider openai --models gpt-4o-mini,gpt-4.1-mini --runs 10 --base-seed 1000
```

Benchmark multiple models on "marry / promiscuous / eliminate" tendencies in the bracket game:

```bash
pip install "persona-engine[llm]"
export OPENAI_API_KEY="..."
persona-engine kmf-bracket-bench --decider openai --models gpt-4o-mini,gpt-4.1-mini --runs 10 --base-seed 1000 --judge-seed 2024 --candidates 24
```

For a cleaner apples-to-apples “tendency” comparison (no physics divergence), use fixed pair encounters:

```bash
pip install "persona-engine[llm]"
export OPENAI_API_KEY="..."
persona-engine encounter-bench-models --models gpt-4o-mini,gpt-4.1-mini --runs 10 --base-seed 1000 --agents 30 --encounters 200
```

If you want to benchmark a provider that offers an OpenAI-compatible API, pass `--api-base-url` and `--api-key-env`:

```bash
export XAI_API_KEY="..."
persona-engine encounter-bench-models \
  --api-base-url https://api.x.ai/v1 \
  --api-key-env XAI_API_KEY \
  --models <xai-model-name-1>,<xai-model-name-2> \
  --runs 10 --base-seed 1000 --agents 30 --encounters 200
```

## Web UI (watch the chaos)

Run a local web UI to watch the bouncing-blob sim and tweak flags (seed, agent count, decider/model, speed, radius):

```bash
pip install -e ".[ui]"
persona-engine ui
```

Quick restart helper (kills old UI process on the port and starts a new one):

```bash
scripts/restart_ui.sh --port 8000 --reload
```

Performance knobs:
- `max_interactions_per_tick`: process multiple collisions per tick
- `llm_concurrency`: parallel model decisions per tick (`decider=openai`)
- `max_pending_requests`: cap queued in-flight LLM interaction calls (helps UI smoothness)
- `pair_cache_size`: cache prior pair decisions to avoid repeated model calls
- `memory_size`: number of recent interactions each blob remembers

## Development install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

Apache License 2.0. See `LICENSE` for details.
