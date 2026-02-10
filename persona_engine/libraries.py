# persona_engine/libraries.py
from __future__ import annotations

import hashlib
import json
import os
import random
import re
from dataclasses import dataclass
from importlib import resources
from typing import Any, Dict, List, Optional, Tuple, Union


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


@dataclass(frozen=True)
class ResolvedChainedLibrary:
    chain: Tuple[str, ...]
    data: Dict[str, Any]
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


def _validate_list_payload(payload: Any, label: str) -> List[str]:
    errs: List[str] = []
    if not isinstance(payload, list):
        errs.append(f"{label}: expected list, got {type(payload).__name__}")
        return errs

    if not payload:
        errs.append(f"{label}: empty list")
        return errs

    if all(isinstance(x, str) for x in payload):
        if not any(str(x).strip() for x in payload):
            errs.append(f"{label}: list contains only empty strings")
        return errs

    if all(isinstance(x, dict) for x in payload):
        saw_value = False
        for idx, item in enumerate(payload):
            if "value" not in item:
                errs.append(f"{label}: item {idx} missing 'value'")
                continue
            v = str(item.get("value", "")).strip()
            if not v:
                errs.append(f"{label}: item {idx} has empty 'value'")
                continue
            saw_value = True
            if "weight" in item:
                try:
                    wf = float(item["weight"])
                except Exception:
                    errs.append(f"{label}: item {idx} has invalid weight (not a number)")
                    continue
                if wf <= 0:
                    errs.append(f"{label}: item {idx} has non-positive weight")
        if not saw_value:
            errs.append(f"{label}: no usable values found")
        return errs

    errs.append(f"{label}: mixed or unsupported list element types")
    return errs


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


def _parse_chain_from_stem(stem: str) -> Optional[Tuple[str, ...]]:
    if "@" not in stem:
        return None
    parts = tuple(p.strip() for p in stem.split("@") if p.strip())
    if len(parts) < 2:
        return None
    return parts


def _validate_chain_payload(chain: Tuple[str, ...], payload: Any) -> List[str]:
    errs: List[str] = []
    label = "@".join(chain)

    if not isinstance(payload, dict):
        errs.append(f"{label}: expected top-level object (dict), got {type(payload).__name__}")
        return errs

    leaf_depth = len(chain) - 1

    def walk(node: Any, depth: int, path: List[str]) -> None:
        at = ".".join(path) if path else "<root>"
        if depth < leaf_depth:
            if not isinstance(node, dict):
                errs.append(f"{label}: expected object at {at}, got {type(node).__name__}")
                return
            if not node:
                errs.append(f"{label}: empty object at {at}")
                return
            for k, v in node.items():
                if not isinstance(k, str) or not k.strip():
                    errs.append(f"{label}: non-string key at {at}")
                    continue
                walk(v, depth + 1, path + [k])
            return

        if not isinstance(node, list):
            errs.append(f"{label}: expected list at {at}, got {type(node).__name__}")
            return

        try:
            vals, _weights = _normalize_list_payload(node)
        except Exception as e:
            errs.append(f"{label}: invalid list payload at {at}: {e}")
            return

        if not vals:
            errs.append(f"{label}: empty list at {at}")

    walk(payload, 0, [])
    return errs


