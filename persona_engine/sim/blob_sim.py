from __future__ import annotations

import json
import logging
import math
import random
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

from ..generator import generate_persona, persona_to_prompt
from ..models import Persona
from ..scoring import score_mutual


logger = logging.getLogger(__name__)


Decider = Literal["heuristic", "openai"]
Outcome = Literal["pair", "fling", "avoid", "remove"]


@dataclass
class Blob:
    idx: int
    persona: Persona
    x: float
    y: float
    vx: float
    vy: float
    alive: bool = True
    cooldown: int = 0
    partner: Optional[int] = None
    exit_reason: Optional[str] = None
    known_ids: set[int] = field(default_factory=set)
    recent_memories: List[Dict[str, object]] = field(default_factory=list)
    memory_version: int = 0
    pending_decision: bool = False
    violence_rep: int = 0
    promiscuity_rep: int = 0


def iter_blob_sim(
    *,
    agents: int = 18,
    steps: int = 600,
    seed: int = 123,
    pack: str = "default",
    lib_dir: Optional[str] = None,
    lib_files: Optional[Dict[str, str]] = None,
    interaction_radius: float = 0.06,
    speed: float = 0.02,
    decider: Decider = "heuristic",
    openai_model: str = "gpt-4o-mini",
    openai_temperature: float = 0.3,
    api_base_url: Optional[str] = None,
    api_key_env: str = "OPENAI_API_KEY",
    max_messages: int = 20,
    llm_concurrency: int = 1,
    pair_cache_size: int = 2000,
    max_interactions_per_tick: int = 1,
    memory_size: int = 8,
    max_pending_requests: int = 8,
):
    """
    Streaming version of the blob sim.

    Yields frames:
      {"t": int, "blobs": [...], "event": optional dict}
    """
    if agents < 2:
        raise ValueError("agents must be >= 2")
    if steps < 1:
        raise ValueError("steps must be >= 1")
    if max_messages < 1:
        raise ValueError("max_messages must be >= 1")
    if llm_concurrency < 1:
        raise ValueError("llm_concurrency must be >= 1")
    if pair_cache_size < 0:
        raise ValueError("pair_cache_size must be >= 0")
    if max_interactions_per_tick < 1:
        raise ValueError("max_interactions_per_tick must be >= 1")
    if memory_size < 1:
        raise ValueError("memory_size must be >= 1")
    if max_pending_requests < 1:
        raise ValueError("max_pending_requests must be >= 1")

    rng = random.Random(seed)

    blobs: List[Blob] = []
    for i in range(agents):
        ps = rng.randint(0, 2**31 - 1)
        p = generate_persona(seed=ps, pack=pack, lib_dir=lib_dir, lib_files=lib_files)
        x = rng.random()
        y = rng.random()
        ang = rng.random() * (2.0 * math.pi)
        vx = math.cos(ang) * speed
        vy = math.sin(ang) * speed
        blobs.append(Blob(idx=i, persona=p, x=x, y=y, vx=vx, vy=vy))

    # Initial frame so UI shows blobs immediately even when first LLM call is slow.
    initial_blobs = [
        {
            "id": b.idx,
            "name": b.persona.name,
            "seed": b.persona.seed,
            "alive": b.alive,
            "x": round(b.x, 6),
            "y": round(b.y, 6),
            "partner": b.partner,
            "exit_reason": b.exit_reason,
            "known_count": len(b.known_ids),
            "memory_count": len(b.recent_memories),
            "pending_decision": b.pending_decision,
            "violence_rep": b.violence_rep,
            "promiscuity_rep": b.promiscuity_rep,
        }
        for b in blobs
    ]
    yield {"t": -1, "blobs": initial_blobs, "events": [], "event": None, "inflight_requests": 0}

    r2 = interaction_radius * interaction_radius

    openai_client = None
    executor: Optional[ThreadPoolExecutor] = None
    if decider == "openai":
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "openai package not installed. Install with: pip install openai "
                "(or, from the repo root: pip install -e '.[llm]')."
            ) from e
        import os

        api_key = os.environ.get(api_key_env)
        if not api_key:  # pragma: no cover
            raise RuntimeError(f"{api_key_env} is not set")
        openai_client = OpenAI(api_key=api_key, base_url=api_base_url)
        executor = ThreadPoolExecutor(max_workers=llm_concurrency)

    # LRU-ish cache: key is pair state including memory versions.
    pair_cache: Dict[Tuple[int, int, int, int], Tuple[List[Dict[str, str]], Outcome, str, str]] = {}
    # Non-blocking in-flight LLM requests keyed by pair ids.
    pending: Dict[Tuple[int, int], Dict[str, object]] = {}

    def pair_key(ia: int, ib: int) -> Tuple[int, int, int, int]:
        sa = int(blobs[ia].persona.seed)
        sb = int(blobs[ib].persona.seed)
        mva = int(blobs[ia].memory_version)
        mvb = int(blobs[ib].memory_version)
        if sa <= sb:
            return (sa, sb, mva, mvb)
        return (sb, sa, mvb, mva)

    def cache_get(k: Tuple[int, int, int, int]) -> Optional[Tuple[List[Dict[str, str]], Outcome, str, str]]:
        v = pair_cache.get(k)
        if v is None:
            return None
        # touch for LRU behavior
        pair_cache.pop(k, None)
        pair_cache[k] = v
        return v

    def cache_put(k: Tuple[int, int, int, int], v: Tuple[List[Dict[str, str]], Outcome, str, str]) -> None:
        if pair_cache_size == 0:
            return
        if k in pair_cache:
            pair_cache.pop(k, None)
        pair_cache[k] = v
        # trim oldest
        while len(pair_cache) > pair_cache_size:
            oldest = next(iter(pair_cache))
            pair_cache.pop(oldest, None)

    def decide_with_openai(
        pa: Persona,
        pb: Persona,
        violence_rep_a: int,
        violence_rep_b: int,
        promiscuity_rep_a: int,
        promiscuity_rep_b: int,
        memory_a: List[Dict[str, object]],
        memory_b: List[Dict[str, object]],
        mutual_connection_names: List[str],
    ) -> Tuple[List[Dict[str, str]], Outcome, str, str]:
        assert openai_client is not None
        min_turns = min(max_messages, 6)
        sys = (
            "You are simulating two adults meeting in a social blob simulation. "
            f"Generate a non-graphic, non-explicit chat with BETWEEN {min_turns} and {max_messages} lines, then decide an outcome.\n"
            "Rules:\n"
            "- pair: both personas leave the game together (no longer moving).\n"
            "- fling: both stay in the simulation.\n"
            "- avoid: directional elimination. The chooser survives; the target is removed from the simulation.\n"
            "- no neutral avoid and no generic remove outcome.\n"
            "Social consequences:\n"
            "- frequent fling outcomes increase promiscuity reputation, which can lower long-term trust.\n"
            "- avoid eliminations increase violence reputation, which can increase social targeting.\n"
            "Personas are aware of reputations, recent interaction history, and mutual social connections.\n"
            "Return ONLY valid JSON with keys: messages (array of {speaker,text}), outcome, chooser.\n"
            "chooser must be 'a' or 'b' and is required when outcome='avoid'."
        )
        user = json.dumps(
            {
                "a_persona_prompt": persona_to_prompt(pa),
                "b_persona_prompt": persona_to_prompt(pb),
                "a_brief": _persona_blurb(pa),
                "b_brief": _persona_blurb(pb),
                "reputation": {
                    "a": {"violence_rep": violence_rep_a, "promiscuity_rep": promiscuity_rep_a},
                    "b": {"violence_rep": violence_rep_b, "promiscuity_rep": promiscuity_rep_b},
                },
                "a_recent_memory": memory_a,
                "b_recent_memory": memory_b,
                "mutual_connections": mutual_connection_names,
            },
            ensure_ascii=False,
        )

        raw = ""
        def _wants_no_temp(err: Exception) -> bool:
            s = str(err)
            return "Unsupported parameter" in s and "temperature" in s

        def _model_access_issue(err: Exception) -> bool:
            s = str(err)
            return ("model_not_found" in s) or ("does not have access to model" in s) or ("not have access to model" in s)

        try:
            try:
                resp = openai_client.responses.create(
                    model=openai_model,
                    temperature=openai_temperature,
                    input=[
                        {"role": "system", "content": sys},
                        {"role": "user", "content": user},
                    ],
                )
            except Exception as e_temp:
                if _wants_no_temp(e_temp):
                    logger.warning(
                        "Model does not support temperature; retrying without temperature",
                        extra={"model": openai_model, "api_base_url": api_base_url or "", "api_key_env": api_key_env},
                    )
                    resp = openai_client.responses.create(
                        model=openai_model,
                        input=[
                            {"role": "system", "content": sys},
                            {"role": "user", "content": user},
                        ],
                    )
                else:
                    raise
            raw = getattr(resp, "output_text", "") or ""
        except Exception as e1:
            logger.warning(
                "Responses API failed, trying chat.completions fallback",
                extra={
                    "model": openai_model,
                    "api_base_url": api_base_url or "",
                    "api_key_env": api_key_env,
                    "error": str(e1),
                },
            )
            try:
                try:
                    resp = openai_client.chat.completions.create(
                        model=openai_model,
                        temperature=openai_temperature,
                        messages=[
                            {"role": "system", "content": sys},
                            {"role": "user", "content": user},
                        ],
                    )
                except Exception as e_temp2:
                    if _wants_no_temp(e_temp2):
                        resp = openai_client.chat.completions.create(
                            model=openai_model,
                            messages=[
                                {"role": "system", "content": sys},
                                {"role": "user", "content": user},
                            ],
                        )
                    else:
                        raise
                raw = resp.choices[0].message.content or ""
            except Exception as e2:
                hint = ""
                if _model_access_issue(e1) or _model_access_issue(e2):
                    hint = (
                        " Hint: your project likely lacks access to this model. "
                        "Pick a model you have access to (for example gpt-4o-mini or gpt-4.1-mini), "
                        "or enable access in your provider dashboard."
                    )
                raise RuntimeError(
                    f"LLM request failed for model='{openai_model}' "
                    f"(base_url='{api_base_url or 'default'}', api_key_env='{api_key_env}'): "
                    f"responses_error={e1}; chat_error={e2}.{hint}"
                ) from e2

        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            preview = raw[:300].replace("\n", "\\n")
            raise ValueError(f"Model did not return JSON. Raw preview: {preview}")
        data = json.loads(raw[start : end + 1])
        outcome = data.get("outcome")
        if outcome not in ("pair", "fling", "avoid", "remove"):
            raise ValueError(f"Invalid outcome from model: {outcome}")
        chooser = str(data.get("chooser", "a")).lower()
        if chooser not in ("a", "b"):
            chooser = "a"
        if outcome == "remove":
            # Backward compatible normalize: remove -> avoid.
            outcome = "avoid"
        messages = data.get("messages") or []
        msgs: List[Dict[str, str]] = []
        for m in messages[:max_messages]:
            sp = str(m.get("speaker", ""))[:80]
            tx = str(m.get("text", ""))[:400]
            if sp and tx:
                msgs.append({"speaker": sp, "text": tx})
        return msgs, outcome, chooser, raw

    try:
        for t in range(steps):
            for b in blobs:
                if not b.alive:
                    continue
                if b.pending_decision:
                    # Freeze blobs that are currently waiting on an interaction decision.
                    continue
                if b.cooldown > 0:
                    b.cooldown -= 1
                b.x += b.vx
                b.y += b.vy
                if b.x < 0.0 or b.x > 1.0:
                    b.vx *= -1.0
                    b.x = _clamp(b.x, 0.0, 1.0)
                if b.y < 0.0 or b.y > 1.0:
                    b.vy *= -1.0
                    b.y = _clamp(b.y, 0.0, 1.0)

            events_this_tick: List[Dict[str, object]] = []

            alive_ids = [i for i, b in enumerate(blobs) if b.alive]
            rng.shuffle(alive_ids)
            used_ids: set[int] = set()
            pairs: List[Tuple[int, int]] = []
            pending_ids: set[int] = set()
            for pk in pending.keys():
                pending_ids.add(pk[0])
                pending_ids.add(pk[1])

            # Build disjoint interaction pairs this tick.
            for i in range(len(alive_ids)):
                ia = alive_ids[i]
                a = blobs[ia]
                if not a.alive or a.cooldown > 0 or ia in used_ids or ia in pending_ids:
                    continue
                chosen_ib: Optional[int] = None
                for j in range(i + 1, len(alive_ids)):
                    ib = alive_ids[j]
                    b = blobs[ib]
                    if not b.alive or b.cooldown > 0 or ib in used_ids or ib in pending_ids:
                        continue
                    if _dist2(a, b) > r2:
                        continue
                    chosen_ib = ib
                    break
                if chosen_ib is None:
                    continue
                used_ids.add(ia)
                used_ids.add(chosen_ib)
                pairs.append((ia, chosen_ib))
                if len(pairs) >= max_interactions_per_tick:
                    break

            decisions: List[Tuple[int, int, List[Dict[str, str]], Outcome, str, str]] = []

            if pairs:
                if decider == "openai":
                    for ia, ib in pairs:
                        pair_ids = (min(ia, ib), max(ia, ib))
                        if pair_ids in pending:
                            continue
                        if len(pending) >= max_pending_requests:
                            break

                        k = pair_key(ia, ib)
                        cached = cache_get(k)
                        if cached is not None:
                            msgs, outcome, chooser, raw = cached
                            decisions.append((ia, ib, msgs, outcome, chooser, raw))
                            continue
                        if executor is None:  # pragma: no cover
                            raise RuntimeError("executor not initialized")
                        mutual_ids = sorted((blobs[ia].known_ids & blobs[ib].known_ids))
                        mutual_names = [blobs[mid].persona.name for mid in mutual_ids[:8]]
                        fut = executor.submit(
                            decide_with_openai,
                            blobs[ia].persona,
                            blobs[ib].persona,
                            int(blobs[ia].violence_rep),
                            int(blobs[ib].violence_rep),
                            int(blobs[ia].promiscuity_rep),
                            int(blobs[ib].promiscuity_rep),
                            list(blobs[ia].recent_memories[-memory_size:]),
                            list(blobs[ib].recent_memories[-memory_size:]),
                            mutual_names,
                        )
                        blobs[ia].pending_decision = True
                        blobs[ib].pending_decision = True
                        pending[pair_ids] = {"ia": ia, "ib": ib, "k": k, "future": fut}

                    # Non-blocking poll: apply only completed requests this tick.
                    done_keys: List[Tuple[int, int]] = []
                    for pair_ids, meta in list(pending.items()):
                        fut = meta["future"]
                        if not isinstance(fut, Future) or not fut.done():
                            continue
                        ia = int(meta["ia"])
                        ib = int(meta["ib"])
                        k = meta["k"]
                        try:
                            msgs, outcome, chooser, raw = fut.result()
                        except Exception as e:
                            # Keep sim fluid: fall back to heuristic if one LLM request fails.
                            logger.exception("LLM interaction failed; falling back to heuristic")
                            msgs = _heuristic_chat(
                                blobs[ia].persona,
                                blobs[ib].persona,
                                rng=rng,
                                max_messages=max_messages,
                                memory_a=list(blobs[ia].recent_memories[-memory_size:]),
                                memory_b=list(blobs[ib].recent_memories[-memory_size:]),
                                mutual_names=[blobs[mid].persona.name for mid in sorted((blobs[ia].known_ids & blobs[ib].known_ids))[:8]],
                            )
                            outcome, chooser = _decide_outcome(
                                blobs[ia].persona,
                                blobs[ib].persona,
                                violence_rep_a=int(blobs[ia].violence_rep),
                                violence_rep_b=int(blobs[ib].violence_rep),
                                promiscuity_rep_a=int(blobs[ia].promiscuity_rep),
                                promiscuity_rep_b=int(blobs[ib].promiscuity_rep),
                                memory_a=list(blobs[ia].recent_memories[-memory_size:]),
                                memory_b=list(blobs[ib].recent_memories[-memory_size:]),
                                mutual_count=len(blobs[ia].known_ids & blobs[ib].known_ids),
                                rng=rng,
                            )
                            raw = f"llm_error_fallback: {type(e).__name__}: {e}"

                        blobs[ia].pending_decision = False
                        blobs[ib].pending_decision = False
                        cache_put(k, (msgs, outcome, chooser, raw))
                        decisions.append((ia, ib, msgs, outcome, chooser, raw))
                        done_keys.append(pair_ids)

                    for dk in done_keys:
                        pending.pop(dk, None)
                else:
                    for ia, ib in pairs:
                        k = pair_key(ia, ib)
                        cached = cache_get(k)
                        if cached is not None:
                            msgs, outcome, chooser, raw = cached
                            decisions.append((ia, ib, msgs, outcome, chooser, raw))
                            continue

                        msgs = _heuristic_chat(
                            blobs[ia].persona,
                            blobs[ib].persona,
                            rng=rng,
                            max_messages=max_messages,
                            memory_a=list(blobs[ia].recent_memories[-memory_size:]),
                            memory_b=list(blobs[ib].recent_memories[-memory_size:]),
                            mutual_names=[blobs[mid].persona.name for mid in sorted((blobs[ia].known_ids & blobs[ib].known_ids))[:8]],
                        )
                        outcome, chooser = _decide_outcome(
                            blobs[ia].persona,
                            blobs[ib].persona,
                            violence_rep_a=int(blobs[ia].violence_rep),
                            violence_rep_b=int(blobs[ib].violence_rep),
                            promiscuity_rep_a=int(blobs[ia].promiscuity_rep),
                            promiscuity_rep_b=int(blobs[ib].promiscuity_rep),
                            memory_a=list(blobs[ia].recent_memories[-memory_size:]),
                            memory_b=list(blobs[ib].recent_memories[-memory_size:]),
                            mutual_count=len(blobs[ia].known_ids & blobs[ib].known_ids),
                            rng=rng,
                        )
                        raw = ""
                        cache_put(k, (msgs, outcome, chooser, raw))
                        decisions.append((ia, ib, msgs, outcome, chooser, raw))

            # Apply decisions in pair discovery order for determinism.
            for ia, ib, msgs, outcome, chooser, raw in decisions:
                a = blobs[ia]
                b = blobs[ib]
                if not (a.alive and b.alive):
                    continue
                before_alive = sum(1 for bb in blobs if bb.alive)
                mutual_count = len(a.known_ids & b.known_ids)
                detail = _apply_outcome(blobs, ia, ib, outcome, chooser=chooser, rng=rng)
                after_alive = sum(1 for bb in blobs if bb.alive)
                _remember_interaction(
                    blobs=blobs,
                    t=t,
                    ia=ia,
                    ib=ib,
                    outcome=outcome,
                    chooser=chooser,
                    memory_size=memory_size,
                    mutual_count=mutual_count,
                )

                events_this_tick.append(
                    {
                        "t": t,
                        "a": {"id": ia, "name": a.persona.name, "seed": a.persona.seed},
                        "b": {"id": ib, "name": b.persona.name, "seed": b.persona.seed},
                        "chat": msgs,
                        "outcome": outcome,
                        "chooser": chooser,
                        "mutual_count": mutual_count,
                        "reputation": {
                            "a": {"violence_rep": a.violence_rep, "promiscuity_rep": a.promiscuity_rep},
                            "b": {"violence_rep": b.violence_rep, "promiscuity_rep": b.promiscuity_rep},
                        },
                        "detail": detail,
                        "alive_before": before_alive,
                        "alive_after": after_alive,
                        "raw": raw if raw else None,
                    }
                )

            frame_blobs = [
                {
                    "id": b.idx,
                    "name": b.persona.name,
                    "seed": b.persona.seed,
                    "alive": b.alive,
                    "x": round(b.x, 6),
                    "y": round(b.y, 6),
                    "partner": b.partner,
                    "exit_reason": b.exit_reason,
                    "known_count": len(b.known_ids),
                    "memory_count": len(b.recent_memories),
                    "pending_decision": b.pending_decision,
                    "violence_rep": b.violence_rep,
                    "promiscuity_rep": b.promiscuity_rep,
                }
                for b in blobs
            ]
            yield {
                "t": t,
                "blobs": frame_blobs,
                "events": events_this_tick,
                "event": (events_this_tick[0] if events_this_tick else None),
                "inflight_requests": len(pending) if decider == "openai" else 0,
            }

            if sum(1 for bb in blobs if bb.alive) <= 1:
                break
    finally:
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _dist2(a: Blob, b: Blob) -> float:
    dx = a.x - b.x
    dy = a.y - b.y
    return dx * dx + dy * dy


