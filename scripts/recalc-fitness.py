#!/usr/bin/env python3
"""
Cognitive Fitness Recalculator
==============================

Reads the cognitive-fitness.jsonl ledger, computes rolling-window fitness
scores for three systems (lens, trait, delegation), and writes cached JSON
files consumed by the delegation hooks (and any future lens/trait selector).

Usage:
    python3 scripts/recalc-fitness.py [--dry-run] [--system lens|trait|delegation]
                                      [--trigger NAME]

Options:
    --dry-run    Print computed scores to stdout instead of writing files
    --system     Only recalculate for a specific system
    --trigger    Label recorded in the invocation ledger (default: env
                 RECALC_FITNESS_TRIGGER, else "cli"). The SessionStart hook
                 passes --trigger session-start.

Output files (under _graph/cache/):
    lens-fitness.json, trait-fitness.json, delegation-fitness.json

Scoring model:
    - Rolling window: last `window_size` events per system+entity+domain combo
    - Exponential moving average; ASYMMETRIC by default (alpha_down >
      alpha_up: a negative outcome moves the score faster than an
      equal-magnitude positive one - "lose trust fast, earn it slow",
      the loss-aversion / load-reversal asymmetry)
    - Muller-ratchet recovery floor: in the sparse-evidence regime
      (fewer than `minimum_viable_population` events) the score cannot be
      ratcheted to zero by a few unlucky negatives; at or above that
      population, genuine all-negative telemetry reads ~0 honestly
    - Cold start: fewer than `cold_start_threshold` events blends with the
      configured default (more events = more weight on observed)
    - Scores range 0.0-1.0 where 0.5 = neutral/default

Configuration (injectable, fail-open to code defaults):
    _graph/cache/fitness-config.json - taxonomy tables (lens/trait defaults,
    cognitive-mode map, stale task-type skip-list) and all numeric tunables.
    A fresh install ships EMPTY taxonomy tables: entity names flow in as
    strings from the producers, so the scorer needs no pre-registered
    taxonomy to work.

Environment flags:
    FITNESS_EMA_HONESTY      default "1"; set 0 to restore the legacy
                             symmetric EMA + disable the recovery floor
    LENS_NICHE_SELECTION     default "1"; set 0 to restore pure
                             top-2-by-fitness quick_picks

Consumers:
    - delegation-enforcer.py (UserPromptSubmit hook) reads
      delegation-fitness.json for the per-task-type fitness hint
    - future lens/trait selectors read lens-fitness.json / trait-fitness.json
"""

try:
    import fcntl  # POSIX file locking
except ImportError:  # Windows: degrade to best-effort lock-free (no fcntl)
    class _NoFcntl:
        LOCK_EX = LOCK_UN = LOCK_NB = LOCK_SH = 0
        @staticmethod
        def flock(*_a, **_k):
            return None
    fcntl = _NoFcntl()
import json
import os
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from scripts.lib.cache_writer import atomic_write_json  # noqa: E402
from scripts.lib.delegation_outcomes import (  # noqa: E402
    _is_valid_was_delegated,
    is_quarantined,
)
from scripts.lib.plugin_paths import plugin_root  # noqa: E402

# ---------------------------------------------------------------------------
# Injectable configuration. Code defaults below; _graph/cache/
# fitness-config.json overrides individual keys (same-type values only,
# fail-open: a missing/malformed file or wrong-typed key falls back to the
# code default for that key). Taxonomy tables ship EMPTY on a fresh install -
# entity/domain names flow in as strings from the producers.
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "window_size": 30,
    # Legacy symmetric EMA rate (used when FITNESS_EMA_HONESTY=0 or an
    # explicit alpha is passed by a caller).
    "ema_alpha": 0.3,
    # Asymmetric rates: gaining trust (up) vs losing trust (down).
    "ema_alpha_up": 0.30,
    "ema_alpha_down": 0.45,
    # Sparse-regime anti-death seed (well below the 0.5 neutral midline).
    "recovery_floor": 0.15,
    "score_ceil": 1.0,
    # Below this event count the recovery floor engages; at/above it the
    # score is statistically meaningful and passes through honestly.
    "minimum_viable_population": 8,
    # Below this event count the EMA is blended with the default score.
    "cold_start_threshold": 5,
    "cold_start_default_weight": 0.8,
    # Taxonomy tables (empty on a fresh install; injectable via config).
    "lens_defaults": {},           # lens name -> default score
    "lens_cognitive_modes": {},    # lens name -> cognitive mode (niche map)
    "static_quick_picks": [],      # fallback quick_picks when no data exists
    "trait_defaults": {},          # task_type -> {trait combo -> default}
    "stale_trait_task_types": [],  # task_types to skip at recalc time
}

