#!/usr/bin/env python3
import json
from persona_engine import generate_persona


def main() -> int:
    seeds = [7, 42, 99, 1234, 2024]
    for seed in seeds:
        p = generate_persona(seed=seed).to_dict()
        summary = {
            "seed": p["seed"],
            "name": p["name"],
            "age": p["age"],
            "gender": p["gender"],
            "location": p["location"],
            "occupation": p["occupation"],
            "interests": p["interests"],
        }
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