def _remember_interaction(
    *,
    blobs: List[Blob],
    t: int,
    ia: int,
    ib: int,
    outcome: Outcome,
    chooser: str,
    memory_size: int,
    mutual_count: int,
) -> None:
    a = blobs[ia]
    b = blobs[ib]

    a.known_ids.add(ib)
    b.known_ids.add(ia)

    entry_a: Dict[str, object] = {
        "t": t,
        "with_id": ib,
        "with_name": b.persona.name,
        "outcome": outcome,
        "chooser": chooser,
        "mutual_count": mutual_count,
        "violence_rep_after": a.violence_rep,
        "promiscuity_rep_after": a.promiscuity_rep,
    }
    entry_b: Dict[str, object] = {
        "t": t,
        "with_id": ia,
        "with_name": a.persona.name,
        "outcome": outcome,
        "chooser": chooser,
        "mutual_count": mutual_count,
        "violence_rep_after": b.violence_rep,
        "promiscuity_rep_after": b.promiscuity_rep,
    }

    a.recent_memories.append(entry_a)
    b.recent_memories.append(entry_b)
    if len(a.recent_memories) > memory_size:
        a.recent_memories = a.recent_memories[-memory_size:]
    if len(b.recent_memories) > memory_size:
        b.recent_memories = b.recent_memories[-memory_size:]
    a.memory_version += 1
    b.memory_version += 1


