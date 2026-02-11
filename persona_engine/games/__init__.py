"""
Small simulation/game helpers built on top of persona_engine.

The core package stays dependency-free. Anything that needs an external LLM
client should be optional and imported lazily.
"""

from .kmf_bracket import run_kmf_bracket
from .kmf_bench import run_kmf_bracket_bench

__all__ = ["run_kmf_bracket", "run_kmf_bracket_bench"]
