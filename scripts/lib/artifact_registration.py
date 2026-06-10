"""Artifact Registration Framework (ARS).

Universal classifier + handler-dispatcher for the
artifact-registration-enforcer hook and backfill use.

Design:
  - Synchronous registration (full chain runs in low double-digit ms,
    well inside the hook's 2s hard timeout).
  - knowledge-nodes.json writes use the locked in-place RMW discipline
    (see lib/locked_json_rmw.py) so concurrent sessions cannot lose appends.
  - context-router.json and detection-index.json writes go through
    locked_write_remerge (read-fresh-under-lock, mutate, write in place).
  - Kairn writes are QUEUED to _inbox/artifact-registration-queue.jsonl for
    drainer pickup (the drainer calls the `kairn` CLI; absent binary = the
    queue simply accumulates until Kairn is installed).

Targets:
  - Kairn (via queue -> drainer)
  - _graph/knowledge-nodes.json (semantic node upsert)
  - _graph/cache/context-router.json (rule/skill/command/agent only)
  - _graph/cache/detection-index.json (command/skill only)
  - _ledgers/artifact-registration-{latency,failures}.jsonl (observability)

Classification rules are CONFIG-LOADED: if
_graph/cache/ars-classify-rules.json exists it overrides the built-in
default rules (which match this plugin's directory layout). Projects with a
different layout supply their own rules file instead of editing code.

Public API:
  - classify(path) -> ArtifactType | None
  - is_in_scope(path) -> bool
  - compute_node_id(path) / compute_semantic_node_id(path, type)
  - dispatch(path, mode="apply") -> RegistrationResult
  - handle(path, ...) -> alias for dispatch

Fail-open: all I/O wrapped; partial failures recorded in the failures
ledger but never raised to the caller. The hook must remain non-blocking.
"""

from __future__ import annotations

import hashlib
import json
import re
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from lib.locked_json_rmw import locked_rmw_json, locked_write_remerge
    from lib.plugin_paths import plugin_root
except ImportError:  # same-dir import path (scripts/lib on sys.path)
    from locked_json_rmw import locked_rmw_json, locked_write_remerge
    from plugin_paths import plugin_root

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = plugin_root()

ROUTER_FILE = REPO_ROOT / "_graph" / "cache" / "context-router.json"
DETECTION_FILE = REPO_ROOT / "_graph" / "cache" / "detection-index.json"
KNOWLEDGE_NODES_FILE = REPO_ROOT / "_graph" / "knowledge-nodes.json"
KAIRN_QUEUE = REPO_ROOT / "_inbox" / "artifact-registration-queue.jsonl"
LATENCY_LEDGER = REPO_ROOT / "_ledgers" / "artifact-registration-latency.jsonl"
FAILURES_LEDGER = REPO_ROOT / "_ledgers" / "artifact-registration-failures.jsonl"
CLASSIFY_RULES_FILE = REPO_ROOT / "_graph" / "cache" / "ars-classify-rules.json"

# Recursion guard env var (backfill sets this so the hook skips re-dispatch)
RECURSION_GUARD_ENV = "CLAUDE_ARTIFACT_BACKFILL_RUNNING"

PROVENANCE_TAG = "artifact-registration-enforcer"
BACKFILL_PROVENANCE_TAG = "auto-backfill"


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ArtifactType = str

VALID_TYPES: Tuple[str, ...] = (
    "hook", "rule", "agent", "command", "skill", "ledger", "handoff",
    "decision", "plan", "reference", "knowledge_doc", "script",
)

# Types with live auto-write handlers.
MVP_TYPES: Tuple[str, ...] = (
    "ledger", "handoff", "reference", "knowledge_doc", "plan",
    "command", "skill", "rule", "hook", "script", "agent",
)