def _persona_blurb(p: Persona) -> str:
    d = p.to_dict()
    traits = ", ".join(d.get("personality_traits") or [])
    interests = ", ".join(d.get("interests") or [])
    return f'{d["name"]} ({d["age"]}, {d["occupation"]}; traits: {traits}; interests: {interests})'


def _heuristic_chat(
    a: Persona,
    b: Persona,
    *,
    rng: random.Random,
    max_messages: int,
    memory_a: List[Dict[str, object]],
    memory_b: List[Dict[str, object]],
    mutual_names: List[str],
) -> List[Dict[str, str]]:
    ad = a.to_dict()
    bd = b.to_dict()
    shared = sorted(set(ad.get("interests") or []).intersection(set(bd.get("interests") or [])))
    topic = rng.choice(shared) if shared else rng.choice((ad.get("interests") or ["life"]))
    style_a = ad.get("communication_style") or "short and direct"
    style_b = bd.get("communication_style") or "short and direct"
    turns_cap = max(1, max_messages)
    lo = min(6, turns_cap)
    hi = min(12, turns_cap)
    turns = lo if hi <= lo else rng.randint(lo, hi)

    question_pool_a = [
        f"[{style_a}] What's your take on {topic}?",
        f"[{style_a}] What are you optimizing for right now?",
        f"[{style_a}] Are you more long-term or in-the-moment?",
        f"[{style_a}] What do you care about most this year?",
        f"[{style_a}] How do you handle conflict usually?",
    ]
    question_pool_b = [
        f"[{style_b}] You seem focused. What's driving you lately?",
        f"[{style_b}] What's your day-to-day like in {bd.get('occupation')}?",
        f"[{style_b}] Dealbreaker question: what do you avoid in people?",
        f"[{style_b}] Would we align on lifestyle or clash?",
        f"[{style_b}] Are you risk-heavy or risk-averse?",
    ]
    answer_pool_a = [
        f"[{style_a}] I'm a {ad.get('occupation')}; my focus is {ad.get('life_goal')}.",
        f"[{style_a}] I lean {ad.get('risk_tolerance')} with money as {ad.get('financial_attitude')}.",
        f"[{style_a}] I communicate {style_a} and care about {topic}.",
        f"[{style_a}] My main concern lately is {ad.get('main_concern')}.",
    ]
    answer_pool_b = [
        f"[{style_b}] I work as a {bd.get('occupation')} and aim to {bd.get('life_goal')}.",
        f"[{style_b}] I’m usually {bd.get('communication_style')} and {bd.get('risk_tolerance')}.",
        f"[{style_b}] Biggest concern for me is {bd.get('main_concern')}.",
        f"[{style_b}] I care a lot about {topic} and long-term fit.",
    ]

    if mutual_names:
        name = mutual_names[0]
        question_pool_a.append(f"[{style_a}] Do you know {name}?")
        question_pool_b.append(f"[{style_b}] Heard your name from {name} before. True?")

    if memory_a:
        last = memory_a[-1]
        with_name = str(last.get("with_name", "someone"))
        outcome = str(last.get("outcome", "unknown"))
        answer_pool_a.append(f"[{style_a}] Last time with {with_name} ended as {outcome}; I'm adjusting.")
    if memory_b:
        last = memory_b[-1]
        with_name = str(last.get("with_name", "someone"))
        outcome = str(last.get("outcome", "unknown"))
        answer_pool_b.append(f"[{style_b}] My recent interaction with {with_name} was {outcome}.")

    msgs: List[Dict[str, str]] = []
    speaker_is_a = True
    for i in range(turns):
        if speaker_is_a:
            text = rng.choice(question_pool_a if i % 2 == 0 else answer_pool_a)
            msgs.append({"speaker": ad["name"], "text": text})
        else:
            text = rng.choice(question_pool_b if i % 2 == 0 else answer_pool_b)
            msgs.append({"speaker": bd["name"], "text": text})
        speaker_is_a = not speaker_is_a

    return msgs[:max_messages]


