# persona_engine/cli.py
import argparse
import json
import sys
from typing import Dict, List, Optional

from .generator import generate_persona, persona_to_prompt
from .libraries import LibraryStore


def _parse_lib_kv(items: Optional[List[str]]) -> Optional[Dict[str, str]]:
    if not items:
        return None
    out: Dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --lib entry: {item}. Expected key=path")
        key, path = item.split("=", 1)
        key = key.strip()
        path = path.strip()
        if not key or not path:
            raise ValueError(f"Invalid --lib entry: {item}. Expected key=path")
        out[key] = path
    return out


def _add_pack_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--pack", type=str, default="default", help="Built-in library pack name")
    p.add_argument("--lib-dir", type=str, default=None, help="Directory of JSON libraries")
    p.add_argument(
        "--lib",
        action="append",
        default=None,
        help="Override a single library via key=path (repeatable)",
    )


def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--seed", type=int, default=None, help="Seed for deterministic generation")
    _add_pack_args(p)


def cmd_generate(args: argparse.Namespace) -> int:
    lib_files = _parse_lib_kv(args.lib)
    persona = generate_persona(
        seed=args.seed,
        pack=args.pack,
        lib_dir=args.lib_dir,
        lib_files=lib_files,
    )
    print(json.dumps(persona.to_dict(), indent=2, sort_keys=True))
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    lib_files = _parse_lib_kv(args.lib)
    persona = generate_persona(
        seed=args.seed,
        pack=args.pack,
        lib_dir=args.lib_dir,
        lib_files=lib_files,
    )
    print(persona_to_prompt(persona))
    return 0


def cmd_validate_pack(args: argparse.Namespace) -> int:
    lib_files = _parse_lib_kv(args.lib)
    libs = LibraryStore(
        pack=args.pack,
        lib_dir=args.lib_dir,
        lib_files=lib_files,
        lenient_json=True,
    )

    errors = libs.validate_all_relationships()
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1

    print("OK")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="persona-engine", description="Deterministic persona generator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="Generate persona JSON")
    _add_common_args(p_gen)
    p_gen.set_defaults(func=cmd_generate)

    p_prompt = sub.add_parser("prompt", help="Generate the LLM system prompt for a persona")
    _add_common_args(p_prompt)
    p_prompt.set_defaults(func=cmd_prompt)

    p_val = sub.add_parser("validate-pack", help="Validate relationship-aware libraries in a pack or directory")
    _add_pack_args(p_val)
    p_val.set_defaults(func=cmd_validate_pack)

    args = parser.parse_args(argv)

    try:
        return int(args.func(args))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