# Router/Detection are selective; Kairn + knowledge_nodes are universal.
TARGETS_BY_TYPE: Dict[str, Tuple[str, ...]] = {
    "hook":          ("kairn", "knowledge_nodes"),
    "rule":          ("kairn", "router", "knowledge_nodes"),
    "agent":         ("kairn", "router", "knowledge_nodes"),
    "command":       ("kairn", "router", "detection", "knowledge_nodes"),
    "skill":         ("kairn", "router", "detection", "knowledge_nodes"),
    "ledger":        ("kairn", "knowledge_nodes"),
    "handoff":       ("kairn", "knowledge_nodes"),
    "reference":     ("kairn", "knowledge_nodes"),
    "knowledge_doc": ("kairn", "knowledge_nodes"),
    "plan":          ("kairn", "knowledge_nodes"),
    "decision":      (),   # default-skip (pipeline outputs, not curated docs)
    "script":        ("kairn", "knowledge_nodes"),
}

_SEMANTIC_PREFIX: Dict[str, str] = {
    "hook": "hook", "rule": "rule", "agent": "agent", "command": "command",
    "skill": "skill", "ledger": "ledger", "handoff": "handoff",
    "plan": "plan", "reference": "ref", "knowledge_doc": "knowledge-doc",
    "script": "script",
}


@dataclass
class RegistrationResult:
    path: str
    artifact_type: Optional[str]
    in_scope: bool
    mode: str  # "apply" | "observe"
    duration_ms: float = 0.0
    targets_attempted: List[str] = field(default_factory=list)
    targets_ok: List[str] = field(default_factory=list)
    targets_failed: List[Tuple[str, str]] = field(default_factory=list)
    skipped_reason: Optional[str] = None
    idempotent_skip: bool = False
    session: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": time.time(),
            "session": self.session,
            "path": self.path,
            "type": self.artifact_type,
            "in_scope": self.in_scope,
            "mode": self.mode,
            "duration_ms": round(self.duration_ms, 3),
            "targets_attempted": list(self.targets_attempted),
            "targets_ok": list(self.targets_ok),
            "targets_failed": [{"target": t, "error": e} for (t, e) in self.targets_failed],
            "skipped_reason": self.skipped_reason,
            "idempotent_skip": self.idempotent_skip,
        }


# ---------------------------------------------------------------------------
# Classification + scope
# ---------------------------------------------------------------------------

_DENY_PATTERNS: Tuple[re.Pattern[str], ...] = tuple(
    re.compile(p) for p in (
        r"(^|/)\.git(/|$)",
        r"(^|/)node_modules(/|$)",
        r"(^|/)_archive(/|$)",
        r"(^|/)__pycache__(/|$)",
        r"\.pyc$", r"\.tmp$", r"\.bak$", r"\.lock$", r"\.swp$",
        r"\.DS_Store$",
        r"^_handoffs/archive/",
    )
)

# Built-in classification rules matching THIS plugin's directory layout.
# First match wins. Override via _graph/cache/ars-classify-rules.json:
#   {"rules": [{"pattern": "^my/hooks/.+\\.py$", "type": "hook"}, ...]}
_DEFAULT_CLASSIFY_RULES: Tuple[Tuple[str, str], ...] = (
    (r"^hooks/scripts/[^/]+\.py$", "hook"),
    (r"^knowledge/rules/.+\.md$", "rule"),
    (r"^agents/.+\.md$", "agent"),
    (r"^commands/.+\.md$", "command"),
    (r"^skills/.+(/SKILL\.md|\.md)$", "skill"),
    (r"^_ledgers/[^/]+\.md$", "ledger"),
    (r"^_handoffs/(?!archive/)[^/]+\.md$", "handoff"),
    (r"^knowledge/decisions/.+\.md$", "decision"),
    (r"^knowledge/plans/.+\.md$", "plan"),
    (r"^docs/.+\.md$", "reference"),
    (r"^knowledge/(patterns|learnings)/.+\.md$", "knowledge_doc"),
    (r"^scripts/.+\.py$", "script"),
)