def _decide_outcome(
    a: Persona,
    b: Persona,
    *,
    violence_rep_a: int,
    violence_rep_b: int,
    promiscuity_rep_a: int,
    promiscuity_rep_b: int,
    memory_a: List[Dict[str, object]],
    memory_b: List[Dict[str, object]],
    mutual_count: int,
    rng: random.Random,
) -> Tuple[Outcome, str]:
    # Symmetric "mutual compatibility".
    s = score_mutual(a, b)

    # Bias based on some personality signals for chaos.
    ad = a.to_dict()
    bd = b.to_dict()
    direct = ("direct and blunt" in (ad.get("personality_traits") or [])) or ("direct and blunt" in (bd.get("personality_traits") or []))
    impulsive = ("impulsive" in (ad.get("personality_traits") or [])) or ("impulsive" in (bd.get("personality_traits") or []))

    # Deterministic-ish buckets with tiny randomness to avoid repeats.
    jitter = rng.uniform(-0.5, 0.5)
    s2 = s + jitter + (min(mutual_count, 4) * 0.25)

    def last_outcome(mem: List[Dict[str, object]]) -> str:
        if not mem:
            return ""
        return str(mem[-1].get("outcome", ""))

    lo_a = last_outcome(memory_a)
    lo_b = last_outcome(memory_b)
    if lo_a == "avoid" or lo_b == "avoid":
        s2 -= 0.6
    if lo_a == "fling" or lo_b == "fling":
        s2 += 0.25
    if lo_a == "pair" or lo_b == "pair":
        s2 += 0.35

    # Social consequences: high reputations reduce "stable trust" dynamics.
    social_drag = (violence_rep_a + violence_rep_b) * 0.22 + (promiscuity_rep_a + promiscuity_rep_b) * 0.14
    s2 -= social_drag

    # If the other side is perceived as more violent, this side is more likely to preemptively avoid.
    chooser_bias = (violence_rep_b - violence_rep_a) * 0.18
    chooser = "a" if (chooser_bias + rng.uniform(-0.15, 0.15)) >= 0 else "b"

    if s2 >= 7.5:
        return "pair", chooser
    if s2 >= 5.5:
        return ("fling", chooser) if impulsive and rng.random() < 0.6 else ("pair", chooser)
    if s2 >= 3.5:
        return ("avoid", chooser) if direct and rng.random() < 0.5 else ("fling", chooser)
    return "avoid", chooser


