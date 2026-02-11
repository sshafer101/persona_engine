from __future__ import annotations

import os
import pathlib


def _strip_quotes(s: str) -> str:
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        return s[1:-1]
    return s


def load_dotenv_if_present(dotenv_path: str = ".env") -> None:
    """
    Lightweight .env loader (no external dependency).
    Only sets vars that are not already in the process environment.
    """
    p = pathlib.Path(dotenv_path)
    if not p.exists() or not p.is_file():
        return

    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception:
        return

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = _strip_quotes(val.strip())
        if not key or key in os.environ:
            continue
        os.environ[key] = val