def _load_classify_rules() -> Tuple[Tuple[re.Pattern[str], str], ...]:
    """Compile classification rules, preferring the config file when valid."""
    raw_rules: List[Tuple[str, str]] = []
    try:
        if CLASSIFY_RULES_FILE.exists():
            data = json.loads(CLASSIFY_RULES_FILE.read_text(encoding="utf-8"))
            for entry in data.get("rules", []):
                pat, typ = entry.get("pattern"), entry.get("type")
                if isinstance(pat, str) and typ in VALID_TYPES:
                    raw_rules.append((pat, typ))
    except (OSError, json.JSONDecodeError, AttributeError):
        raw_rules = []
    if not raw_rules:
        raw_rules = list(_DEFAULT_CLASSIFY_RULES)
    compiled: List[Tuple[re.Pattern[str], str]] = []
    for pat, typ in raw_rules:
        try:
            compiled.append((re.compile(pat), typ))
        except re.error:
            continue
    return tuple(compiled)


_CLASSIFY_RULES = _load_classify_rules()


def _normalize_path(path: str) -> str:
    """Convert absolute paths to repo-relative; strip leading ./."""
    p = path.strip()
    if p.startswith(str(REPO_ROOT) + "/"):
        p = p[len(str(REPO_ROOT)) + 1:]
    if p.startswith("./"):
        p = p[2:]
    return p


def is_in_scope(path: str) -> bool:
    """True if path is NOT in deny list."""
    rel = _normalize_path(path)
    for deny in _DENY_PATTERNS:
        if deny.search(rel):
            return False
    return True


def classify(path: str) -> Optional[ArtifactType]:
    """Return artifact type or None if path not classifiable."""
    if not is_in_scope(path):
        return None
    rel = _normalize_path(path)
    for pattern, comp_type in _CLASSIFY_RULES:
        if pattern.match(rel):
            return comp_type
    return None


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


def compute_node_id(path: str) -> str:
    """Deterministic node id from path. SHA-256(path)[:12]."""
    rel = _normalize_path(path)
    return hashlib.sha256(rel.encode("utf-8")).hexdigest()[:12]


def compute_semantic_node_id(path: str, comp_type: str) -> str:
    """Semantic node id: <type-prefix>-<filename-stem-lower>."""
    rel = _normalize_path(path)
    prefix = _SEMANTIC_PREFIX.get(comp_type)
    if not prefix:
        return f"artifact-{compute_node_id(path)}"
    stem = Path(rel).stem
    return f"{prefix}-{stem.lower()}"


def compute_kairn_name(path: str, artifact_type: str) -> str:
    """Naming convention for Kairn nodes: '<Type>: <filename-without-ext>'."""
    rel = _normalize_path(path)
    return f"{artifact_type.title()}: {Path(rel).stem}"


def extract_title(path: str) -> Optional[str]:
    """Best-effort: first H1 in markdown, or None for non-markdown.

    Path-traversal guard: resolve and verify the path stays within
    REPO_ROOT before opening.
    """
    rel = _normalize_path(path)
    abs_path = REPO_ROOT / rel
    try:
        if not abs_path.resolve().is_relative_to(REPO_ROOT.resolve()):
            return None
    except (OSError, ValueError):
        return None
    if not abs_path.exists() or abs_path.is_dir():
        return None
    if abs_path.suffix.lower() != ".md":
        return None
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            for _ in range(50):
                line = f.readline()
                if not line:
                    break
                if line.startswith("# "):
                    return line[2:].strip()
    except OSError:
        return None
    return None


# ---------------------------------------------------------------------------
# Target writers
# ---------------------------------------------------------------------------