FITNESS_CONFIG_NAME = "fitness-config.json"


# Valid ranges for numeric overrides. A value outside its range is rejected
# (code default kept) - e.g. a zero/negative cold_start_threshold would
# silently disable blending, an out-of-unit alpha breaks the EMA contract.
_CONFIG_RANGES = {
    "window_size": (1, 10_000),
    "ema_alpha": (0.0, 1.0),
    "ema_alpha_up": (0.0, 1.0),
    "ema_alpha_down": (0.0, 1.0),
    "recovery_floor": (0.0, 1.0),
    "score_ceil": (0.0, 1.0),
    "minimum_viable_population": (0, 10_000),
    "cold_start_threshold": (1, 10_000),
    "cold_start_default_weight": (0.0, 1.0),
}


def load_config(root: Path) -> dict:
    """Merge fitness-config.json over the code defaults.

    Per-key validation: an override is accepted only when its type matches
    the default's type (bool/int/float treated leniently for numerics) AND,
    for numerics, it falls inside _CONFIG_RANGES. Fail-open: any read/parse
    problem returns pure code defaults; an invalid key keeps its default.
    """
    cfg = dict(DEFAULT_CONFIG)
    path = Path(root) / "_graph" / "cache" / FITNESS_CONFIG_NAME
    try:
        with open(path, encoding="utf-8") as f:
            overrides = json.load(f)
        if not isinstance(overrides, dict):
            return cfg
        for key, default in DEFAULT_CONFIG.items():
            if key not in overrides:
                continue
            val = overrides[key]
            if isinstance(default, (int, float)) and not isinstance(default, bool):
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    lo, hi = _CONFIG_RANGES.get(key, (float("-inf"), float("inf")))
                    if lo <= val <= hi:
                        cfg[key] = val
            elif isinstance(val, type(default)):
                cfg[key] = val
        return cfg
    except (OSError, json.JSONDecodeError):
        return cfg


def _ema_honesty_enabled() -> bool:
    """Master kill-switch for the asymmetric-EMA + recovery-floor behavior.
    Default ON. Set FITNESS_EMA_HONESTY=0 (or false/off/no) to restore exact
    legacy symmetric behavior. Read at call-time so tests/operators can
    toggle."""
    val = os.environ.get("FITNESS_EMA_HONESTY", "1")
    return str(val).strip().lower() not in ("0", "false", "off", "no", "")


def _niche_selection_enabled() -> bool:
    """Anti-monoculture quick_picks selection. Default ON; set
    LENS_NICHE_SELECTION=0 for pure top-2-by-fitness."""
    return os.environ.get("LENS_NICHE_SELECTION", "1") != "0"


def read_ledger(path: Path):
    """Read and parse the fitness ledger. Skips malformed lines."""
    events = []
    if not path.exists():
        return events
    with open(path, "r", encoding="utf-8") as f:
        # Shared lock pairs with the producers' LOCK_EX appends so a
        # SessionStart recalc never reads a row mid-append from a concurrent
        # session's Stop handler. Advisory + fail-open: if the lock cannot
        # be taken the read proceeds (malformed-line guard limits damage).
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        except Exception:
            pass
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                print(f"WARNING: Skipping malformed line {line_num} in ledger",
                      file=sys.stderr)
                continue
            if isinstance(event, dict):
                events.append(event)
    return events


def outcome_to_score(outcome):
    """Convert outcome string to numeric score."""
    return {"positive": 1.0, "negative": 0.0, "neutral": 0.5}.get(outcome, 0.5)


def _clamp01(x):
    """Bound a score to [0, 1] and map NaN to neutral 0.5. Real producers emit
    only {0.0, 0.5, 1.0} so for valid input this is a no-op, but it keeps the
    EMA output schema strictly bounded even on out-of-contract / NaN / inf
    values (defensive)."""
    try:
        if x != x:  # NaN
            return 0.5
        return round(max(0.0, min(1.0, x)), 4)
    except Exception:
        return 0.5


def _symmetric_ema(values, alpha):
    """Legacy symmetric EMA. Single update rate in both directions.
    Used directly when an explicit alpha is passed, when the honesty flag is
    off, and as the fail-open fallback path."""
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return _clamp01(ema)


def compute_ema(values, cfg, alpha=None, alpha_up=None, alpha_down=None):
    """Exponential moving average over a list of values in [0, 1].

    Default (FITNESS_EMA_HONESTY on): ASYMMETRIC - a value that pulls the EMA
    DOWN is folded in with alpha_down, one that pulls it UP (or holds) with
    alpha_up, so negative outcomes decay-in faster than equal-magnitude
    positive ones. Passing an explicit `alpha` forces the legacy SYMMETRIC
    behavior (back-compat for callers/tests). Return type is a rounded float
    in [0, 1].

    Fail-open: any unexpected error in the asymmetric path falls back to the
    legacy symmetric alpha; this never raises (it feeds a SessionStart
    recompute consumed by the live delegation-enforcer hook)."""
    if not values:
        return 0.5
    legacy_alpha = cfg["ema_alpha"]
    # Explicit alpha => caller wants legacy symmetric semantics.
    if alpha is not None:
        try:
            return _symmetric_ema(values, alpha)
        except Exception:
            return 0.5
    if not _ema_honesty_enabled():
        try:
            return _symmetric_ema(values, legacy_alpha)
        except Exception:
            return 0.5
    try:
        a_up = cfg["ema_alpha_up"] if alpha_up is None else float(alpha_up)
        a_down = cfg["ema_alpha_down"] if alpha_down is None else float(alpha_down)
        ema = values[0]
        for v in values[1:]:
            a = a_down if v < ema else a_up
            ema = a * v + (1 - a) * ema
        return _clamp01(ema)
    except Exception:
        # Fail-open to the legacy symmetric behavior, never crash.
        try:
            return _symmetric_ema(values, legacy_alpha)
        except Exception:
            return 0.5


def apply_ratchet_floor(score, event_count, cfg):
    """Muller-ratchet recovery floor + anti-windup clamp:
    max(floor, min(ceil, score)).

    The recovery floor engages ONLY in the sparse-evidence regime
    (event_count < minimum_viable_population), so a handful of unlucky
    negative events cannot permanently ratchet a low-N entity to zero (from
    which EMA recovery is arithmetically crippled). At or above the
    minimum-viable population the score is statistically meaningful: the
    floor drops to 0 and genuine all-negative telemetry passes through
    honestly - real one-sided data must read ~0, not be masked.

    No-op when the honesty flag is off. Fail-open: returns the input score
    unchanged on any error (never crashes the recompute)."""
    try:
        if not _ema_honesty_enabled():
            return score
        # Guard against a nonsensical negative event_count (data drift)
        # silently activating the floor; the sparse regime is strictly
        # 0 <= N < MVP. Real call sites pass len(windowed) (always >= 0).
        sparse = 0 <= event_count < cfg["minimum_viable_population"]
        effective_floor = cfg["recovery_floor"] if sparse else 0.0
        return round(max(effective_floor, min(cfg["score_ceil"], score)), 4)
    except Exception:
        return score


def _ema_meta(cfg):
    """Additive diagnostic header block so audits/consumers can see the
    asymmetry + floor that produced the scores. Does not remove or rename
    any existing field."""
    on = _ema_honesty_enabled()
    return {
        "ema_honesty": on,
        "alpha_up": cfg["ema_alpha_up"] if on else cfg["ema_alpha"],
        "alpha_down": cfg["ema_alpha_down"] if on else cfg["ema_alpha"],
        "recovery_floor": cfg["recovery_floor"] if on else 0.0,
        "min_viable_population": cfg["minimum_viable_population"] if on else None,
    }


def cold_start_blend(observed, default, event_count, cfg):
    """Blend observed score with default when few events exist.

    Pipeline order note: every call site runs EMA -> cold_start_blend ->
    apply_ratchet_floor. The floor is deliberately the LAST backstop on the
    blended value (not on the raw EMA): in the sparse regime the blend
    usually lifts the score above the floor already, and applying the floor
    last guarantees the published score never sits below it regardless of
    how the blend weights are configured."""
    threshold = cfg["cold_start_threshold"]
    default_w = cfg["cold_start_default_weight"]
    if event_count >= threshold:
        return observed
    # Linear interpolation: more events = more weight on observed
    observed_weight = (1 - default_w) + (default_w * (event_count / threshold))
    default_weight = 1 - observed_weight
    return round(observed * observed_weight + default * default_weight, 4)


# ---------------------------------------------------------------------------
# Lens system
# ---------------------------------------------------------------------------

def _niche_distance(lens_a, lens_b, mode_map):
    """1.0 if the two lenses have different cognitive modes, else 0.0.
    Unknown lenses are treated as distant (1.0) so the selector never
    over-penalises a lens missing from the mode map."""
    mode_a = mode_map.get(lens_a)
    mode_b = mode_map.get(lens_b)
    if mode_a is None or mode_b is None:
        return 1.0
    return 0.0 if mode_a == mode_b else 1.0


def _select_quick_picks(domain_scores, pick2_usage, mode_map):
    """Choose 2 lenses for a domain (anti-monoculture selection).

    Legacy (LENS_NICHE_SELECTION off): top-2 by raw fitness. That is pure
    competitive exclusion - the two fittest lenses win EVERY domain and the
    repertoire collapses to one pair across all domains.

    Niche-aware (default): pick-1 = highest-fitness lens (exploit). pick-2 =
    among lenses cognitively DISTANT from pick-1, the one used LEAST often as
    pick-2 so far this recalc pass, fitness as tiebreak (explore/rotate).
    This rotates the second slot across under-selected lenses. Fail-open to
    legacy top-2 if no distant lens exists. Output shape: list[str] of <=2.
    `pick2_usage` is a mutable counter shared across the domain loop
    (deterministic given sorted domain order).
    """
    # Sort by fitness desc, lens-name asc as tiebreak -> fully deterministic
    # output even when lenses tie on fitness (e.g. cold-start lenses blended
    # to the same float), independent of ledger event-arrival order.
    ranked = sorted(domain_scores, key=lambda x: (-x[1], x[0]))
    if not _niche_selection_enabled() or len(ranked) < 2:
        return [lens for lens, _ in ranked[:2]]
    first_lens = ranked[0][0]
    distant = [(lens, s) for lens, s in ranked[1:]
               if _niche_distance(first_lens, lens, mode_map) > 0]
    pool = distant if distant else ranked[1:]
    # Least-used-as-pick2 wins; higher fitness breaks ties. Rotation across
    # domains is what actually breaks the monoculture.
    second = min(pool, key=lambda ls: (pick2_usage[ls[0]], -ls[1]))[0]
    pick2_usage[second] += 1
    return [first_lens, second]


def recalc_lens(events, cfg):
    """Recalculate lens fitness scores."""
    lens_defaults = cfg["lens_defaults"]
    mode_map = cfg["lens_cognitive_modes"]

    # Group events by entity+domain
    grouped = defaultdict(list)
    for e in events:
        if e.get("system") != "lens":
            continue
        entity = e.get("entity", "")
        domain = e.get("domain", "_default")
        grouped[(entity, domain)].append(outcome_to_score(e.get("outcome", "neutral")))

    scores = {}
    for (entity, domain), values in grouped.items():
        windowed = values[-cfg["window_size"]:]
        ema = compute_ema(windowed, cfg)
        default = lens_defaults.get(entity, 0.5)
        blended = cold_start_blend(ema, default, len(windowed), cfg)
        blended = apply_ratchet_floor(blended, len(windowed), cfg)

        if entity not in scores:
            scores[entity] = {}
        scores[entity][domain] = blended

    # Ensure all configured default lenses appear
    for lens, default_score in lens_defaults.items():
        if lens not in scores:
            scores[lens] = {"_default": default_score}
        elif "_default" not in scores[lens]:
            scores[lens]["_default"] = default_score

    # Compute quick_picks per domain
    all_domains = set()
    for lens_scores in scores.values():
        all_domains.update(lens_scores.keys())

    quick_picks = {}
    pick2_usage = defaultdict(int)
    for domain in sorted(all_domains):
        domain_scores = []
        for lens, lens_scores in scores.items():
            score = lens_scores.get(domain, lens_scores.get("_default", 0.5))
            domain_scores.append((lens, score))
        quick_picks[domain] = _select_quick_picks(domain_scores, pick2_usage,
                                                  mode_map)

    # Always have a _default quick_picks
    if "_default" not in quick_picks:
        quick_picks["_default"] = list(cfg["static_quick_picks"])

    return {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": cfg["window_size"],
        "scores": scores,
        "quick_picks": quick_picks,
        **_ema_meta(cfg),
    }


# ---------------------------------------------------------------------------
# Trait system
# ---------------------------------------------------------------------------

def _warn_if_stale_skiplist_collides_with_live_config(root, cfg):
    """Cheap runtime guard that warns if a type in stale_trait_task_types is
    (re-)added to delegation-config as a trait-routed task_type. Silent
    suppression would otherwise starve the new type of fitness data
    forever."""
    try:
        stale = set(cfg["stale_trait_task_types"])
        if not stale:
            return
        cfg_path = Path(root) / "_graph" / "cache" / "delegation-config.json"
        if not cfg_path.exists():
            return  # nothing to validate against, skip silently
        with open(cfg_path, encoding="utf-8") as f:
            dcfg = json.load(f)
        live_trait_types = {
            k for k, v in (dcfg.get("task_types") or {}).items()
            if isinstance(v, dict) and "traits" in v
        }
        overlap = stale & live_trait_types
        if overlap:
            print(
                f"WARNING: stale_trait_task_types contains live trait-routed "
                f"task_types {sorted(overlap)!r}. Remove them from "
                f"{FITNESS_CONFIG_NAME} or fitness scoring will be suppressed.",
                file=sys.stderr,
            )
    except (OSError, json.JSONDecodeError):
        return  # config unreadable / malformed - non-fatal, skip


def recalc_trait(events, cfg, root=None):
    """Recalculate trait fitness scores."""
    if root is not None:
        _warn_if_stale_skiplist_collides_with_live_config(root, cfg)
    trait_defaults = cfg["trait_defaults"]
    stale_types = set(cfg["stale_trait_task_types"])

    # Group by domain (task_type) + entity (trait combo). Entity is
    # normalized to lowercase so mixed-case producer output is not
    # double-counted as distinct combos by the EMA scorer.
    grouped = defaultdict(lambda: defaultdict(list))
    for e in events:
        if e.get("system") != "trait":
            continue
        domain = e.get("domain", "_default")
        # Skip orphan task_types that no longer have a matching live entry.
        if domain in stale_types:
            continue
        entity = e.get("entity", "").lower()
        grouped[domain][entity].append(outcome_to_score(e.get("outcome", "neutral")))

    scores = {}
    for task_type, combos in grouped.items():
        scores[task_type] = {}
        for combo, values in combos.items():
            windowed = values[-cfg["window_size"]:]
            ema = compute_ema(windowed, cfg)
            default = trait_defaults.get(task_type, {}).get(combo, 0.5)
            blended = cold_start_blend(ema, default, len(windowed), cfg)
            scores[task_type][combo] = apply_ratchet_floor(blended, len(windowed), cfg)

    # Ensure all configured default task types appear
    for task_type, default_combos in trait_defaults.items():
        if not isinstance(default_combos, dict):
            continue
        if task_type not in scores:
            scores[task_type] = dict(default_combos)
        else:
            for combo, default_score in default_combos.items():
                if combo not in scores[task_type]:
                    scores[task_type][combo] = default_score

    return {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": cfg["window_size"],
        "scores": scores,
        **_ema_meta(cfg),
    }


# ---------------------------------------------------------------------------
# Delegation system
# ---------------------------------------------------------------------------

def recalc_delegation(events, cfg):
    """
    Recalculate delegation fitness scores.

    Mirrors the trait pattern but groups by (task_type, entity). Each
    delegation event is shaped:

        {
          "ts": "...",
          "system": "delegation",
          "entity": "<task_type or agent name>",
          "domain": "<task_type>",
          "outcome": "positive|negative|neutral",
          "details": {"was_delegated": bool, "score": float,
                      "threshold": float, "session": "..."}
        }

    Includes prediction_delta per task_type (the "backward signal"):
    the fraction of events whose outcome matches expectation
    (was_delegated AND positive outcome, OR not was_delegated AND
    non-positive outcome). When details are insufficient, falls back to
    a neutral 0.5 so downstream tuning does not penalise on cold-start.

    Canonical filtering (single point of sanitization is
    scripts/lib/delegation_outcomes):
      - skip system != delegation
      - skip quarantined rows (data-quality annotation)
      - schema-validate was_delegated via lib._is_valid_was_delegated
    """
    grouped = defaultdict(lambda: defaultdict(list))  # task_type -> entity -> [scores]
    raw_outcomes = defaultdict(list)  # task_type -> [(was_delegated, outcome_score)]

    for e in events:
        if e.get("system") != "delegation":
            continue
        if is_quarantined(e):
            continue
        # Defensive details-dict guard: a non-dict truthy `details` (producer
        # drift) must not crash the read; pre-bind the dict-or-empty value.
        raw_details = e.get("details")
        details_d = raw_details if isinstance(raw_details, dict) else {}
        wd = details_d.get("was_delegated")
        if not _is_valid_was_delegated(wd):
            continue
        domain = e.get("domain", "_default")
        entity = e.get("entity", "_default")
        score = outcome_to_score(e.get("outcome", "neutral"))
        grouped[domain][entity].append(score)
        if wd is not None:
            raw_outcomes[domain].append((bool(wd), score))

    scores = {}
    prediction_deltas = {}

    for task_type, combos in grouped.items():
        scores[task_type] = {}
        for combo, values in combos.items():
            windowed = values[-cfg["window_size"]:]
            ema = compute_ema(windowed, cfg)
            blended = cold_start_blend(ema, 0.5, len(windowed), cfg)
            scores[task_type][combo] = apply_ratchet_floor(blended, len(windowed), cfg)

        # prediction_delta: fraction of events where outcome aligned with
        # the delegation decision. was_delegated=True + positive (sc>=0.5)
        # OR was_delegated=False + non-positive (sc<=0.5; neutral counts
        # because not delegating + neutral outcome is consistent evidence
        # the decision was reasonable).
        outcomes = raw_outcomes.get(task_type, [])
        if outcomes:
            matched = sum(
                1 for was_d, sc in outcomes
                if (was_d and sc >= 0.5) or (not was_d and sc <= 0.5)
            )
            prediction_deltas[task_type] = round(matched / len(outcomes), 4)
        else:
            # Counterfactual data may not exist; fall back to neutral 0.5 so
            # downstream tuning does not penalise on cold-start.
            prediction_deltas[task_type] = 0.5

    return {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": cfg["window_size"],
        "alpha": cfg["ema_alpha"],
        **_ema_meta(cfg),
        "scores": scores,
        "prediction_delta": prediction_deltas,
        "schema_version": "1.0",
        "notes": ("prediction_delta = fraction of events whose outcome "
                  "aligned with the delegation decision; 0.5 neutral when "
                  "details.was_delegated absent."),
    }


