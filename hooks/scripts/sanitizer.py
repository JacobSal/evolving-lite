#!/usr/bin/env python3
"""
Agent Output Sanitizer - cross-session injection defense.

Scans sub-agent / persisted output for prompt-injection patterns before it is
written to memory. Tiered response keyed off a confidence score:
  score >= 0.8  -> quarantine
  score >= 0.4  -> redact (replace matched spans with [REDACTED: name])
  else          -> allow

Matches inside code fences / blockquotes are down-weighted (educational content
preserved). All 14 patterns are generic and pre-compiled at import.

Stdlib only. Importable API:  scan_content(text) -> SanitizationResult
"""

import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
try:
    from common import PLUGIN_ROOT  # noqa: E402
except Exception:  # pragma: no cover - fallback if run fully standalone
    PLUGIN_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class PatternMatch:
    pattern_name: str
    text_snippet: str
    position: int
    match_end: int
    in_code_fence: bool
    weight: float
    adjusted_weight: float


@dataclass
class SanitizationResult:
    clean: bool
    confidence: float
    action: str  # "allow" | "redact" | "quarantine"
    matches: list = field(default_factory=list)
    sanitized_content: str = ""
    original_length: int = 0


# 14 generic injection patterns (pre-compiled at module load).
_RAW_PATTERNS = [
    {"pattern": r"ignore\s+(?:(?:all|previous|prior)\s+)+instructions", "weight": 0.6, "name": "instruction_override"},
    {"pattern": r"disregard\s+(?:(?:all|previous|prior)\s+)+(?:instructions|rules|guidelines)?", "weight": 0.6, "name": "instruction_disregard"},
    {"pattern": r"forget\s+(?:(?:all|previous|prior|your)\s+)+instructions", "weight": 0.6, "name": "instruction_forget"},
    {"pattern": r"new\s+instructions:", "weight": 0.6, "name": "new_instructions"},
    {"pattern": r"system\s+prompt:", "weight": 0.5, "name": "system_prompt_extract"},
    {"pattern": r"you\s+are\s+now\s+a", "weight": 0.4, "name": "role_override"},
    {"pattern": r"act\s+as\s+if", "weight": 0.4, "name": "role_act_as"},
    {"pattern": r"pretend\s+you\s+are", "weight": 0.4, "name": "role_pretend"},
    {"pattern": r"jailbreak", "weight": 0.5, "name": "jailbreak"},
    {"pattern": r"<system>", "weight": 0.5, "name": "system_tag"},
    {"pattern": r"<\|im_start\|>system", "weight": 0.6, "name": "chatml_inject"},
    {"pattern": r"Human:\s*\n[^\n]{0,500}Assistant:", "weight": 0.4, "name": "conversation_inject"},
    {"pattern": r"IMPORTANT:\s*(?:ignore|override|disregard)", "weight": 0.5, "name": "important_override"},
    {"pattern": r"(?:base64|atob)\s*\([^\n]{0,200}[A-Za-z0-9+/=]{50,}", "weight": 0.4, "name": "encoded_payload"},
]

# IGNORECASE only - NOT DOTALL. None of these patterns need `.` to cross
# newlines, and global DOTALL + an unbounded `.*?` over 100KB of adversarial
# fetched content is a ReDoS surface. The two patterns that previously relied
# on DOTALL now use explicit, length-bounded character classes instead.
COMPILED_PATTERNS = []
for _p in _RAW_PATTERNS:
    try:
        COMPILED_PATTERNS.append({
            "regex": re.compile(_p["pattern"], re.IGNORECASE),
            "weight": _p["weight"],
            "name": _p["name"],
        })
    except re.error as _e:  # pragma: no cover
        print(f"WARNING: sanitizer pattern '{_p['name']}' failed to compile: {_e}", file=sys.stderr)

QUARANTINE_THRESHOLD = 0.8
REDACT_THRESHOLD = 0.4
MAX_LOG_LINES = 1000
KEEP_LOG_LINES = 500


def detect_code_fences(content: str) -> list:
    matches = list(re.compile(r"^(`{3,}|~{3,})", re.MULTILINE).finditer(content))
    fences, pending = [], {}
    for m in matches:
        delim = m.group(1)[0]
        if delim not in pending:
            pending[delim] = m
        else:
            fences.append((pending.pop(delim).start(), m.end()))
    return fences