def _append_jsonl(path: Path, entry: Dict[str, Any]) -> None:
    """Append a single JSON object as a line. Best-effort."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _sanitize_for_fts5(text: str) -> str:
    """Strip tokens that start with a digit (FTS5 treats leading-digit
    tokens as column refs -> 'no such column' errors on later queries)."""
    return " ".join(
        tok for tok in text.split() if not (tok and tok[0].isdigit())
    ).strip()


def enqueue_kairn_add(
    path: str,
    artifact_type: str,
    title: Optional[str],
    tags: Optional[List[str]] = None,
    backfill: bool = False,
) -> bool:
    """Append a Kairn-add request to the artifact-registration queue.

    The actual `kairn add` call is performed by a drainer; without Kairn
    installed the queue simply accumulates (harmless, replayable).
    """
    rel = _normalize_path(path)
    tags_list = list(tags or [])
    tags_list.append(artifact_type)
    if backfill:
        tags_list.append(BACKFILL_PROVENANCE_TAG)
    entry = {
        "ts": time.time(),
        "kind": "kairn_add",
        "path": rel,
        "node_id": compute_node_id(path),
        "kn_add": {
            "name": compute_kairn_name(path, artifact_type),
            "type": "doc",
            "description": title or compute_kairn_name(path, artifact_type),
            "tags": tags_list,
            "namespace": "knowledge",
        },
        "provenance": BACKFILL_PROVENANCE_TAG if backfill else PROVENANCE_TAG,
    }
    _append_jsonl(KAIRN_QUEUE, entry)
    return True


def upsert_router_route(route_name: str, keywords: List[str], refs: List[str]) -> bool:
    """Add or merge a route into context-router.json. Idempotent on route_name.

    Writes via locked_write_remerge (read-fresh-under-lock, in-place) -
    context-router.json is a multi-writer target across concurrent sessions.
    Curated routes using the human-edited `primary_nodes` key are never
    touched; this writer manages node-id `primary`/`secondary` keys only.
    """
    if not ROUTER_FILE.exists():
        return False

    def _apply(data: Any) -> bool:
        routes = data.get("routes") if isinstance(data, dict) else None
        if not isinstance(routes, dict):
            return False
        existing = routes.get(route_name)
        if isinstance(existing, dict):
            merged_kw = list(existing.get("keywords") or [])
            for k in keywords:
                if k not in merged_kw:
                    merged_kw.append(k)
            merged_primary = list(existing.get("primary") or [])
            for r in refs:
                if r not in merged_primary:
                    merged_primary.append(r)
            if (merged_kw == existing.get("keywords")
                    and merged_primary == existing.get("primary")):
                return False  # idempotent skip
            existing["keywords"] = merged_kw
            existing["primary"] = merged_primary
            existing.setdefault("created_by", PROVENANCE_TAG)
        else:
            routes[route_name] = {
                "keywords": list(keywords),
                "primary": list(refs),
                "secondary": [],
                "created_by": PROVENANCE_TAG,
                "created_at": time.time(),
            }
        return True

    return locked_write_remerge(ROUTER_FILE, _apply, acquire_timeout_s=0.5)


def upsert_detection_entry(
    key: str,
    keywords: List[str],
    patterns: Optional[List[str]] = None,
    confidence_boost: int = 10,
    artifact_type: str = "command",
    preserve_existing: bool = True,
) -> bool:
    """Add or merge a detection-index entry. Idempotent on entry name.

    Schema: {"entries": {name: {"keywords": [...], "command": "/name",
    "confidence_boost": int}}}.

    Curation-safety: with preserve_existing=True (default) this is strict
    insert-only - an existing entry is left untouched so hand-curated
    keywords/confidence are never downgraded by auto-generated defaults.
    """
    if not DETECTION_FILE.exists():
        return False
    name = key.lstrip("/")

    def _apply(data: Any) -> bool:
        if not isinstance(data, dict):
            return False
        entries = data.get("entries")
        if not isinstance(entries, dict):
            entries = {}
            data["entries"] = entries
        existing = entries.get(name)
        if isinstance(existing, dict):
            if preserve_existing:
                return False
            merged_kw = list(existing.get("keywords") or [])
            for k in keywords:
                if k not in merged_kw:
                    merged_kw.append(k)
            if merged_kw == existing.get("keywords"):
                return False
            existing["keywords"] = merged_kw
            return True
        entries[name] = {
            "keywords": list(keywords),
            "command": f"/{name}" if artifact_type == "command" else name,
            "confidence_boost": confidence_boost,
            "type": artifact_type,
            "created_by": PROVENANCE_TAG,
        }
        return True

    return locked_write_remerge(DETECTION_FILE, _apply, acquire_timeout_s=0.5)


def upsert_knowledge_node(
    path: str,
    artifact_type: str,
    title: Optional[str],
    backfill: bool = False,
) -> bool:
    """Add a knowledge-graph node to _graph/knowledge-nodes.json.

    Idempotent on (id). The read + idempotency-check + append run UNDER the
    exclusive lock, closing both races on this file: lost-append (two
    concurrent inode-swap writers) and duplicate-insert (two writers both
    missing the id on a stale read).
    """
    if not KNOWLEDGE_NODES_FILE.exists():
        return False

    node_id = compute_semantic_node_id(path, artifact_type)
    rel = _normalize_path(path)

    import datetime as _dt
    now_iso = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stem = Path(rel).stem

    new_node = {
        "id": node_id,
        "type": artifact_type,
        "name": title or stem,
        "source_path": rel,
        "description": title or stem,
        "created_at": now_iso,
        "created_session": "ars-backfill" if backfill else "ars-auto",
        "provenance": BACKFILL_PROVENANCE_TAG if backfill else "auto-ars",
    }

    def _mutate(data: Any) -> Tuple[Any, bool]:
        if not isinstance(data, dict):
            return data, False
        nodes = data.get("nodes")
        if not isinstance(nodes, list):
            return data, False
        for n in nodes:
            if isinstance(n, dict) and n.get("id") == node_id:
                return data, False  # idempotent: already present
        nodes.append(new_node)
        return data, True

    # Bounded lock wait leaves ample headroom under the hook's 2s SIGALRM.
    # On contention timeout LockTimeout (a TimeoutError) propagates to the
    # dispatcher's per-target try/except: fail-open, re-registers next Write.
    try:
        return locked_rmw_json(
            KNOWLEDGE_NODES_FILE, _mutate, acquire_timeout_s=0.5
        )
    except json.JSONDecodeError as e:
        raise RuntimeError(f"knowledge-nodes.json read failed: {e}") from e


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def dispatch(
    path: str,
    mode: str = "apply",
    backfill: bool = False,
    write_ledger: bool = True,
    session_id: Optional[str] = None,
) -> RegistrationResult:
    """Classify path and dispatch to the registration targets.

    Never raises (fail-open). All errors recorded in result.targets_failed.
    """
    t0 = time.perf_counter()
    _resolved_session: Optional[str] = session_id
    if _resolved_session is None:
        try:
            try:
                from lib.session_attribution import resolve_session_id as _rsi
            except ImportError:
                from session_attribution import resolve_session_id as _rsi
            _resolved_session = _rsi()
        except Exception:
            _resolved_session = None
    result = RegistrationResult(
        path=_normalize_path(path),
        artifact_type=None,
        in_scope=is_in_scope(path),
        mode=mode,
        session=_resolved_session,
    )

    if os.environ.get(RECURSION_GUARD_ENV) == "1" and not backfill:
        result.skipped_reason = "recursion_guard"
        result.duration_ms = (time.perf_counter() - t0) * 1000
        if write_ledger:
            _append_jsonl_safe(LATENCY_LEDGER, result.to_dict())
        return result

    if not result.in_scope:
        result.skipped_reason = "deny_list"
        result.duration_ms = (time.perf_counter() - t0) * 1000
        if write_ledger:
            _append_jsonl_safe(LATENCY_LEDGER, result.to_dict())
        return result

    comp_type = classify(path)
    result.artifact_type = comp_type
    if comp_type is None:
        result.skipped_reason = "unclassified"
        result.duration_ms = (time.perf_counter() - t0) * 1000
        if write_ledger:
            _append_jsonl_safe(LATENCY_LEDGER, result.to_dict())
        return result

    if comp_type not in MVP_TYPES:
        result.skipped_reason = "non_mvp_type_stub"
        result.targets_attempted = list(TARGETS_BY_TYPE.get(comp_type, ()))
        result.duration_ms = (time.perf_counter() - t0) * 1000
        if write_ledger:
            _append_jsonl_safe(LATENCY_LEDGER, result.to_dict())
        return result

    targets = TARGETS_BY_TYPE.get(comp_type, ())
    result.targets_attempted = list(targets)

    if mode == "observe":
        result.duration_ms = (time.perf_counter() - t0) * 1000
        if write_ledger:
            _append_jsonl_safe(LATENCY_LEDGER, result.to_dict())
        return result

    # APPLY mode: walk targets
    title = extract_title(path)

    if "kairn" in targets:
        try:
            enqueue_kairn_add(path, comp_type, title, tags=None, backfill=backfill)
            result.targets_ok.append("kairn")
        except Exception as e:
            result.targets_failed.append(("kairn", _safe_str(e)))

    if "router" in targets:
        try:
            inserted = upsert_router_route(
                route_name=_derive_route_name(path, comp_type),
                keywords=_derive_keywords(path, comp_type, title),
                # Route primary points at the SEMANTIC node id - the same id
                # upsert_knowledge_node creates - so the route resolves to a
                # real node instead of a dangling hash id.
                refs=[compute_semantic_node_id(path, comp_type)],
            )
            result.targets_ok.append("router" if inserted else "router:idempotent")
        except Exception as e:
            result.targets_failed.append(("router", _safe_str(e)))

    if "detection" in targets:
        try:
            inserted = upsert_detection_entry(
                key=_derive_detection_key(path, comp_type),
                keywords=_derive_keywords(path, comp_type, title),
                artifact_type=comp_type,
            )
            result.targets_ok.append("detection" if inserted else "detection:idempotent")
        except Exception as e:
            result.targets_failed.append(("detection", _safe_str(e)))

    if "knowledge_nodes" in targets:
        try:
            inserted = upsert_knowledge_node(
                path=path, artifact_type=comp_type, title=title, backfill=backfill,
            )
            result.targets_ok.append(
                "knowledge_nodes" if inserted else "knowledge_nodes:idempotent"
            )
        except Exception as e:
            result.targets_failed.append(("knowledge_nodes", _safe_str(e)))

    result.duration_ms = (time.perf_counter() - t0) * 1000

    if result.targets_failed:
        _append_jsonl_safe(FAILURES_LEDGER, {
            "ts": time.time(),
            "path": result.path,
            "type": comp_type,
            "failures": [{"target": t, "error": e} for (t, e) in result.targets_failed],
        })
    if write_ledger:
        _append_jsonl_safe(LATENCY_LEDGER, result.to_dict())

    return result


def handle(
    path: str,
    mode: str = "apply",
    backfill: bool = False,
    write_ledger: bool = True,
    session_id: Optional[str] = None,
) -> RegistrationResult:
    """Public alias for dispatch() with full pass-through."""
    return dispatch(path, mode=mode, backfill=backfill,
                    write_ledger=write_ledger, session_id=session_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_keywords(path: str, comp_type: str, title: Optional[str]) -> List[str]:
    """Naive keyword extraction: filename stem + H1 tokens. No NLP."""
    rel = _normalize_path(path)
    stem = Path(rel).stem
    kws: List[str] = [comp_type]
    _MIN_KW_LEN, _MAX_KW_LEN = 3, 30
    for tok in re.split(r"[-_.]+", stem):
        tok_l = tok.lower().strip()
        if _MIN_KW_LEN <= len(tok_l) <= _MAX_KW_LEN and not tok_l.isdigit():
            kws.append(tok_l)
    if title:
        for tok in re.split(r"[\s\-_:.]+", _sanitize_for_fts5(title)):
            tok_l = tok.lower().strip()
            if _MIN_KW_LEN <= len(tok_l) <= _MAX_KW_LEN and not tok_l.isdigit():
                if tok_l not in kws:
                    kws.append(tok_l)
    return kws[:10]


def _derive_detection_key(path: str, comp_type: str) -> str:
    rel = _normalize_path(path)
    stem = Path(rel).stem
    return f"/{stem}" if comp_type == "command" else stem


def _derive_route_name(path: str, comp_type: str) -> str:
    """Unique router key including source-tree prefix, so same-stem files in
    different trees do not silently merge under one route key."""
    rel = _normalize_path(path)
    prefix = rel.split("/", 1)[0].lstrip(".").replace(".", "_").replace("-", "_") or "root"
    return f"auto-{comp_type}-{prefix}-{Path(rel).stem}"


def _safe_str(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:300]


def _append_jsonl_safe(path: Path, entry: Dict[str, Any]) -> None:
    """Observability must never break dispatch."""
    try:
        _append_jsonl(path, entry)
    except Exception:
        pass