def _apply_outcome(
    blobs: List[Blob],
    ia: int,
    ib: int,
    outcome: Outcome,
    *,
    chooser: str,
    rng: random.Random,
) -> Dict[str, object]:
    a = blobs[ia]
    b = blobs[ib]
    if not (a.alive and b.alive):
        return {}

    if outcome == "pair":
        # Pair outcome removes both from the arena.
        a.partner = b.idx
        b.partner = a.idx
        a.alive = False
        b.alive = False
        a.exit_reason = "paired"
        b.exit_reason = "paired"
        # Pairing tends to dampen prior promiscuity rep slightly.
        a.promiscuity_rep = max(0, a.promiscuity_rep - 1)
        b.promiscuity_rep = max(0, b.promiscuity_rep - 1)
        detail: Dict[str, object] = {"removed_ids": [a.idx, b.idx], "reason": "pair_exit"}
    elif outcome == "fling":
        # Both stay in game.
        a.promiscuity_rep += 1
        b.promiscuity_rep += 1
        a.vx += rng.uniform(-0.02, 0.02)
        a.vy += rng.uniform(-0.02, 0.02)
        b.vx += rng.uniform(-0.02, 0.02)
        b.vy += rng.uniform(-0.02, 0.02)
        detail = {"removed_ids": [], "reason": "fling"}
    elif outcome == "avoid":
        # Directional elimination: chooser survives, target removed.
        chooser_blob = a if chooser == "a" else b
        target_blob = b if chooser == "a" else a
        chooser_blob.violence_rep += 1
        target_blob.alive = False
        target_blob.partner = None
        target_blob.exit_reason = "avoided_out"
        detail = {
            "removed_ids": [target_blob.idx],
            "reason": "avoid_elimination",
            "eliminator_id": chooser_blob.idx,
            "eliminated_id": target_blob.idx,
        }
    elif outcome == "remove":
        # Backward compatibility: normalize remove to avoid-elimination.
        chooser_blob = a if chooser == "a" else b
        target_blob = b if chooser == "a" else a
        chooser_blob.violence_rep += 1
        target_blob.alive = False
        target_blob.partner = None
        target_blob.exit_reason = "avoided_out"
        detail = {
            "removed_ids": [target_blob.idx],
            "reason": "avoid_elimination",
            "eliminator_id": chooser_blob.idx,
            "eliminated_id": target_blob.idx,
        }
    else:
        raise ValueError(f"Unknown outcome: {outcome}")

    a.cooldown = 12
    b.cooldown = 12
    return detail