# ---------------------------------------------------------------------------
# IO + CLI
# ---------------------------------------------------------------------------

def write_cache(path: Path, data) -> None:
    """Atomic locked write via the shared cache_writer (same-dir tempfile +
    os.replace; LOCK_EX serializes concurrent writers)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, data, lock=True)


def log_invocation(ledger_path: Path, record) -> None:
    """Append one JSON line to the invocation ledger. Fail-open: never raise."""
    try:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception as exc:
        print(f"WARNING: failed to append invocation ledger: {exc}", file=sys.stderr)


def _arg_value(argv, flag):
    if flag in argv:
        idx = argv.index(flag)
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return None


def main():
    start = time.monotonic()
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    events = []  # initialized before try so exception handler can read len(events)

    root = plugin_root()
    ledger_path = root / "_memory" / "analytics" / "cognitive-fitness.jsonl"
    cache_dir = root / "_graph" / "cache"
    invocation_ledger = root / "_ledgers" / "recalc-fitness-invocations.jsonl"

    dry_run = "--dry-run" in sys.argv
    system_filter = _arg_value(sys.argv, "--system")
    trigger = (_arg_value(sys.argv, "--trigger")
               or os.environ.get("RECALC_FITNESS_TRIGGER", "cli"))

    if system_filter is not None and system_filter not in ("lens", "trait", "delegation"):
        print(f"ERROR: Unknown system '{system_filter}'. Use: lens, trait, delegation",
              file=sys.stderr)
        log_invocation(invocation_ledger, {
            "ts": started_at,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "events_read": 0,
            "systems_requested": [system_filter],
            "dry_run": dry_run,
            "outputs_written": [],
            "success": False,
            "error": f"unknown_system:{system_filter}",
            "trigger": trigger,
        })
        sys.exit(1)

    try:
        cfg = load_config(root)
        events = read_ledger(ledger_path)
        print(f"Read {len(events)} events from ledger", file=sys.stderr)

        results = {}
        if system_filter is None or system_filter == "lens":
            results["lens"] = recalc_lens(events, cfg)
        if system_filter is None or system_filter == "trait":
            results["trait"] = recalc_trait(events, cfg, root=root)
        if system_filter is None or system_filter == "delegation":
            results["delegation"] = recalc_delegation(events, cfg)

        if dry_run:
            print(json.dumps(results, indent=2))
            log_invocation(invocation_ledger, {
                "ts": started_at,
                "duration_ms": round((time.monotonic() - start) * 1000, 3),
                "events_read": len(events),
                "systems_requested": list(results.keys()),
                "dry_run": True,
                "outputs_written": [],
                "success": True,
                "error": None,
                "trigger": trigger,
            })
            return

        file_map = {
            "lens": cache_dir / "lens-fitness.json",
            "trait": cache_dir / "trait-fitness.json",
            "delegation": cache_dir / "delegation-fitness.json",
        }

        outputs_written = []
        for system, data in results.items():
            path = file_map[system]
            write_cache(path, data)
            try:
                outputs_written.append(str(path.relative_to(root)))
            except ValueError:
                outputs_written.append(str(path))  # cache resolved outside root
            print(f"Written: {path}", file=sys.stderr)

        print(f"Recalculation complete: {len(results)} cache(s) updated",
              file=sys.stderr)

        log_invocation(invocation_ledger, {
            "ts": started_at,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "events_read": len(events),
            "systems_requested": list(results.keys()),
            "dry_run": False,
            "outputs_written": outputs_written,
            "success": True,
            "error": None,
            "trigger": trigger,
        })
    except Exception as exc:
        log_invocation(invocation_ledger, {
            "ts": started_at,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "events_read": len(events),
            "systems_requested": [system_filter] if system_filter
                                 else ["lens", "trait", "delegation"],
            "dry_run": dry_run,
            "outputs_written": [],
            "success": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "trigger": trigger,
        })
        raise


if __name__ == "__main__":
    main()
