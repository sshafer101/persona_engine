import argparse
import json

from persona_engine import generate_persona, persona_to_prompt


def cmd_generate(args: argparse.Namespace) -> None:
    persona = generate_persona(seed=args.seed)
    print(json.dumps(persona.to_dict(), indent=2))


def cmd_prompt(args: argparse.Namespace) -> None:
    persona = generate_persona(seed=args.seed)
    prompt = persona_to_prompt(persona)
    print(prompt)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persona engine MVP - generate random personas."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_gen = subparsers.add_parser("generate", help="Generate persona JSON")
    p_gen.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional seed for repeatable persona",
    )
    p_gen.set_defaults(func=cmd_generate)

    p_prompt = subparsers.add_parser("prompt", help="Generate LLM system prompt")
    p_prompt.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional seed for repeatable persona",
    )
    p_prompt.set_defaults(func=cmd_prompt)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