def _pick_from_leaf_list(rng: random.Random, node: Any) -> str:
    vals, weights = _normalize_list_payload(node)
    if not vals:
        return ""
    if weights:
        return rng.choices(vals, weights=weights, k=1)[0]
    return rng.choice(vals)


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
        self._chained: Dict[Tuple[str, ...], str] = {}

        self._resolved_independent: Dict[str, ResolvedLibrary] = {}
        self._resolved_dependent: Dict[Tuple[str, str], ResolvedDependentLibrary] = {}
        self._resolved_chained: Dict[Tuple[str, ...], ResolvedChainedLibrary] = {}

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
            stem = _stem(filename).strip()
            if not stem:
                continue

            chain = _parse_chain_from_stem(stem)
            if chain:
                self._chained[chain] = filename
                if len(chain) == 2:
                    child, parent = chain[0], chain[1]
                    self._dependent[(child, parent)] = filename
                continue

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

    def chained_chains(self) -> List[Tuple[str, ...]]:
        return sorted(self._chained.keys(), key=lambda c: (len(c), c))

    def has(self, key: str) -> bool:
        return key in self._independent

    def has_dep(self, child: str, parent: str) -> bool:
        return (child, parent) in self._dependent

    def has_chain(self, chain: Tuple[str, ...]) -> bool:
        return chain in self._chained

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

    def resolve_chain(self, chain: Tuple[str, ...]) -> ResolvedChainedLibrary:
        if chain in self._resolved_chained:
            return self._resolved_chained[chain]

        if chain not in self._chained:
            raise KeyError(f"Unknown chained library: {'@'.join(chain)}")

        filename = self._chained[chain]
        raw = self._raw_by_filename[filename]
        source = self._source_by_filename.get(filename, filename)

        payload = self._loads(raw)
        errs = _validate_chain_payload(chain, payload)
        if errs:
            raise ValueError(f"Invalid chained library {'@'.join(chain)} in {source}: " + "; ".join(errs))

        lib = ResolvedChainedLibrary(chain=chain, data=payload, source=source, raw_bytes=raw)
        self._resolved_chained[chain] = lib
        return lib

    def validate_all_relationships(self) -> List[str]:
        errors: List[str] = []
        for chain in self.chained_chains():
            filename = self._chained[chain]
            raw = self._raw_by_filename[filename]
            source = self._source_by_filename.get(filename, filename)
            try:
                payload = self._loads(raw)
            except Exception as e:
                errors.append(f"{'@'.join(chain)}: JSON parse error in {source}: {e}")
                continue

            errs = _validate_chain_payload(chain, payload)
            for err in errs:
                errors.append(f"{err} (source={source})")
        return errors

    def validate_all(self, required_keys: Optional[List[str]] = None) -> List[str]:
        errors: List[str] = []

        for key, filename in self._independent.items():
            raw = self._raw_by_filename[filename]
            source = self._source_by_filename.get(filename, filename)
            try:
                payload = self._loads(raw)
            except Exception as e:
                errors.append(f"{key}: JSON parse error in {source}: {e}")
                continue
            for err in _validate_list_payload(payload, f"{key}"):
                errors.append(f"{err} (source={source})")

        for (child, parent), filename in self._dependent.items():
            raw = self._raw_by_filename[filename]
            source = self._source_by_filename.get(filename, filename)
            try:
                payload = self._loads(raw)
            except Exception as e:
                errors.append(f"{child}@{parent}: JSON parse error in {source}: {e}")
                continue

            if not isinstance(payload, dict):
                errors.append(f"{child}@{parent}: expected top-level object (dict), got {type(payload).__name__} (source={source})")
                continue

            if not payload:
                errors.append(f"{child}@{parent}: empty object (source={source})")
                continue

            for parent_val, child_list in payload.items():
                label = f"{child}@{parent}:{parent_val}"
                for err in _validate_list_payload(child_list, label):
                    errors.append(f"{err} (source={source})")

        for chain in self.chained_chains():
            filename = self._chained[chain]
            raw = self._raw_by_filename[filename]
            source = self._source_by_filename.get(filename, filename)
            try:
                payload = self._loads(raw)
            except Exception as e:
                errors.append(f"{'@'.join(chain)}: JSON parse error in {source}: {e}")
                continue

            errs = _validate_chain_payload(chain, payload)
            for err in errs:
                errors.append(f"{err} (source={source})")

        if required_keys:
            for key in required_keys:
                if not self.has(key):
                    errors.append(f"missing required library: {key}")

        return errors

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

    def pick_chain(self, rng: random.Random, chain: Tuple[str, ...]) -> Dict[str, str]:
        lib = self.resolve_chain(chain)
        data: Any = lib.data

        chosen: Dict[str, str] = {}
        parentmost_key = chain[-1]

        parent_val = rng.choice(list(data.keys()))
        chosen[parentmost_key] = parent_val
        node: Any = data[parent_val]

        for idx in range(len(chain) - 2, -1, -1):
            key = chain[idx]

            if isinstance(node, dict):
                if not node:
                    raise ValueError(f"{'@'.join(chain)}: empty object encountered while selecting {key}")
                next_k = rng.choice(list(node.keys()))
                chosen[key] = str(next_k)
                node = node[next_k]
                continue

            if isinstance(node, list):
                chosen[key] = _pick_from_leaf_list(rng, node)
                node = None
                continue

            raise ValueError(f"{'@'.join(chain)}: unexpected node type {type(node).__name__} while selecting {key}")

        return chosen

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

        for chain in sorted([c for c in self._chained.keys() if len(c) > 2], key=lambda c: (len(c), c)):
            filename = self._chained[chain]
            h.update("@".join(chain).encode("utf-8"))
            h.update(b"\0")
            h.update(self._raw_by_filename[filename])
            h.update(b"\0")

        return h.hexdigest()
