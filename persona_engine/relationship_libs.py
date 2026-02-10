from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import random


@dataclass(frozen=True)
class RelatedLibrary:
    """
    Represents a relationship-aware library parsed from a filename like:
      - cities@countries.json
      - streets@cities@countries.json

    chain parts are ordered as they appear in the filename:
      ("cities", "countries")
      ("streets", "cities", "countries")
    """
    chain: Tuple[str, ...]
    data: Dict[str, Any]


class RelationshipError(ValueError):
    pass


def parse_chain_from_stem(stem: str) -> Optional[Tuple[str, ...]]:
    """
    Given a filename stem (no .json), returns tuple of parts if relationship-aware, else None.
    Example:
      "cities@countries" -> ("cities", "countries")
      "streets@cities@countries" -> ("streets","cities","countries")
      "interests" -> None
    """
    if "@" not in stem:
        return None
    parts = tuple(p.strip() for p in stem.split("@") if p.strip())
    if len(parts) < 2:
        return None
    return parts


def _is_str_list(x: Any) -> bool:
    return isinstance(x, list) and all(isinstance(i, str) for i in x)


def validate_related_payload(chain: Sequence[str], payload: Any) -> List[str]:
    """
    Structural validation for relationship-aware payloads.

    For chain length N:
      payload must be dict at levels 0..N-2, and list[str] at leaves.

    Returns list of error strings (empty means OK).
    """
    errs: List[str] = []
    if not isinstance(payload, dict):
        errs.append(f"{'@'.join(chain)}: expected top-level object (dict), got {type(payload).__name__}")
        return errs

    def walk(level: int, node: Any, path: List[str]) -> None:
        # level corresponds to which part we are selecting from the right side inward
        # but structurally we just need dicts until last hop, then list[str].
        remaining_hops = len(chain) - 1 - level
        if remaining_hops > 0:
            if not isinstance(node, dict):
                errs.append(f"{'@'.join(chain)}: expected object at {'.'.join(path) or '<root>'}, got {type(node).__name__}")
                return
            if not node:
                errs.append(f"{'@'.join(chain)}: empty object at {'.'.join(path) or '<root>'}")
                return
            for k, v in node.items():
                if not isinstance(k, str):
                    errs.append(f"{'@'.join(chain)}: non-string key at {'.'.join(path) or '<root>'}")
                    continue
                walk(level + 1, v, path + [k])
        else:
            if not _is_str_list(node):
                errs.append(f"{'@'.join(chain)}: expected list[str] at {'.'.join(path) or '<root>'}, got {type(node).__name__}")
                return
            if len(node) == 0:
                errs.append(f"{'@'.join(chain)}: empty list at {'.'.join(path) or '<root>'}")

    walk(0, payload, [])
    return errs


def resolve_related_values(related: RelatedLibrary, rng: random.Random) -> Dict[str, str]:
    """
    Resolve a coherent set of values across the chain.

    For ("cities","countries"):
      chooses a country (from payload keys), then a city from that country.
      returns {"countries": "...", "cities": "..."}

    For ("streets","cities","countries"):
      chooses country, then city under that country, then street under that city.
      returns {"countries": "...", "cities": "...", "streets": "..."}
    """
    chain = related.chain
    data = related.data

    # Validate quickly to avoid weird KeyErrors later
    errs = validate_related_payload(chain, data)
    if errs:
        raise RelationshipError("; ".join(errs))

    # Walk from parentmost down to childmost.
    # Payload is keyed by parentmost at top-level.
    parentmost_key = chain[-1]
    chosen: Dict[str, str] = {}

    country = rng.choice(list(data.keys()))
    chosen[parentmost_key] = country

    node: Any = data[country]

    # For each intermediate key (from right to left excluding parentmost)
    # Example chain: streets, cities, countries
    # intermediate keys in order: cities, then streets
    for idx in range(len(chain) - 2, -1, -1):
        key = chain[idx]
        # If node is dict, choose a key.
        if isinstance(node, dict):
            next_k = rng.choice(list(node.keys()))
            chosen[key] = next_k
            node = node[next_k]
            continue

        # If node is list[str], choose an item. This should only happen at leaf.
        if _is_str_list(node):
            chosen[key] = rng.choice(node)
            node = None
            continue

        raise RelationshipError(f"{'@'.join(chain)}: unexpected node type {type(node).__name__} while resolving")

    return chosen


def format_location_from_relationships(resolved: Mapping[str, str]) -> str:
    """
    Convenience formatter, if you want to use it for persona 'location'.
    Tries common naming patterns:
      streets + cities + countries
      cities + countries
    Falls back to joining values from most specific to least.
    """
    # Prefer plural keys that match your filename convention
    street = resolved.get("streets") or resolved.get("street")
    city = resolved.get("cities") or resolved.get("city")
    country = resolved.get("countries") or resolved.get("country")

    parts: List[str] = []
    if street:
        parts.append(street)
    if city:
        parts.append(city)
    if country:
        parts.append(country)

    if parts:
        return ", ".join(parts)

    # fallback: childmost first
    return ", ".join(resolved[k] for k in resolved.keys())