def run_blob_sim(
    *,
    agents: int = 18,
    steps: int = 600,
    seed: int = 123,
    pack: str = "default",
    lib_dir: Optional[str] = None,
    lib_files: Optional[Dict[str, str]] = None,
    interaction_radius: float = 0.06,
    speed: float = 0.02,
    decider: Decider = "heuristic",
    openai_model: str = "gpt-4o-mini",
    openai_temperature: float = 0.3,
    api_base_url: Optional[str] = None,
    api_key_env: str = "OPENAI_API_KEY",
    max_messages: int = 20,
    llm_concurrency: int = 1,
    pair_cache_size: int = 2000,
    max_interactions_per_tick: int = 1,
    memory_size: int = 8,
    max_pending_requests: int = 8,
) -> Dict[str, object]:
    """
    Headless "blobs bouncing around" sim.

    Output is a deterministic (seeded) event log you can render later.
    """
    events: List[Dict[str, object]] = []
    last_t = 0
    last_blobs: List[Dict[str, object]] = []
    for frame in iter_blob_sim(
        agents=agents,
        steps=steps,
        seed=seed,
        pack=pack,
        lib_dir=lib_dir,
        lib_files=lib_files,
        interaction_radius=interaction_radius,
        speed=speed,
        decider=decider,
        openai_model=openai_model,
        openai_temperature=openai_temperature,
        api_base_url=api_base_url,
        api_key_env=api_key_env,
        max_messages=max_messages,
        llm_concurrency=llm_concurrency,
        pair_cache_size=pair_cache_size,
        max_interactions_per_tick=max_interactions_per_tick,
        memory_size=memory_size,
        max_pending_requests=max_pending_requests,
    ):
        last_t = int(frame["t"])
        last_blobs = list(frame["blobs"])
        tick_events = frame.get("events") or []
        for ev in tick_events:
            events.append(ev)

    survivors = [b for b in last_blobs if b.get("alive")]

    counts: Dict[str, int] = {"pair": 0, "fling": 0, "avoid": 0, "remove": 0}
    eliminated_total = 0
    paired_exit_total = 0
    for e in events:
        o = e.get("outcome")
        if isinstance(o, str) and o in counts:
            counts[o] += 1
        detail = e.get("detail")
        if isinstance(detail, dict):
            reason = str(detail.get("reason", ""))
            if reason == "avoid_elimination":
                eliminated_total += 1
            elif reason == "pair_exit":
                paired_exit_total += 2

    interactions = len(events)
    eliminate_rate = (eliminated_total / interactions) if interactions else 0.0
    pair_rate = (counts["pair"] / interactions) if interactions else 0.0
    fling_rate = (counts["fling"] / interactions) if interactions else 0.0
    avoid_rate = (counts["avoid"] / interactions) if interactions else 0.0

    return {
        "sim": "blob_sim",
        "seed": seed,
        "pack": pack,
        "agents": agents,
        "steps_requested": steps,
        "steps_ran": (last_t + 1) if last_blobs else 0,
        "interaction_radius": interaction_radius,
        "decider": decider,
        "stats": {
            "interactions": interactions,
            "outcome_counts": counts,
            "pair_rate": round(pair_rate, 6),
            "fling_rate": round(fling_rate, 6),
            "avoid_rate": round(avoid_rate, 6),
            "remove_rate": round(eliminate_rate, 6),
            "removed_total": eliminated_total,
            "paired_exit_total": paired_exit_total,
            # Friendly aliases for model-comparison dashboards.
            "marry_rate": round(pair_rate, 6),
            "promiscuous_rate": round(fling_rate, 6),
            "eliminate_rate": round(eliminate_rate, 6),
        },
        "final_alive": len(survivors),
        "survivors": [
            {
                "id": int(b["id"]),
                "name": str(b["name"]),
                "seed": int(b["seed"]),
                "x": float(b["x"]),
                "y": float(b["y"]),
                "partner": b.get("partner"),
                "known_count": int(b.get("known_count", 0)),
                "memory_count": int(b.get("memory_count", 0)),
                "violence_rep": int(b.get("violence_rep", 0)),
                "promiscuity_rep": int(b.get("promiscuity_rep", 0)),
            }
            for b in survivors
        ],
        "events": events,
    }
