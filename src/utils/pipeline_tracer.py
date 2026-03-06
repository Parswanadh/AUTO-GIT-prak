"""
Pipeline Tracer — Observability for Auto-GIT
============================================
Writes two files per run into logs/:

  pipeline_trace_<ts>.jsonl   — one JSON line per pipeline event (node start/end,
                                  full context snapshot, errors, token usage)
  agent_status_<ts>.md        — human-readable summary: which nodes ran, which
                                  models are alive/dead/timed-out, token totals

Usage (in workflow_enhanced.py):
    from src.utils.pipeline_tracer import PipelineTracer

    tracer = PipelineTracer(logs_dir="logs", idea=idea)
    ...
    # after each node yields in the astream loop:
    tracer.on_node_complete(node_name, node_state)
    ...
    # at the very end:
    tracer.finish(final_state)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── All pipeline nodes in execution order ─────────────────────────────────────
_ALL_NODES: List[str] = [
    "requirements_extraction",
    "research",
    "generate_perspectives",
    "problem_extraction",
    "solution_generation",
    "critique",
    "consensus_check",
    "solution_selection",
    "architect_spec",
    "code_generation",
    "code_review_agent",
    "code_testing",
    "strategy_reasoner",
    "code_fixing",
    "pipeline_self_eval",
    "git_publishing",
]


class PipelineTracer:
    """
    Lightweight tracer that records every node execution in JSONL format and
    produces a human-readable agent-status Markdown report at pipeline end.

    Thread-safe enough for the single-threaded async pipeline loop.
    """

    def __init__(self, logs_dir: str = "logs", idea: str = "", thread_id: str = "default"):
        self.idea = idea
        self.thread_id = thread_id
        self.ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(logs_dir, exist_ok=True)

        self.logs_dir    = logs_dir
        self.trace_path  = os.path.join(logs_dir, f"pipeline_trace_{self.ts}.jsonl")
        self.status_path = os.path.join(logs_dir, f"agent_status_{self.ts}.md")
        self.health_path = os.path.join(logs_dir, f"model_health_{self.ts}.json")
        self.ckpt_path   = os.path.join(logs_dir, f"checkpoint_{thread_id}.json")

        # Per-node tracking
        self._call_count:  Dict[str, int]   = {}   # node_name → total invocations
        self._last_event:  float            = time.time()    # timestamp of last event
        self._node_timings: Dict[str, List[float]] = {}  # node_name → list of durations (s)
        self._pipeline_start: float         = time.time()    # wall clock start

        # Accumulated full pipeline state (LangGraph yields only deltas per node)
        self._full_state:  Dict[str, Any]   = {"idea": idea}

        # Open trace file (kept open for the whole run, flushed per event)
        self._fh = open(self.trace_path, "w", encoding="utf-8")

        self._write({
            "event": "pipeline_start",
            "ts": datetime.now().isoformat(),
            "idea": idea[:200],
            "thread_id": thread_id,
        })

        print(f"\n📋 Pipeline trace → {self.trace_path}")
        print(f"🤖 Agent status  → {self.status_path}\n")

    # ── Public API ─────────────────────────────────────────────────────────────

    def on_node_complete(self, node_name: str, state: Dict[str, Any]) -> None:
        """
        Call once per `async for state in workflow.astream(...)` iteration after
        processing the state for *node_name*.

        LangGraph only yields the delta (fields changed by this node), so we
        merge into a running full-state copy before summarising.
        """
        # Merge this node's delta into the accumulated full state.
        # Never overwrite an existing list/dict with a scalar — some nodes
        # (e.g. consensus_check) store e.g. debate_rounds as an int count
        # while the actual list lives from an earlier node.
        for k, v in state.items():
            if v is None:
                continue
            existing = self._full_state.get(k)
            if isinstance(existing, (list, dict)) and not isinstance(v, (list, dict)):
                continue  # keep the richer type already in state
            self._full_state[k] = v

        # Increment call counter
        count = self._call_count.get(node_name, 0) + 1
        self._call_count[node_name] = count

        # Time since last event (approximate node duration)
        now = time.time()
        elapsed = round(now - self._last_event, 2)
        self._last_event = now
        # Accumulate per-node timing
        self._node_timings.setdefault(node_name, []).append(elapsed)

        errors = self._full_state.get("errors") or []
        if not isinstance(errors, list): errors = []

        try:
            context = self._summarise(node_name, self._full_state)
        except Exception as exc:
            context = {"summarise_error": str(exc), "stage": self._full_state.get("current_stage", "")}

        record = {
            "event":         "node_complete",
            "ts":            datetime.now().isoformat(),
            "node":          node_name,
            "call_num":      count,
            "elapsed_s":     elapsed,
            "current_stage": self._full_state.get("current_stage", ""),
            "context":       context,
            "errors_last3":  errors[-3:],
            "error_count":   len(errors),
        }
        self._write(record)
        # Save a JSON snapshot so humans can inspect pipeline state (and as a
        # readable complement to the LangGraph SQLite checkpoint).
        self.save_checkpoint(node_name)

    def save_checkpoint(self, last_node: str) -> None:
        """Write a human-readable JSON checkpoint of the full accumulated state.

        This is a *complement* to the LangGraph SqliteSaver checkpoint, not a
        replacement.  Useful for inspecting what state looks like at each node.
        """
        payload = {
            "ts": datetime.now().isoformat(),
            "thread_id": self.thread_id,
            "last_completed_node": last_node,
            "node_calls": dict(self._call_count),
            "full_state": self._full_state,
        }
        try:
            with open(self.ckpt_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, default=str, indent=2)
        except Exception:
            pass  # never crash the pipeline due to checkpointing

    @staticmethod
    def load_checkpoint(logs_dir: str, thread_id: str) -> Optional[Dict]:
        """Load the most recent JSON checkpoint for *thread_id*, or None."""
        path = os.path.join(logs_dir, f"checkpoint_{thread_id}.json")
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def finish(self, final_state: Optional[Dict[str, Any]]) -> None:
        """
        Call once when the pipeline ends (success or exception).
        Writes the closing JSONL event, then generates the Markdown report.
        """
        # Lazy-import to avoid circular dependency at module level
        try:
            from src.utils.model_manager import get_token_stats, get_model_health_report
            token_stats = get_token_stats()
            health      = get_model_health_report()
        except Exception as e:
            token_stats = {}
            health      = {"error": str(e)}

        # Merge final delta into accumulated state (if provided)
        if final_state:
            self._full_state.update({k: v for k, v in final_state.items() if v is not None})
        agg = self._full_state

        self._write({
            "event":        "pipeline_end",
            "ts":           datetime.now().isoformat(),
            "node_calls":   dict(self._call_count),
            "final_stage":  agg.get("current_stage", ""),
            "github_repo":  agg.get("github_repo", ""),
            "error_count":  len(agg.get("errors") or []),
            "files_generated": list((agg.get("generated_code") or {}).keys()),
            "token_stats":  token_stats,
        })
        self._fh.close()

        # Write model health JSON
        try:
            with open(self.health_path, "w", encoding="utf-8") as f:
                json.dump(health, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        # Write human-readable agent status Markdown
        self._write_status_md(token_stats, health)

        # Print per-node profiling summary
        self.print_profiling_summary()

        print(f"\n📋 Trace  saved → {self.trace_path}")
        print(f"⚕️  Health saved → {self.health_path}")
        print(f"🤖 Status saved → {self.status_path}")

    # ── Per-node profiling ────────────────────────────────────────────────────

    def get_profiling_data(self) -> Dict[str, Any]:
        """Return structured per-node profiling data."""
        total_wall = time.time() - self._pipeline_start
        data: Dict[str, Any] = {"total_wall_s": round(total_wall, 2), "nodes": {}}
        for node_name, durations in self._node_timings.items():
            total = sum(durations)
            data["nodes"][node_name] = {
                "calls": len(durations),
                "total_s": round(total, 2),
                "avg_s": round(total / len(durations), 2) if durations else 0,
                "max_s": round(max(durations), 2) if durations else 0,
                "pct_of_total": round(100.0 * total / total_wall, 1) if total_wall > 0 else 0,
            }
        return data

    def print_profiling_summary(self) -> None:
        """Print a formatted per-node profiling summary to stdout."""
        data = self.get_profiling_data()
        total_wall = data["total_wall_s"]
        nodes = data.get("nodes", {})
        if not nodes:
            return

        print("\n" + "═" * 60)
        print("  ⏱️  PER-NODE PROFILING SUMMARY")
        print("═" * 60)
        print(f"  {'Node':<25s} {'Calls':>5s} {'Total':>8s} {'Avg':>8s} {'Max':>8s} {'%':>6s}")
        print(f"  {'─'*25} {'─'*5} {'─'*8} {'─'*8} {'─'*8} {'─'*6}")

        # Sort by total time descending
        sorted_nodes = sorted(nodes.items(), key=lambda x: -x[1]["total_s"])
        for name, info in sorted_nodes:
            total_s = info["total_s"]
            avg_s = info["avg_s"]
            max_s = info["max_s"]
            pct = info["pct_of_total"]
            calls = info["calls"]
            # Format times nicely
            total_f = f"{total_s:.1f}s" if total_s < 60 else f"{total_s/60:.1f}m"
            avg_f = f"{avg_s:.1f}s" if avg_s < 60 else f"{avg_s/60:.1f}m"
            max_f = f"{max_s:.1f}s" if max_s < 60 else f"{max_s/60:.1f}m"
            print(f"  {name:<25s} {calls:>5d} {total_f:>8s} {avg_f:>8s} {max_f:>8s} {pct:>5.1f}%")

        total_f = f"{total_wall:.1f}s" if total_wall < 60 else f"{total_wall/60:.1f}m"
        print(f"  {'─'*25} {'─'*5} {'─'*8} {'─'*8} {'─'*8} {'─'*6}")
        print(f"  {'TOTAL':<25s} {'':>5s} {total_f:>8s}")
        print("═" * 60 + "\n")

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _write(self, obj: Dict) -> None:
        """Append a JSON line and flush immediately."""
        try:
            self._fh.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
            self._fh.flush()
        except Exception:
            pass  # never crash the pipeline due to tracing

    def _summarise(self, node_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract a compact, serialisable summary of the state for this node."""
        # idea may only exist in accumulated state (not per-node delta)
        idea = state.get("idea") or self.idea or ""
        summary: Dict[str, Any] = {
            "idea_snippet": (idea[:120] + "…") if len(idea) > 120 else idea,
            "stage": state.get("current_stage", ""),
        }

        rc = state.get("research_context") or {}

        if node_name == "research":
            summary["papers"]          = len(rc.get("papers", []) or [])
            summary["web_results"]     = len(rc.get("web_results", []) or [])
            summary["implementations"] = len(rc.get("implementations", []) or [])

        elif node_name == "generate_perspectives":
            persp = state.get("perspectives") or state.get("experts") or []
            summary["perspectives"] = len(persp) if isinstance(persp, list) else str(type(persp))

        elif node_name == "problem_extraction":
            problems = state.get("problems") or []
            sel      = state.get("selected_problem") or ""
            summary["problem_count"]    = len(problems)
            summary["problems_preview"] = [str(p)[:80] for p in problems[:3]]
            summary["selected_problem"] = str(sel)[:120]

        elif node_name == "solution_generation":
            rounds = state.get("debate_rounds") or []
            if not isinstance(rounds, list): rounds = []
            summary["debate_rounds"] = len(rounds)
            if rounds:
                last = rounds[-1]
                proposals = last.get("proposals") or [] if isinstance(last, dict) else []
                summary["proposals_this_round"] = len(proposals)
                summary["proposal_snippets"] = [
                    {
                        "perspective":    p.get("perspective", ""),
                        "approach_name":  str(p.get("approach_name",  ""))[:80],
                        "key_innovation": str(p.get("key_innovation", ""))[:120],
                        "novelty":        p.get("novelty_score",    0),
                        "feasibility":    p.get("feasibility_score",0),
                    }
                    for p in proposals[:3] if isinstance(p, dict)
                ]

        elif node_name == "critique":
            rounds = state.get("debate_rounds") or []
            if not isinstance(rounds, list): rounds = []
            if rounds:
                last = rounds[-1] if isinstance(rounds[-1], dict) else {}
                critiques = last.get("critiques") or []
                summary["critiques_count"] = len(critiques)
                summary["critique_snippets"] = [
                    {
                        "reviewer":    c.get("reviewer_perspective", ""),
                        "assessment":  c.get("overall_assessment", ""),
                        "strengths":   (c.get("strengths") or [])[:2],
                        "weaknesses":  (c.get("weaknesses") or [])[:2],
                        "recommend":   c.get("recommendation", ""),
                    }
                    for c in critiques[:3] if isinstance(c, dict)
                ]

        elif node_name == "consensus_check":
            score = state.get("consensus_score", 0)
            rounds = state.get("debate_rounds") or []
            n_rounds = len(rounds) if isinstance(rounds, list) else (rounds if isinstance(rounds, int) else 0)
            summary["consensus_score"] = score
            summary["debate_rounds"]   = n_rounds

        elif node_name == "solution_selection":
            fs = state.get("final_solution") or {}
            summary["selected_solution"] = {
                "approach_name":  str(fs.get("approach_name",  ""))[:100],
                "perspective":    str(fs.get("perspective",    ""))[:60],
                "key_innovation": str(fs.get("key_innovation", ""))[:200],
                "architecture":   str(fs.get("architecture_design", ""))[:200],
                "impl_steps":     (fs.get("implementation_plan") or [])[:3],
                "novelty_score":  fs.get("novelty_score",    0),
                "feasibility":    fs.get("feasibility_score",0),
            }

        elif node_name == "code_generation":
            gc_files = state.get("generated_code") or {}
            if not isinstance(gc_files, dict): gc_files = {}
            summary["files"]      = list(gc_files.keys())
            summary["file_count"] = len(gc_files)
            summary["file_sizes"] = {
                fname: len(code) if isinstance(code, (str, bytes)) else code
                for fname, code in list(gc_files.items())[:10]
            }

        elif node_name in ("code_testing", "code_fixing"):
            vr = state.get("validation_results") or {}
            if not isinstance(vr, dict): vr = {}
            errs = vr.get("errors") or []
            # Also count execution_errors from test_results (runtime crashes,
            # static-check failures, etc.) — previously these were invisible
            # because only validation_results.errors was counted.
            _tr = state.get("test_results") or {}
            if not isinstance(_tr, dict): _tr = {}
            _exec_errs = _tr.get("execution_errors") or []
            _validation_err_count = len(errs) if isinstance(errs, list) else 0
            _execution_err_count  = len(_exec_errs) if isinstance(_exec_errs, list) else 0
            summary["fix_attempts"]  = state.get("fix_attempts", 0)
            summary["tests_passed"]  = state.get("tests_passed", None)
            summary["errors_found"]  = _validation_err_count + _execution_err_count
            summary["validation_errors"] = _validation_err_count
            summary["execution_errors"]  = _execution_err_count
            summary["syntax_ok"]     = vr.get("syntax_valid", None)

            # Track deterministic auto-fixer effectiveness
            _auto_fixed = state.get("_auto_fixed_errors") or []
            if isinstance(_auto_fixed, list) and _auto_fixed:
                summary["auto_fixed_errors"] = len(_auto_fixed)
                summary["auto_fixed_types"] = list(set(
                    e.split(":")[0].strip() if ":" in str(e) else str(e)[:60]
                    for e in _auto_fixed[:20]
                ))
            else:
                summary["auto_fixed_errors"] = 0

        elif node_name == "git_publishing":
            summary["github_repo"] = state.get("github_repo", "")
            summary["output_dir"]  = state.get("output_dir", "")

        # Always include top-level error list size
        errs = state.get("errors") or []
        summary["total_pipeline_errors"] = len(errs) if isinstance(errs, list) else 0
        return summary

    def _write_status_md(
        self,
        token_stats: Dict[str, Any],
        health: Dict[str, Any],
    ) -> None:
        """Write the human-readable agent_status Markdown file."""
        lines: List[str] = []
        lines.append("# 🤖 Auto-GIT Agent & Model Status Report\n")
        lines.append(f"**Run**: `{self.ts}`  ")
        lines.append(f"**Idea**: _{self.idea[:120]}_\n")

        # ── Pipeline node execution table ──────────────────────────────────
        lines.append("## 📊 Pipeline Node Execution\n")
        lines.append("| # | Node | Status | Calls | Time | % |")
        lines.append("|---|------|--------|-------|------|---|")
        profiling = self.get_profiling_data()
        prof_nodes = profiling.get("nodes", {})
        for i, node in enumerate(_ALL_NODES, 1):
            calls  = self._call_count.get(node, 0)
            status = "✅ ran" if calls > 0 else "⬜ not reached"
            pn = prof_nodes.get(node, {})
            time_s = pn.get("total_s", 0)
            pct    = pn.get("pct_of_total", 0)
            time_f = f"{time_s:.1f}s" if time_s < 60 else f"{time_s/60:.1f}m"
            lines.append(f"| {i} | `{node}` | {status} | {calls} | {time_f} | {pct:.1f}% |")

        # ── Token usage ────────────────────────────────────────────────────
        lines.append("\n## 🧠 LLM Token Usage\n")
        total   = token_stats.get("total_tokens", 0)
        calls   = token_stats.get("calls", 0)
        prompt  = token_stats.get("prompt_tokens", 0)
        comp    = token_stats.get("completion_tokens", 0)
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total LLM calls | **{calls}** |")
        lines.append(f"| Total tokens | **{total:,}** |")
        lines.append(f"| Prompt tokens | {prompt:,} |")
        lines.append(f"| Completion tokens | {comp:,} |")

        by_profile = token_stats.get("by_profile") or {}
        if by_profile:
            lines.append("\n### By Profile\n")
            lines.append("| Profile | Tokens |")
            lines.append("|---------|--------|")
            for profile, n in sorted(by_profile.items(), key=lambda x: -x[1]):
                lines.append(f"| `{profile}` | {n:,} |")

        by_model = token_stats.get("by_model") or {}
        if by_model:
            lines.append("\n### By Model (top 15)\n")
            lines.append("| Model | Tokens |")
            lines.append("|-------|--------|")
            for model, n in sorted(by_model.items(), key=lambda x: -x[1])[:15]:
                display = model if len(model) <= 60 else "…" + model[-59:]
                lines.append(f"| `{display}` | {n:,} |")

        # ── Model health ───────────────────────────────────────────────────
        lines.append("\n## ⚕️ Model Health\n")

        resolved = health.get("resolved") or {}
        if resolved:
            lines.append("### ✅ Active (resolved profile → model)\n")
            lines.append("| Profile | Model |")
            lines.append("|---------|-------|")
            for profile, model in sorted(resolved.items()):
                lines.append(f"| `{profile}` | `{model}` |")

        dead = health.get("dead") or []
        if dead:
            lines.append("\n### 🚫 Dead — 404 (skipped for rest of session)\n")
            for m in dead:
                lines.append(f"- `{m}`")

        cooling = health.get("cooling") or []
        if cooling:
            lines.append("\n### ⏳ Rate-limited (cooling down)\n")
            for entry in cooling:
                m   = entry.get("model", entry) if isinstance(entry, dict) else entry
                rem = entry.get("remaining_s", "?") if isinstance(entry, dict) else "?"
                lines.append(f"- `{m}` — {rem}s remaining")

        timed_out = health.get("timed_out") or {}
        if timed_out:
            lines.append("\n### ⏱️ Timed-out this session\n")
            lines.append("| Model | Timeouts |")
            lines.append("|-------|----------|")
            for m, cnt in sorted(timed_out.items(), key=lambda x: -x[1]):
                lines.append(f"| `{m}` | {cnt} |")

        lines.append("\n---\n_Generated by Auto-GIT pipeline tracer_")

        try:
            with open(self.status_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass
