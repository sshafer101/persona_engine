# persona_engine/libraries.py
from __future__ import annotations

import hashlib
import json
import os
import random
import re
from dataclasses import dataclass
from importlib import resources
from typing import Dict, List, Optional, Tuple, Union


@dataclass(frozen=True)
class ResolvedLibrary:
    key: str
    values: List[str]
    weights: Optional[List[float]]
    source: str
    raw_bytes: bytes


@dataclass(frozen=True)
class ResolvedDependentLibrary:
    child: str
    parent: str
    mapping: Dict[str, Tuple[List[str], Optional[List[float]]]]
    source: str
    raw_bytes: bytes


def _strip_bom(s: str) -> str:
    return s.lstrip("\ufeff")


def _remove_line_comments(s: str) -> str:
    out_lines: List[str] = []
    for line in s.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _remove_trailing_commas(s: str) -> str:
    return _TRAILING_COMMA_RE.sub(r"\1", s)


def _lenient_json_loads(raw: bytes) -> object:
    text = raw.decode("utf-8", errors="replace")
    text = _strip_bom(text)
    text = _remove_line_comments(text)
    text = _remove_trailing_commas(text)
    return json.loads(text)


def _normalize_list_payload(payload: Union[List[str], List[dict]]) -> Tuple[List[str], Optional[List[float]]]:
    if not isinstance(payload, list):
        raise ValueError("Library JSON must be a list")

    if not payload:
        return [], None

    if all(isinstance(x, str) for x in payload):
        values = [str(x).strip() for x in payload if str(x).strip()]
        return values, None

    if all(isinstance(x, dict) for x in payload):
        values: List[str] = []
        weights: List[float] = []
        for item in payload:
            if "value" not in item:
                continue
            v = str(item["value"]).strip()
            if not v:
                continue
            w = item.get("weight", 1)
            try:
                wf = float(w)
            except Exception:
                wf = 1.0
            if wf <= 0:
                continue
            values.append(v)
            weights.append(wf)
        return values, weights if values else None

    raise ValueError("Library JSON must be a list of strings or a list of objects with value and optional weight")


def _list_builtin_json_files(pack: str) -> Dict[str, bytes]:
    base = resources.files("persona_engine") / "data" / pack
    result: Dict[str, bytes] = {}
    try:
        for entry in base.iterdir():
            if entry.is_file() and entry.name.lower().endswith(".json"):
                result[entry.name] = entry.read_bytes()
    except FileNotFoundError:
        return {}
    return result


def _list_dir_json_files(lib_dir: str) -> Dict[str, bytes]:
    result: Dict[str, bytes] = {}
    if not lib_dir or not os.path.isdir(lib_dir):
        return result
    for name in os.listdir(lib_dir):
        if not name.lower().endswith(".json"):
            continue
        path = os.path.join(lib_dir, name)
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as f:
            result[name] = f.read()
    return result


def _stem(filename: str) -> str:
    if filename.lower().endswith(".json"):
        return filename[:-5]
    return filename


class LibraryStore:
    def __init__(
        self,
        pack: str = "default",
        lib_dir: Optional[str] = None,
        lib_files: Optional[Dict[str, str]] = None,
        lenient_json: bool = True,
    ):
        self.pack = pack
        self.lib_dir = lib_dir
        self.lib_files = lib_files or {}
        self.lenient_json = lenient_json

        self._raw_by_filename: Dict[str, bytes] = {}
        self._source_by_filename: Dict[str, str] = {}

        self._independent: Dict[str, str] = {}
        self._dependent: Dict[Tuple[str, str], str] = {}

        self._resolved_independent: Dict[str, ResolvedLibrary] = {}
        self._resolved_dependent: Dict[Tuple[str, str], ResolvedDependentLibrary] = {}

        self._discover()

    def _discover(self) -> None:
        builtin = _list_builtin_json_files(self.pack)
        for filename, raw in builtin.items():
            self._raw_by_filename[filename] = raw
            self._source_by_filename[filename] = f"persona_engine/data/{self.pack}/{filename}"

        if self.lib_dir:
            user_dir = _list_dir_json_files(self.lib_dir)
            for filename, raw in user_dir.items():
                self._raw_by_filename[filename] = raw
                self._source_by_filename[filename] = os.path.abspath(os.path.join(self.lib_dir, filename))

        for key, path in self.lib_files.items():
            if not os.path.isfile(path):
                raise FileNotFoundError(f"Library override file not found for {key}: {path}")
            filename = f"{key}.json"
            with open(path, "rb") as f:
                raw = f.read()
            self._raw_by_filename[filename] = raw
            self._source_by_filename[filename] = os.path.abspath(path)

        for filename in sorted(self._raw_by_filename.keys()):
            stem = _stem(filename)
            if "@" in stem:
                child, parent = stem.split("@", 1)
                child = child.strip()
                parent = parent.strip()
                if child and parent:
                    self._dependent[(child, parent)] = filename
            else:
                key = stem.strip()
                if key:
                    self._independent[key] = filename

    def keys(self) -> List[str]:
        k = set(self._independent.keys())
        for (child, _parent) in self._dependent.keys():
            k.add(child)
        return sorted(k)

    def dependent_pairs(self) -> List[Tuple[str, str]]:
        return sorted(self._dependent.keys())

    def has(self, key: str) -> bool:
        return key in self._independent

    def has_dep(self, child: str, parent: str) -> bool:
        return (child, parent) in self._dependent

    def _loads(self, raw: bytes) -> object:
        if self.lenient_json:
            return _lenient_json_loads(raw)
        return json.loads(raw.decode("utf-8"))

    def resolve(self, key: str) -> ResolvedLibrary:
        if key in self._resolved_independent:
            return self._resolved_independent[key]

        if key not in self._independent:
            raise KeyError(f"Unknown independent key: {key}. Available: {', '.join(sorted(self._independent.keys()))}")

        filename = self._independent[key]
        raw = self._raw_by_filename[filename]
        source = self._source_by_filename.get(filename, filename)

        payload = self._loads(raw)
        values, weights = _normalize_list_payload(payload)
        if not values:
            raise ValueError(f"Library {key} resolved to an empty list from {source}")

        lib = ResolvedLibrary(key=key, values=values, weights=weights, source=source, raw_bytes=raw)
        self._resolved_independent[key] = lib
        return lib

    def resolve_dep(self, child: str, parent: str) -> ResolvedDependentLibrary:
        pair = (child, parent)
        if pair in self._resolved_dependent:
            return self._resolved_dependent[pair]

        if pair not in self._dependent:
            raise KeyError(f"Unknown dependent pair: {child}@{parent}")

        filename = self._dependent[pair]
        raw = self._raw_by_filename[filename]
        source = self._source_by_filename.get(filename, filename)

        payload = self._loads(raw)
        if not isinstance(payload, dict):
            raise ValueError(f"Dependent library {child}@{parent} must be a JSON object (map) in {source}")

        mapping: Dict[str, Tuple[List[str], Optional[List[float]]]] = {}
        for k, v in payload.items():
            parent_val = str(k)
            vals, weights = _normalize_list_payload(v)
            if vals:
                mapping[parent_val] = (vals, weights)

        if not mapping:
            raise ValueError(f"Dependent library {child}@{parent} has no usable entries in {source}")

        lib = ResolvedDependentLibrary(child=child, parent=parent, mapping=mapping, source=source, raw_bytes=raw)
        self._resolved_dependent[pair] = lib
        return lib

    def pick(self, rng: random.Random, key: str) -> str:
        lib = self.resolve(key)
        if lib.weights:
            return rng.choices(lib.values, weights=lib.weights, k=1)[0]
        return rng.choice(lib.values)

    def pick_unique(self, rng: random.Random, key: str, k: int) -> List[str]:
        lib = self.resolve(key)
        if k <= 0:
            return []
        if not lib.weights:
            k = min(k, len(lib.values))
            return rng.sample(lib.values, k)

        chosen: List[str] = []
        attempts = 0
        max_attempts = max(50, k * 50)
        while len(chosen) < k and attempts < max_attempts:
            v = self.pick(rng, key)
            if v not in chosen:
                chosen.append(v)
            attempts += 1

        if len(chosen) < k:
            remaining = [v for v in lib.values if v not in chosen]
            rng.shuffle(remaining)
            chosen.extend(remaining[: max(0, k - len(chosen))])

        return chosen[:k]

    def pick_dep(
        self,
        rng: random.Random,
        child: str,
        parent: str,
        parent_value: str,
        fallback_child: Optional[str] = None,
    ) -> str:
        dep = self.resolve_dep(child, parent)
        if parent_value in dep.mapping:
            vals, weights = dep.mapping[parent_value]
            if weights:
                return rng.choices(vals, weights=weights, k=1)[0]
            return rng.choice(vals)

        if fallback_child and self.has(fallback_child):
            return self.pick(rng, fallback_child)

        all_vals: List[str] = []
        all_weights: Optional[List[float]] = None
        for vals, weights in dep.mapping.values():
            all_vals.extend(vals)
            if weights:
                if all_weights is None:
                    all_weights = []
                all_weights.extend(weights)

        if all_vals:
            if all_weights and len(all_weights) == len(all_vals):
                return rng.choices(all_vals, weights=all_weights, k=1)[0]
            return rng.choice(all_vals)

        return ""

    def library_hash(self) -> str:
        h = hashlib.sha256()
        h.update(self.pack.encode("utf-8"))
        h.update(b"\0")

        for key in sorted(self._independent.keys()):
            filename = self._independent[key]
            h.update(key.encode("utf-8"))
            h.update(b"\0")
            h.update(self._raw_by_filename[filename])
            h.update(b"\0")

        for (child, parent) in sorted(self._dependent.keys()):
            filename = self._dependent[(child, parent)]
            h.update(f"{child}@{parent}".encode("utf-8"))
            h.update(b"\0")
            h.update(self._raw_by_filename[filename])
            h.update(b"\0")

        return h.hexdigest()