def _in_code_fence(position: int, fences: list) -> bool:
    return any(start <= position <= end for start, end in fences)


def _in_markdown_quote(content: str, position: int) -> bool:
    line_start = content.rfind("\n", 0, position) + 1
    return content[line_start:position + 1].lstrip().startswith(">")


def scan_content(content: str) -> SanitizationResult:
    """Scan content for injection patterns; return score + recommended action."""
    original_length = len(content)
    if original_length < 20:
        return SanitizationResult(True, 0.0, "allow", [], content, original_length)

    fences = detect_code_fences(content)
    all_matches = []
    score = 0.0
    for pat in COMPILED_PATTERNS:
        for m in pat["regex"].finditer(content):
            is_fenced = _in_code_fence(m.start(), fences)
            is_quoted = _in_markdown_quote(content, m.start())
            weight = pat["weight"]
            if is_fenced:
                weight *= 0.3
            elif is_quoted:
                weight *= 0.5
            s, e = max(0, m.start() - 20), min(len(content), m.end() + 20)
            all_matches.append(PatternMatch(
                pattern_name=pat["name"],
                text_snippet=content[s:e].replace("\n", " "),
                position=m.start(),
                match_end=m.end(),
                in_code_fence=is_fenced,
                weight=pat["weight"],
                adjusted_weight=weight,
            ))
            score += weight

    if len(all_matches) >= 3:
        score *= 1.5
    score = min(score, 1.0)

    if score >= QUARANTINE_THRESHOLD:
        action = "quarantine"
    elif score >= REDACT_THRESHOLD:
        action = "redact"
    else:
        action = "allow"

    # quarantine MUST NOT pass the raw payload through sanitized_content - a
    # caller that surfaces the field without branching on action would otherwise
    # receive the verbatim hostile text.
    if action == "redact":
        sanitized = redact_matches(content, all_matches)
    elif action == "quarantine":
        sanitized = "[QUARANTINED: content withheld due to high-confidence injection]"
    else:
        sanitized = content
    return SanitizationResult(
        clean=len(all_matches) == 0,
        confidence=score,
        action=action,
        matches=[{
            "pattern_name": m.pattern_name,
            "text_snippet": m.text_snippet,
            "position": m.position,
            "in_code_fence": m.in_code_fence,
        } for m in all_matches],
        sanitized_content=sanitized,
        original_length=original_length,
    )


def redact_matches(content: str, matches: list) -> str:
    if not matches:
        return content
    replacements = [(m.position, m.match_end, f"[REDACTED: {m.pattern_name}]")
                    for m in matches if not m.in_code_fence]
    replacements.sort(key=lambda x: x[0], reverse=True)
    result = content
    for start, end, repl in replacements:
        result = result[:start] + repl + result[end:]
    conf = sum(m.adjusted_weight for m in matches)
    return f"[SANITIZED: {len(matches)} pattern(s) detected, confidence {conf:.2f}]\n\n{result}"


def _get_log_path() -> Path:
    security_dir = PLUGIN_ROOT / "_memory" / "security"
    try:
        security_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        fallback = Path.home() / ".claude" / "memory" / "security"
        try:
            fallback.mkdir(parents=True, exist_ok=True)
        except OSError as exc:  # pragma: no cover
            print(f"WARNING: cannot create log dir {fallback}: {exc}", file=sys.stderr)
        return fallback / "injection-attempts.jsonl"
    return security_dir / "injection-attempts.jsonl"


def log_detection(result: SanitizationResult, file_path: str = "") -> None:
    log_path = _get_log_path()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": result.action,
        "confidence": round(result.confidence, 3),
        "match_count": len(result.matches),
        "patterns": [m["pattern_name"] for m in result.matches],
        "file_path": str(file_path),
        "content_length": result.original_length,
    }
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        _rotate_log_if_needed(log_path)
    except OSError as exc:  # pragma: no cover
        print(f"WARNING: failed to log injection detection to {log_path}: {exc}", file=sys.stderr)


def _rotate_log_if_needed(log_path: Path) -> None:
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_LOG_LINES:
            fd, tmp_path = tempfile.mkstemp(dir=log_path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.writelines(lines[-KEEP_LOG_LINES:])
                os.replace(tmp_path, log_path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
    except OSError as exc:  # pragma: no cover
        print(f"WARNING: log rotation failed for {log_path}: {exc}", file=sys.stderr)
