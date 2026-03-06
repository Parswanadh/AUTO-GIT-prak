# Auto-GIT Pipeline Delay Root-Cause Report

**Date**: March 7, 2026  
**Prepared By**: GitHub Copilot  
**Method**: Direct code inspection + sub-agent static analysis + sub-agent docs/logs analysis

---

## Executive Summary

The pipeline is slow primarily because the **late-stage execution path is too heavy and too repetitive**.

The strongest root causes are:

1. **Repeated environment creation and dependency installation**
2. **Large LLM timeout budgets and fallback cascades**
3. **Repeated code generation / review / testing / fixing loops**
4. **High prompt volume and large cross-file context during generation/fixing**
5. **Weak observability around node-level time, VRAM, and retry cost**

This means the pipeline is not mainly slow because of research. It is mainly slow because the **back half of the pipeline repeats expensive work**.

---

## Investigation Steps

### Step 1: Static code-path investigation
A sub-agent reviewed the main enhanced pipeline and supporting utilities, focusing on:
- `src/langraph_pipeline/nodes.py`
- `src/langraph_pipeline/workflow_enhanced.py`
- `src/utils/model_manager.py`
- `src/utils/code_executor.py`
- `src/utils/enhanced_validator.py`
- related validation / testing helpers

### Step 2: Docs and logs investigation
A second sub-agent reviewed:
- `PROGRESS.md`
- `claude.md`
- `BUILD_STATUS_TODO.md`
- `PIPELINE_IMPROVEMENT_PLAN.md`
- `logs/`
- runtime output artifacts
- monitoring and trace-related files

### Step 3: Reconciliation
The two analyses were compared to separate:
- actual dominant latency sources
- secondary costs
- stale assumptions in older documentation

---

## Root Causes Ranked

## 1. Repeated environment creation and dependency installation

### Why it is slow
Testing and verification repeatedly create virtual environments and install dependencies. That cost is then paid again when the fix loop re-enters testing.

### Why this matters
This is pure setup overhead and does not improve output quality after the first successful environment build.

### Impact level
**Very High**

### Fix
- Reuse one persistent environment per generated project
- Key it by a requirements hash
- Skip reinstall when requirements did not change
- Reuse the same environment across testing, feature verification, and fix loops

---

## 2. Long timeout budgets and provider fallback cascades

### Why it is slow
Some stages allow very long waits before timing out, and then retry or cascade to fallback providers. A single bad model response path can consume several minutes.

### Why this matters
This produces invisible stalls and turns isolated provider issues into pipeline-wide latency spikes.

### Impact level
**Very High**

### Fix
- Add node-level latency budgets
- Lower per-stage timeout budgets for hot-path calls
- Preflight provider health once per run
- Restrict fallback chains in latency-sensitive stages

---

## 3. Multi-pass code generation / review / test / fix loops

### Why it is slow
The pipeline can do:
- code generation
- code review
- code testing
- feature verification
- strategy reasoning
- code fixing
- self-eval / goal-eval

Then repeat parts of that sequence multiple times.

### Why this matters
Even if each stage is reasonable alone, repeating the whole back half causes multiplicative latency.

### Impact level
**Very High on failing runs**

### Fix
- Add wall-clock stop conditions, not just attempt counts
- Skip full review after tiny deterministic fixes
- Re-test only changed files or changed checks where possible
- Stop expanding fix budgets before runtime stability is proven

---

## 4. Large prompt payloads and repeated full-file context injection

### Why it is slow
Code generation and fix prompts include extensive cross-file context. This increases token volume and slows model response time.

### Why this matters
Prompt bloat directly increases both token cost and latency.

### Impact level
**High**

### Fix
- Replace whole-file regeneration with patch/diff-based edits
- Use repo-map summaries instead of dumping broad file contents
- Send only changed or directly related files

---

## 5. Per-file validation using multiple subprocess tools

### Why it is slow
The enhanced validator runs multiple tools like `mypy`, `bandit`, and `ruff`, and that work can repeat over many files and many fix passes.

### Why this matters
Validation is valuable, but repeated per-file subprocess startup is expensive.

### Impact level
**Moderate to High**

### Fix
- Run project-level validation where possible
- Skip unchanged files
- Use cheap syntax/import gates first, then deeper checks only when needed

---

## 6. Feature verification adds another expensive pass

### Why it is slow
Feature verification adds another LLM generation step plus another subprocess execution phase after regular testing already happened.

### Impact level
**Moderate**

### Fix
- Only run feature verification when structured requirements are rich enough
- Reuse the same test environment and project directory
- Cache generated feature tests across retries

---

## 7. Research is not the top bottleneck, but it still contributes

### Why it is slow
Research may perform multiple passes, fallbacks, and citation verification.

### Impact level
**Moderate**

### Fix
- Cache research results by idea hash
- Make deep-dive passes optional
- Parallelize citation verification

---

## Evidence Summary

## Evidence from logs/docs
- Product/runtime expectations still mention roughly **5–10 minutes** in some docs
- Real recorded runs in logs and progress notes show roughly **20–80+ minutes**
- A traced run showed the heaviest stages were:
  - `code_review_agent`
  - `code_generation`
  - `code_fixing`
  - repeated `code_testing`
  - repeated `strategy_reasoner`

## Evidence from code
- expensive retry loops and long timeouts
- repeated environment creation
- multiple late-stage loops
- expensive subprocess-based validation
- heavy cross-file prompt construction

---

## Observability Gaps

Current observability is not strong enough to prove stage-level cost in real time.

### Missing or incomplete
- resource monitoring is not fully integrated into the live workflow
- per-node wall-clock budgets are not enforced
- VRAM / RAM / CPU are not consistently logged per node
- token tracking is incomplete in some paths
- published runtime expectations are stale relative to real logs

### Why this matters
Without full node-level telemetry, the system relies too much on inference instead of measured bottlenecks.

---

## Immediate Recommendations

## Phase 1: Fastest wins
1. Reuse one persistent test environment
2. Lower timeout budgets in hot-path stages
3. Add node-level timing and slow-stage logging
4. Gate expensive review/fix loops after small deterministic fixes

## Phase 2: Architecture improvements
5. Implement diff-based fixing instead of whole-file regeneration
6. Add repo-map / code-graph context instead of large raw prompts
7. Split validation into cheap-vs-expensive tiers

## Phase 3: Observability
8. Integrate `ResourceMonitor` into the main workflow
9. Record per-node CPU/RAM/VRAM/token/latency metrics
10. Publish runtime dashboards based on real completed runs

---

## Recommended Next Engineering Order

1. Fix repeated environment recreation
2. Add node-level timeout budgets
3. Reduce retry/fallback waste
4. Limit repeated review/fix loops
5. Add integrated runtime telemetry
6. Then implement plan items like speculative diffs and repo-map context

---

## Bottom Line

The pipeline delay is caused mostly by **repeated expensive work after generation begins**, not by the initial research phase.

The best immediate improvement is to:
- **reuse environments**,
- **cap slow nodes harder**,
- **reduce repeated full-pipeline fix loops**,
- **measure real per-node cost with integrated telemetry**.
