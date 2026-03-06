"""
CodeGen Error Memory — Persistent learning from pipeline mistakes.

Records every bug caught during code generation, review, testing, and fixing.
On future runs, injects the top lessons into LLM prompts so the same
mistakes are not repeated.

Storage: a single JSONL file (one JSON object per line) at
    data/memory/codegen_errors.jsonl

Each entry:
    {
        "timestamp": "2026-02-26T09:12:47",
        "run_id": "build_a_local_password_manager_001",
        "idea_summary": "local password manager ...",
        "phase": "code_review" | "static_check" | "runtime_test" | "fix_loop",
        "bug_type": "API_MISMATCH" | "SELF_METHOD_MISSING" | ...,
        "file": "main.py",
        "line": 164,
        "description": "self._save_metadata() called but method is _write_metadata()",
        "fix_applied": "Renamed call to self._write_metadata(self._metadata)",
        "fixed": true
    }

Query API:
    memory = CodegenErrorMemory()
    lessons = memory.get_top_lessons(n=15)
    # Returns a formatted string ready to paste into an LLM prompt
"""

from __future__ import annotations

import json
import pathlib
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("codegen_error_memory")

_DEFAULT_PATH = pathlib.Path("data/memory/codegen_errors.jsonl")


class CodegenErrorMemory:
    """Append-only ledger of code-generation mistakes + query helpers."""

    def __init__(self, path: Optional[pathlib.Path] = None):
        self.path = path or _DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #
    def record(
        self,
        run_id: str,
        idea_summary: str,
        phase: str,
        bug_type: str,
        file: str,
        description: str,
        fix_applied: str = "",
        fixed: bool = False,
        line: Optional[int] = None,
    ) -> None:
        """Append one error entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "idea_summary": idea_summary[:120],
            "phase": phase,
            "bug_type": bug_type,
            "file": file,
            "line": line,
            "description": description[:300],
            "fix_applied": fix_applied[:300],
            "fixed": fixed,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.debug("Recorded codegen error: %s in %s", bug_type, file)

    def record_batch(self, entries: List[Dict[str, Any]]) -> int:
        """Append multiple entries at once. Returns count written."""
        count = 0
        with self.path.open("a", encoding="utf-8") as f:
            for e in entries:
                e.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
                e["idea_summary"] = str(e.get("idea_summary", ""))[:120]
                e["description"] = str(e.get("description", ""))[:300]
                e["fix_applied"] = str(e.get("fix_applied", ""))[:300]
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
                count += 1
        logger.info("Recorded %d codegen errors in batch", count)
        return count

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    def _load_all(self) -> List[Dict[str, Any]]:
        """Load every entry (used internally)."""
        entries: List[Dict[str, Any]] = []
        if not self.path.exists():
            return entries
        _skipped = 0  # V18 FIX: track skipped lines
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                _skipped += 1
                continue
        if _skipped:
            logger.warning(f"Skipped {_skipped} malformed JSONL line(s) in error memory ({self.path})")
        return entries

    def get_top_lessons(self, n: int = 15) -> str:
        """
        Return a formatted string of the N most frequent bug patterns,
        ready to inject into an LLM prompt.

        Format:
            LESSONS FROM PAST RUNS (avoid these mistakes):
            1. [API_MISMATCH × 4] self.method() called but method doesn't exist — always verify method names against the actual class definition.
            2. [UNINITIALIZED_ATTR × 3] self.x used before assignment in __init__ — initialize all instance attributes in __init__ before calling any methods.
            ...
        """
        entries = self._load_all()
        if not entries:
            return ""

        # Group by (bug_type, description_key)
        # Use bug_type + first 80 chars of description as dedup key
        pattern_counter: Counter = Counter()
        pattern_examples: Dict[str, str] = {}  # key → best description

        for e in entries:
            bug_type = e.get("bug_type", "UNKNOWN")
            desc = e.get("description", "")
            # Normalise: strip line numbers, filenames for grouping
            key = f"{bug_type}::{desc[:80]}"
            pattern_counter[key] += 1
            # Keep the longest description as the example
            if key not in pattern_examples or len(desc) > len(pattern_examples[key]):
                pattern_examples[key] = desc

        if not pattern_counter:
            return ""

        lines = ["LESSONS FROM PAST RUNS (avoid these mistakes):"]
        for i, (key, count) in enumerate(pattern_counter.most_common(n), 1):
            bug_type = key.split("::")[0]
            desc = pattern_examples[key]
            lines.append(f"{i}. [{bug_type} × {count}] {desc}")

        return "\n".join(lines)

    def get_lessons_for_review(self, n: int = 10) -> str:
        """
        Return lessons formatted for the code review agent prompt.
        Focuses on bug types and what to look for.
        """
        entries = self._load_all()
        if not entries:
            return ""

        # Count bug types
        type_counter: Counter = Counter()
        type_examples: Dict[str, List[str]] = {}

        for e in entries:
            bt = e.get("bug_type", "UNKNOWN")
            type_counter[bt] += 1
            if bt not in type_examples:
                type_examples[bt] = []
            if len(type_examples[bt]) < 2:
                desc = e.get("description", "")
                if desc and desc not in type_examples[bt]:
                    type_examples[bt].append(desc[:150])

        if not type_counter:
            return ""

        lines = ["HISTORICALLY FREQUENT BUGS (pay extra attention to these):"]
        for bt, count in type_counter.most_common(n):
            examples = type_examples.get(bt, [])
            ex_str = " | ".join(examples) if examples else "no examples"
            lines.append(f"- {bt} (seen {count}× before): {ex_str}")

        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics."""
        entries = self._load_all()
        if not entries:
            return {"total": 0, "fixed": 0, "unfixed": 0, "top_types": {}}

        fixed = sum(1 for e in entries if e.get("fixed"))
        type_counter = Counter(e.get("bug_type", "UNKNOWN") for e in entries)

        return {
            "total": len(entries),
            "fixed": fixed,
            "unfixed": len(entries) - fixed,
            "fix_rate": f"{fixed / len(entries) * 100:.0f}%" if entries else "0%",
            "top_types": dict(type_counter.most_common(10)),
            "unique_runs": len(set(e.get("run_id", "") for e in entries)),
        }


# ------------------------------------------------------------------ #
# Module-level singleton
# ------------------------------------------------------------------ #
_instance: Optional[CodegenErrorMemory] = None


def get_error_memory() -> CodegenErrorMemory:
    """Get or create the singleton instance."""
    global _instance
    if _instance is None:
        _instance = CodegenErrorMemory()
    return _instance
