# persona_engine/cli.py
import argparse
import json
import sys
from typing import Dict, List, Optional

from .env import load_dotenv_if_present
from .generator import REQUIRED_KEYS, generate_persona, persona_to_prompt
from .games import run_kmf_bracket, run_kmf_bracket_bench
from .libraries import LibraryStore
from .sim import run_blob_sim, run_blob_sim_bench, run_encounter_bench, run_encounter_bench_models


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


def _add_llm_args(p: argparse.ArgumentParser, *, default_temp: float) -> None:
    p.add_argument("--decider", type=str, default="heuristic", choices=["heuristic", "openai"])
    p.add_argument("--openai-model", type=str, default="gpt-4o-mini", help="Model name (decider=openai)")
    p.add_argument("--openai-temperature", type=float, default=default_temp, help="Temperature (decider=openai)")
    p.add_argument("--api-base-url", type=str, default=None, help="Optional OpenAI-compatible API base URL")
    p.add_argument("--api-key-env", type=str, default="OPENAI_API_KEY", help="Env var name holding the API key")


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

    errors = libs.validate_all(required_keys=sorted(REQUIRED_KEYS))
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1

    print("OK")
    return 0


def cmd_kmf_bracket(args: argparse.Namespace) -> int:
    lib_files = _parse_lib_kv(args.lib)
    out = run_kmf_bracket(
        candidates_n=args.candidates,
        judge_seed=args.judge_seed,
        seed=args.seed if args.seed is not None else 123,
        pack=args.pack,
        lib_dir=args.lib_dir,
        lib_files=lib_files,
        decider=args.decider,
        openai_model=args.openai_model,
        openai_temperature=args.openai_temperature,
        api_base_url=args.api_base_url,
        api_key_env=args.api_key_env,
    )
    print(json.dumps(out, indent=2, sort_keys=False, ensure_ascii=False))
    return 0


def cmd_blob_sim(args: argparse.Namespace) -> int:
    lib_files = _parse_lib_kv(args.lib)
    out = run_blob_sim(
        agents=args.agents,
        steps=args.steps,
        seed=args.seed if args.seed is not None else 123,
        pack=args.pack,
        lib_dir=args.lib_dir,
        lib_files=lib_files,
        interaction_radius=args.interaction_radius,
        speed=args.speed,
        decider=args.decider,
        openai_model=args.openai_model,
        openai_temperature=args.openai_temperature,
        api_base_url=args.api_base_url,
        api_key_env=args.api_key_env,
        max_messages=args.max_messages,
        llm_concurrency=args.llm_concurrency,
        pair_cache_size=args.pair_cache_size,
        max_interactions_per_tick=args.max_interactions_per_tick,
        memory_size=args.memory_size,
        max_pending_requests=args.max_pending_requests,
    )
    print(json.dumps(out, indent=2, sort_keys=False, ensure_ascii=False))
    return 0


def cmd_blob_sim_bench(args: argparse.Namespace) -> int:
    lib_files = _parse_lib_kv(args.lib)
    models = [m.strip() for m in (args.models or "").split(",") if m.strip()]
    out = run_blob_sim_bench(
        models=models,
        runs=args.runs,
        base_seed=args.base_seed,
        agents=args.agents,
        steps=args.steps,
        pack=args.pack,
        lib_dir=args.lib_dir,
        lib_files=lib_files,
        interaction_radius=args.interaction_radius,
        speed=args.speed,
        decider=args.decider,
        openai_temperature=args.openai_temperature,
        api_base_url=args.api_base_url,
        api_key_env=args.api_key_env,
    )
    print(json.dumps(out, indent=2, sort_keys=False, ensure_ascii=False))
    return 0


def cmd_kmf_bracket_bench(args: argparse.Namespace) -> int:
    lib_files = _parse_lib_kv(args.lib)
    models = [m.strip() for m in (args.models or "").split(",") if m.strip()]
    out = run_kmf_bracket_bench(
        models=models,
        runs=args.runs,
        base_seed=args.base_seed,
        judge_seed=args.judge_seed,
        candidates_n=args.candidates,
        pack=args.pack,
        lib_dir=args.lib_dir,
        lib_files=lib_files,
        decider=args.decider,
        openai_temperature=args.openai_temperature,
        api_base_url=args.api_base_url,
        api_key_env=args.api_key_env,
    )
    print(json.dumps(out, indent=2, sort_keys=False, ensure_ascii=False))
    return 0


