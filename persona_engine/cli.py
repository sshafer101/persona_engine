# persona_engine/cli.py

from __future__ import annotations

import argparse
import json
import secrets
import sys
from typing import Any

from persona_engine import generate_persona, persona_to_prompt


def _pick_seed(seed: int | None) -> int:
    if seed is not None:
        return int(seed)
    return secrets.randbelow(2**32)


def cmd_generate(args: argparse.Namespace) -> int:
    seed = _pick_seed(args.seed)
    persona = generate_persona(seed=seed)
    data: Any = persona.to_dict()

    if args.include_seed and isinstance(data, dict):
        data.setdefault("seed", seed)

    print(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    seed = _pick_seed(args.seed)
    persona = generate_persona(seed=seed)
    print(persona_to_prompt(persona))
    if args.print_seed:
        print(f"\n(seed: {seed})", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="persona-engine",
        description="Deterministic persona generator. Same seed, same persona.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="Print persona JSON")
    p_gen.add_argument("--seed", type=int, default=None, help="Seed for deterministic output")
    p_gen.add_argument(
        "--include-seed",
        action="store_true",
        help="Include seed field in the emitted JSON",
    )
    p_gen.set_defaults(func=cmd_generate)

    p_prompt = sub.add_parser("prompt", help="Print LLM system prompt for the persona")
    p_prompt.add_argument("--seed", type=int, default=None, help="Seed for deterministic output")
    p_prompt.add_argument(
        "--print-seed",
        action="store_true",
        help="Print seed to stderr (useful when seed is omitted)",
    )
    p_prompt.set_defaults(func=cmd_prompt)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

