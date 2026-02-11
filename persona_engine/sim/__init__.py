"""
Toy simulations built on top of persona_engine.

These are intentionally dependency-free so they can run in any environment and
produce deterministic logs that you can later visualize (web, pygame, etc.).
"""

from .blob_sim import run_blob_sim
from .blob_bench import run_blob_sim_bench
from .encounter_bench import run_encounter_bench, run_encounter_bench_models

__all__ = ["run_blob_sim", "run_blob_sim_bench", "run_encounter_bench", "run_encounter_bench_models"]