def cmd_encounter_bench(args: argparse.Namespace) -> int:
    lib_files = _parse_lib_kv(args.lib)
    out = run_encounter_bench(
        seed=args.seed if args.seed is not None else 123,
        agents=args.agents,
        encounters=args.encounters,
        pack=args.pack,
        lib_dir=args.lib_dir,
        lib_files=lib_files,
        decider=args.decider,
        openai_model=args.openai_model,
        openai_temperature=args.openai_temperature,
        api_base_url=args.api_base_url,
        api_key_env=args.api_key_env,
    )
    print(json.dumps(out, indent=2, sort_keys=False, ensure_ascii=False))
    return 0


def cmd_encounter_bench_models(args: argparse.Namespace) -> int:
    lib_files = _parse_lib_kv(args.lib)
    models = [m.strip() for m in (args.models or "").split(",") if m.strip()]
    out = run_encounter_bench_models(
        models=models,
        runs=args.runs,
        base_seed=args.base_seed,
        agents=args.agents,
        encounters=args.encounters,
        pack=args.pack,
        lib_dir=args.lib_dir,
        lib_files=lib_files,
        decider=args.decider,
        openai_temperature=args.openai_temperature,
        api_base_url=args.api_base_url,
        api_key_env=args.api_key_env,
    )
    print(json.dumps(out, indent=2, sort_keys=False, ensure_ascii=False))
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    try:
        import uvicorn  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "UI deps not installed. Install with: pip install -e '.[ui]' "
            "(or: pip install fastapi uvicorn[standard])."
        ) from e

    uvicorn.run(
        "persona_engine.ui.server:app",
        host=args.host,
        port=int(args.port),
        reload=bool(args.reload),
        log_level="info",
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    load_dotenv_if_present(".env")

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

    p_kmf = sub.add_parser(
        "kmf-bracket",
        help="Run an AI-only bracketed 'marry / hookup / eliminate' simulation (heuristic by default)",
    )
    _add_common_args(p_kmf)
    p_kmf.add_argument("--candidates", type=int, default=24, help="Number of candidates (>= 3)")
    p_kmf.add_argument("--judge-seed", type=int, default=2024, help="Seed for the judge persona")
    _add_llm_args(p_kmf, default_temp=0.2)
    p_kmf.set_defaults(func=cmd_kmf_bracket)

    p_blob = sub.add_parser("blob-sim", help="Run the headless bouncing-blobs persona interaction sim")
    _add_common_args(p_blob)
    p_blob.add_argument("--agents", type=int, default=18, help="Number of blobs/personas")
    p_blob.add_argument("--steps", type=int, default=600, help="Max steps to run")
    p_blob.add_argument("--interaction-radius", type=float, default=0.06, help="Distance threshold for interactions")
    p_blob.add_argument("--speed", type=float, default=0.02, help="Base movement speed")
    p_blob.add_argument("--max-messages", type=int, default=20, help="Max conversation lines per interaction")
    p_blob.add_argument("--llm-concurrency", type=int, default=1, help="Parallel model decisions (decider=openai)")
    p_blob.add_argument("--pair-cache-size", type=int, default=2000, help="Cached pair decisions (0 disables)")
    p_blob.add_argument("--max-interactions-per-tick", type=int, default=1, help="Max disjoint interactions processed each tick")
    p_blob.add_argument("--memory-size", type=int, default=8, help="Recent interactions each blob remembers")
    p_blob.add_argument("--max-pending-requests", type=int, default=8, help="Max queued in-flight LLM interaction requests")
    _add_llm_args(p_blob, default_temp=0.3)
    p_blob.set_defaults(func=cmd_blob_sim)

    p_bench = sub.add_parser("blob-sim-bench", help="Benchmark blob-sim across models (compare remove_rate, counts)")
    _add_common_args(p_bench)
    p_bench.add_argument("--agents", type=int, default=18, help="Number of blobs/personas")
    p_bench.add_argument("--steps", type=int, default=600, help="Max steps per run")
    p_bench.add_argument("--interaction-radius", type=float, default=0.06, help="Distance threshold for interactions")
    p_bench.add_argument("--speed", type=float, default=0.02, help="Base movement speed")
    p_bench.add_argument("--decider", type=str, default="openai", choices=["heuristic", "openai"])
    p_bench.add_argument("--models", type=str, required=True, help="Comma-separated model names (or labels for decider=heuristic)")
    p_bench.add_argument("--runs", type=int, default=10, help="Runs per model")
    p_bench.add_argument("--base-seed", type=int, default=1000, help="Base seed (run i uses base_seed+i)")
    p_bench.add_argument("--openai-temperature", type=float, default=0.3, help="Temperature (decider=openai)")
    p_bench.add_argument("--api-base-url", type=str, default=None, help="Optional OpenAI-compatible API base URL")
    p_bench.add_argument("--api-key-env", type=str, default="OPENAI_API_KEY", help="Env var name holding the API key")
    p_bench.set_defaults(func=cmd_blob_sim_bench)

    p_kmf_bench = sub.add_parser("kmf-bracket-bench", help="Benchmark kmf-bracket across models (marry/hookup/eliminate rates)")
    _add_common_args(p_kmf_bench)
    p_kmf_bench.add_argument("--decider", type=str, default="openai", choices=["heuristic", "openai"])
    p_kmf_bench.add_argument("--models", type=str, required=True, help="Comma-separated model names (or labels for decider=heuristic)")
    p_kmf_bench.add_argument("--runs", type=int, default=10, help="Runs per model")
    p_kmf_bench.add_argument("--base-seed", type=int, default=1000, help="Base seed (run i uses base_seed+i)")
    p_kmf_bench.add_argument("--judge-seed", type=int, default=2024, help="Seed for the judge persona (constant across runs)")
    p_kmf_bench.add_argument("--candidates", type=int, default=24, help="Number of candidates (>= 3)")
    p_kmf_bench.add_argument("--openai-temperature", type=float, default=0.2, help="Temperature (decider=openai)")
    p_kmf_bench.add_argument("--api-base-url", type=str, default=None, help="Optional OpenAI-compatible API base URL")
    p_kmf_bench.add_argument("--api-key-env", type=str, default="OPENAI_API_KEY", help="Env var name holding the API key")
    p_kmf_bench.set_defaults(func=cmd_kmf_bracket_bench)

    p_enc = sub.add_parser("encounter-bench", help="Fixed-dataset pair encounters (good for comparing model tendencies)")
    _add_common_args(p_enc)
    p_enc.add_argument("--agents", type=int, default=30, help="Roster size")
    p_enc.add_argument("--encounters", type=int, default=200, help="Number of random pair encounters")
    _add_llm_args(p_enc, default_temp=0.3)
    p_enc.set_defaults(func=cmd_encounter_bench)

    p_encm = sub.add_parser("encounter-bench-models", help="Run encounter-bench across models (same seeds/datasets) and summarize rates")
    _add_common_args(p_encm)
    p_encm.add_argument("--models", type=str, required=True, help="Comma-separated model names")
    p_encm.add_argument("--runs", type=int, default=5, help="Runs per model (seed i uses base_seed+i)")
    p_encm.add_argument("--base-seed", type=int, default=1000, help="Base seed (run i uses base_seed+i)")
    p_encm.add_argument("--agents", type=int, default=30, help="Roster size")
    p_encm.add_argument("--encounters", type=int, default=200, help="Encounters per run")
    p_encm.add_argument("--decider", type=str, default="openai", choices=["heuristic", "openai"])
    p_encm.add_argument("--openai-temperature", type=float, default=0.3, help="Temperature (decider=openai)")
    p_encm.add_argument("--api-base-url", type=str, default=None, help="Optional OpenAI-compatible API base URL")
    p_encm.add_argument("--api-key-env", type=str, default="OPENAI_API_KEY", help="Env var name holding the API key")
    p_encm.set_defaults(func=cmd_encounter_bench_models)

    p_ui = sub.add_parser("ui", help="Run the local blob-sim web UI (watch interactions + tweak flags)")
    p_ui.add_argument("--host", type=str, default="127.0.0.1")
    p_ui.add_argument("--port", type=int, default=8000)
    p_ui.add_argument("--reload", action="store_true", help="Auto-reload on code changes")
    p_ui.set_defaults(func=cmd_ui)

    args = parser.parse_args(argv)

    try:
        return int(args.func(args))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
