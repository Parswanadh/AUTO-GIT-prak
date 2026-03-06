# Auto-GIT Pipeline — Comprehensive AGI Audit Report

**Audited**: February 2026  
**Scope**: 8 core files — `state.py`, `workflow_enhanced.py`, `nodes.py`, `model_manager.py`, `enhanced_validator.py`, `code_executor.py`, `codegen_error_memory.py`, `run_pipeline.py`  
**Lines of code audited**: ~7,600  
**Verdict**: The system has impressive ambition and clever defensive engineering, but suffers from **God-file concentration risk**, **silent failure masking**, **duplicated logic**, and **validation gaps that inflate quality scores**. The pipeline can complete runs, but the quality numbers it reports should not be trusted at face value.

---

## 1. EVERY PIPELINE NODE — Purpose, Inputs, Outputs, Failure Modes

### Node 1: `research_node` (lines ~240–530 in nodes.py)

| Aspect | Detail |
|---|---|
| **Purpose** | Gathers research context from arXiv, web, GitHub via compound-beta model |
| **LLM Profile** | `research` (compound-beta with web search) |
| **Inputs** | `idea`, optional `requirements` dict |
| **Outputs** | `research_context` (papers, open_problems, implementations, benchmarks), `current_stage` |
| **Failure Modes** | All exceptions caught → returns empty `research_context` with stub structure. **Never crashes the pipeline.** |
| **Silent Failures** | If compound-beta 404s and SearXNG is down and DDG fails, the node returns an empty context dict with zero papers. Downstream nodes will try to extract problems from nothing. No error is appended to state `errors`. The pipeline continues as if research succeeded. |
| **Structural Note** | Has a two-pass architecture: broad search → LLM-identified gap fill. The gap-fill pass is inside a try-except that swallows failures silently. |

### Node 1.5: `generate_perspectives_node` (lines ~540–660)

| Aspect | Detail |
|---|---|
| **Purpose** | Uses LLM to create 3 domain-specific expert perspectives |
| **LLM Profile** | `balanced` |
| **Inputs** | `idea`, `research_context` |
| **Outputs** | `perspectives` list, `current_stage` |
| **Failure Modes** | Falls back to hardcoded `EXPERT_PERSPECTIVES` from state.py on any error. |
| **Weakness** | The hardcoded fallback always returns the same 3 generic experts (ML Researcher, Systems Engineer, Applied Scientist) regardless of whether the idea is about web dev, game design, or ML. |

### Node 2: `problem_extraction_node` (lines ~665–850)

| Aspect | Detail |
|---|---|
| **Purpose** | Extracts problems from research, selects the best one |
| **LLM Profile** | `fast` |
| **Inputs** | `idea`, `research_context`, optional `requirements` |
| **Outputs** | `problems`, `selected_problem`, `current_stage` |
| **Failure Modes** | If `requirements` dict exists, bypasses LLM entirely (uses requirements directly). Otherwise: triple fallback — LLM JSON parse → fallback problem extraction → emergency "implement {idea}" string. |
| **Silent Failures** | Empty paper list + empty implementation list → LLM gets a thin prompt. The LLM selection step has a `try-except` that falls back to `problems[0]` on any error, which could silently pick a bad problem. |

### Node 3: `solution_generation_node` (lines ~870–1010)

| Aspect | Detail |
|---|---|
| **Purpose** | All perspectives propose solutions in parallel |
| **LLM Profile** | `balanced` via `get_fallback_llm()` |
| **Inputs** | `perspectives`, `selected_problem`, `research_context` |
| **Outputs** | `debate_rounds` (appended), `current_stage` |
| **Failure Modes** | Uses `asyncio.gather(return_exceptions=True)`. Failed perspectives produce a fallback "error_proposal" string. If ALL fail, the debate round still gets appended (with error proposals). |
| **Architectural Note** | The `return_exceptions=True` pattern means exceptions are silently mixed into results. The code checks `isinstance(result, Exception)` but any exception type that doesn't match would slip through. |

### Node 4: `critique_node` (lines ~1015–1170)

| Aspect | Detail |
|---|---|
| **Purpose** | Each perspective critiques all other proposals |
| **LLM Profile** | `reasoning` (90-second per-call timeout) |
| **Inputs** | `debate_rounds`, `perspectives` |
| **Outputs** | Updated `debate_rounds` with critiques, `current_stage` |
| **Failure Modes** | Parallel critique via `asyncio.gather(return_exceptions=True)`. Failed critiques produce a "Could not critique" fallback string. If `debate_rounds` is empty, returns immediately with `"critique_complete"`. |
| **Self-review skip** | A perspective doesn't critique its own proposal. This is intentional but means each proposal gets only N-1 critiques. |

### Node 5: `consensus_check_node` (lines ~1175–1230)

| Aspect | Detail |
|---|---|
| **Purpose** | Scores consensus from critiques (no LLM call — deterministic) |
| **LLM Profile** | None (synchronous scoring) |
| **Inputs** | `debate_rounds`, `debate_round_count`, `max_debate_rounds`, `min_consensus_score` |
| **Outputs** | `consensus_score`, `should_continue_debate`, `current_stage` |
| **Failure Modes** | `except Exception` → returns `current_stage: "consensus_reached"`, forcing the pipeline forward. |
| **BUG: Direct state mutation** | Line ~1215: `state["should_continue_debate"] = False`. LangGraph uses immutable state snapshots; direct mutation may have no effect (the returned dict is what matters). This line is misleading dead code. |
| **Scoring** | Keyword matching: "accept"→1.0, "revise"→0.5, "reject"→0.0. Crude but functional. |

### Node 6: `solution_selection_node` (lines ~1235–1395)

| Aspect | Detail |
|---|---|
| **Purpose** | Picks the best proposal via LLM-driven weighted evaluation |
| **LLM Profile** | `reasoning` |
| **Inputs** | `debate_rounds`, `perspectives`, `selected_problem` |
| **Outputs** | `final_solution`, `current_stage` |
| **Failure Modes** | Triple fallback: LLM JSON → highest-scored proposal → emergency first-proposal fallback. The emergency path catches all exceptions and returns a minimal solution dict. |
| **Weakness** | The "highest-scored proposal" fallback uses debate critique scores, which are keyword-counted (accept/revise/reject). If all critiques failed, all proposals score 0 and it picks the first by index. |

### Node 6.5: `architect_spec_node` (lines ~1720–1900)

| Aspect | Detail |
|---|---|
| **Purpose** | Generates detailed technical spec (file plan, data flow, pseudocode, test scenarios) |
| **LLM Profile** | `balanced` via `get_fallback_llm()` |
| **Inputs** | `final_solution`, `idea`, `selected_problem` |
| **Outputs** | `architecture_spec` (JSON), `_architecture_spec_text` (human-readable), `current_stage` |
| **Failure Modes** | Non-fatal. On failure → sets `current_stage: "architect_failed"`, logs warning, pipeline continues without spec. Code generation falls back to LLM-decided file plans. |
| **Strength** | Separates planning from coding (architecture-first approach). The spec includes line count estimates per file. |

### Node 7: `code_generation_node` (lines ~1905–2960)

| Aspect | Detail |
|---|---|
| **Purpose** | Generates multi-file Python projects from spec/solution |
| **LLM Profile** | `powerful` |
| **Inputs** | `architecture_spec`, `final_solution`, `idea`, `research_context`, error memory lessons |
| **Outputs** | `generated_code` (dict with `files`), `current_stage` |
| **Sub-steps** | 13 sequential phases (see enumeration below) |

**13 Sub-phases of code_generation_node**:

1. Load codegen lessons from error memory (JSONL)
2. File planning (LLM or architect spec)
3. Shadow file sanitization (prevent torch.py, numpy.py)
4. Interface contract generation (class signatures)
5. Parallel file generation with stub detection + retry (3 attempts/file)
6. Post-gather shadow sanitization (second pass)
7. Phantom relative import cleanup
8. Requirements.txt cleaning (stdlib filtering)
9. RESEARCH_REPORT.md injection
10. LLM self-review pass (cross-file consistency)
11. Deterministic AST-based cross-file import validator
12. Duplicate class detection/deduplication
13. File key flattening

**Failure Modes**: Each sub-phase has its own try-except. Failures in phases 3-13 are individually caught and logged but don't crash the node. The only fatal failure is complete LLM unavailability during file generation.

**Key Risk**: Phase 5 uses `asyncio.gather(return_exceptions=True)`. Empty file returns (0 bytes) are caught by a post-gather audit that retries serially, but if the serial retry also returns empty, a "skeleton fallback" is written (a file with `raise NotImplementedError`). This means the pipeline can pass code_generation with stub files.

### Node 7.5: `code_review_agent_node` (lines ~2965–3250)

| Aspect | Detail |
|---|---|
| **Purpose** | Deep code review checking 15 bug types, with fix iterations |
| **LLM Profile** | `powerful` (review), `balanced` (fixes) |
| **Inputs** | `generated_code`, `idea`, `selected_problem`, `final_solution`, error memory lessons |
| **Outputs** | Updated `generated_code`, `current_stage` |
| **Iterations** | Up to 2 review→fix cycles |

**15 Bug Types Checked**:
`TRUNCATED`, `MISSING_ENTRY_POINT`, `SILENT_MAIN`, `MISSING_OUTPUT_PROJECTION`, `DEAD_LOGIC`, `STUB_BODY`, `WRONG_CALL`, `MISSING_EXPORT`, `CIRCULAR_IMPORT`, `SHAPE_MISMATCH`, `DUPLICATE_CLASS`, `PLACEHOLDER_INIT`, `API_MISMATCH`, `SELF_METHOD_MISSING`, `UNINITIALIZED_ATTR`

**Failure Modes**: Entire node is non-fatal. If LLM review fails → returns with original code unchanged. If fix LLM fails → keeps original file. Records all found issues to codegen error memory.

**Weakness**: The review is entirely LLM-driven (no AST analysis). The LLM might hallucinate issues that don't exist, or miss real issues. The fix prompt says "return ONLY the fixed code" but LLMs frequently include prose.

### Node 8: `code_testing_node` (lines ~3260–3790)

| Aspect | Detail |
|---|---|
| **Purpose** | Tests generated code via CodeExecutor + EnhancedValidator + static analysis |
| **LLM Profile** | None (no LLM calls) |
| **Inputs** | `generated_code` |
| **Outputs** | `test_results`, `tests_passed`, `code_quality`, `current_stage` |

**Test Pipeline**:
1. Fast AST pre-check (skip venv if syntax broken)
2. Parallel enhanced validation (mypy/bandit/ruff per file)
3. CodeExecutor full test suite (venv create → pip install → syntax → imports → main.py run → basic tests)
4. Static placeholder audit (`nn.Module()` detection)
5. Static method-call/attribute validator (self.method(), cross-file var.method())
6. Pip-timeout grace (if only failure is pip timeout + quality ≥ 80 → pass)
7. Record errors to codegen memory

**Failure Modes**: Top-level `except Exception` returns `testing_failed` with `tests_passed=False`.

**CRITICAL WEAKNESS: `run_basic_tests()` always returns True.** The method in CodeExecutor has the comment "Don't fail on test warnings" and unconditionally returns `True`. This means the test suite has a gap: generated test files are never actually executed with assertion checking.

### Node 8.4: `strategy_reasoner_node` (lines ~3795–3970)

| Aspect | Detail |
|---|---|
| **Purpose** | Analyzes WHY code failed, classifies failure category, generates strategic fix plan |
| **LLM Profile** | `reasoning` |
| **Inputs** | `test_results`, `generated_code`, `idea`, `final_solution`, `_prev_fix_strategies` |
| **Outputs** | Updated `test_results` (with `fix_strategy` injected), `_prev_fix_strategies`, `current_stage` |
| **Failure Modes** | On any error → returns `strategy_fallback` stage, code_fixing proceeds without strategy. |
| **Strategy tracking** | Appends each strategy summary to `_prev_fix_strategies` and includes last 3 in prompt. Prevents repeating failed strategies. |
| **Strength** | This is the most architecturally interesting node — it separates diagnosis from treatment. |

**Failure Categories**: `architecture_flaw`, `incomplete_impl`, `wrong_api`, `shadow_file`, `circular_import`, `missing_dep`, `stub_code`, `truncated`, `wrong_algorithm`

**Fix Strategies**: `patch_files`, `regenerate_worst`, `regenerate_all`

### Node 8.5: `code_fixing_node` (lines ~3975–4465)

| Aspect | Detail |
|---|---|
| **Purpose** | Applies fixes based on test errors and strategy reasoner guidance |
| **LLM Profile** | `powerful` (complex fixes) or `fast` (simple patches) |
| **Inputs** | `test_results` (with `fix_strategy`), `generated_code`, `fix_attempts` |
| **Outputs** | Updated `generated_code`, incremented `fix_attempts`, `current_stage` |
| **Max attempts** | Default 2 (configurable via state `max_fix_attempts`) |

**Key Features**:
- **Fast path**: Pip-only errors → regex-based requirements.txt fix (no LLM call)
- **Shadow file deletion**: Proactively removes files named after packages (torch.py, numpy.py)
- **Strategy-aware**: Uses `fix_strategy` from reasoner to decide patch vs regenerate per file
- **Local module stub generation**: If a `ModuleNotFoundError` is for a local project module (not pip), generates a stub .py file
- **Post-fix AST import repair**: Same cross-file import validator as code_generation
- **Garbage rejection**: Rejects LLM responses that are empty, prose, or syntactically invalid

**Failure Modes**: `except Exception` → returns `fixing_error` with incremented `fix_attempts`. The increment is critical — without it, the pipeline would retry forever.

**BUG: Inconsistent `tests_passed` on pip-only fix**. Line ~4060: pip-only fix path sets `tests_passed: True` without actually re-testing. The code is assumed fixed but never verified.

### Node 9.5: `pipeline_self_eval_node` (lines ~4475–4640)

| Aspect | Detail |
|---|---|
| **Purpose** | Holistic evaluation of generated solution against original idea |
| **LLM Profile** | `powerful` |
| **Inputs** | `idea`, `selected_problem`, `final_solution`, `generated_code`, `test_results` |
| **Outputs** | `self_eval_score`, `self_eval_attempts`, `current_stage` |
| **Scoring** | 0-10 across 4 dimensions: Completeness, Correctness, Alignment, Code Quality |
| **Re-loop threshold** | Score < 4 AND `self_eval_attempts < MAX_SELF_EVAL` (MAX_SELF_EVAL=1) → route back to code_fixing |
| **Failure Modes** | On any error → returns `self_eval_approved` with score -1 and proceeds to publish. **This means a crash in self-eval ALWAYS approves the code.** |
| **Code preview** | Sends first 200 lines per file to LLM. Files longer than 200 lines are truncated. |

**KEY ISSUE**: `MAX_SELF_EVAL = 1` combined with threshold `< 4` means: the self-eval loop effectively runs exactly once and almost never triggers a re-loop (score must be under 4/10). This makes the self-eval a **read-only checkpoint** in practice, not a quality gate.

### Node 9: `git_publishing_node` (lines ~4645–4839)

| Aspect | Detail |
|---|---|
| **Purpose** | Saves code locally or publishes to GitHub |
| **LLM Profile** | None |
| **Inputs** | `generated_code`, `auto_publish`, `tests_passed`, `final_solution` |
| **Outputs** | `output_path` or `github_url`, `current_stage` |
| **Failure Modes** | Publishing failure → fallback to local save. Local save failure → returns error list. |
| **Shadow filter** | Has its own `_SHADOW_SAVE` set (different member list than `_SHADOW_PKG_STEMS_FIX` in code_fixing). |

**BUG: Missing shadow filter on auto_publish=True path**. The shadow file filter (`_SHADOW_SAVE`) only applies in the `tests_failed` local-save path (line ~4690). The `auto_publish=True` GitHub path (line ~4755) and the `auto_publish=False` local-save path (line ~4730) do NOT filter shadow files. Shadow files like `numpy.py` will be published to GitHub.

---

## 2. FIX LOOP MECHANICS

### Loop Topology
```
code_generation → code_review_agent → code_testing ─┬→ strategy_reasoner → code_fixing ──┐
                                                     │                                     │
                                                     │    code_testing ←───────────────────┘
                                                     │         │
                                                     │    (tests pass OR max attempts)
                                                     │         ↓
                                                     └→ pipeline_self_eval ─┬→ git_publishing
                                                                            │
                                                                            └→ code_fixing (score < 4)
```

### Routing Logic (workflow_enhanced.py)

**`should_fix_code()`**:
- `tests_passed == True` → `pipeline_self_eval`
- `fix_attempts >= max_fix_attempts` (default 2) → `pipeline_self_eval`
- Empty generated files → `pipeline_self_eval` (prevents looping on nothing)
- `current_stage in {testing_skipped, no_errors_to_fix, fixing_failed}` → `pipeline_self_eval`
- Otherwise → `strategy_reasoner`

**`_after_fixing()`**:
- `current_stage == fixing_failed` → `pipeline_self_eval` (bail out)
- Otherwise → `code_testing` (skips code_review_agent on re-fixes)

**`should_regen_or_publish()`**:
- `current_stage == self_eval_needs_regen` AND `fix_attempts < max_fix_attempts` → `code_fixing`
- Otherwise → `git_publishing`

### Maximum Iterations (Worst Case)
- Fix loop: 2 iterations (max_fix_attempts=2)
- Self-eval re-loop: 1 iteration (MAX_SELF_EVAL=1), grants 1 more fix attempt
- **Theoretical max**: 2 fix cycles + 1 self-eval regen + 1 more fix = **4 total fix iterations**
- Each iteration involves: strategy_reasoner (1 LLM call) + code_fixing (N LLM calls, one per broken file) + code_testing (no LLM, but full venv cycle)

### Termination Guarantees
- `fix_attempts` is **always incremented** (even on error), preventing infinite loops
- `self_eval_attempts` is always incremented
- `MAX_SELF_EVAL = 1` caps re-evaluation
- `recursion_limit = 100` in LangGraph compilation (hard ceiling)

### Gap: No Code Review on Re-fixes
`_after_fixing()` routes directly to `code_testing`, skipping `code_review_agent_node`. This means fixes are never reviewed for the 15 bug types on subsequent iterations. A fix could introduce a TRUNCATED file or PLACEHOLDER_INIT and it would only be caught by the static checks in code_testing, not the LLM-powered review.

---

## 3. SELF-EVALUATION SCORING

### Dimensions
| Dimension | What it assesses |
|---|---|
| Completeness | Every planned file exists with real code |
| Correctness | main.py runs, no known errors |
| Alignment | Code addresses stated idea/problem |
| Code Quality | No magic strings, error handling, entry-point guard |

### Thresholds & Routing
| Score Range | Action |
|---|---|
| ≥ 4 | **Approved** → git_publishing |
| < 4 (first eval) | **Rejected** → injects `self_eval_fixes` guidance into test_results, routes to code_fixing |
| < 4 (second+ eval) | **Approved anyway** (MAX_SELF_EVAL exhausted) |

### Weaknesses
1. **Threshold too low**: Score < 4 is the only trigger for re-work. A 4.0/10 project gets published. In practice, LLMs tend to score generously (7-9 range), so this gate rarely fires.
2. **MAX_SELF_EVAL = 1**: Only one chance to improve. Was reduced from 3 to prevent long runtimes, but now the gate is nearly non-functional.
3. **Crash = Approve**: Any exception in the self-eval LLM call → `self_eval_approved` with score -1. The pipeline publishes regardless.
4. **Truncated input**: Only first 200 lines per file are sent to the evaluator. A file could have broken code after line 200 and the evaluator would never see it.
5. **No execution test**: Self-eval doesn't run the code — it relies on whatever code_testing already found. If code_testing had a pip timeout grace pass, the self-eval sees "Test suite passed" even though main.py was never executed.

---

## 4. ERROR MEMORY (codegen_error_memory.py)

### Architecture
- **Storage**: Append-only JSONL at `data/memory/codegen_errors.jsonl`
- **Schema**: `{run_id, idea_summary, phase, bug_type, file, description, fix_applied, fixed, timestamp}`
- **Truncation**: `idea_summary` → 120 chars, `description`/`fix_applied` → 300 chars
- **Retrieval**: `get_top_lessons(n=15)` groups by `bug_type::description[:80]`, returns most-frequent patterns
- **Injection Points**: Code generation prompt (top 15 lessons), Code review agent prompt (top 10 lessons)

### Strengths
- Learns from real failures across runs
- Frequency-weighted: common bugs get higher priority in prompts
- Separate retrieval formats for generation vs review
- Singleton pattern prevents file contention

### Weaknesses

1. **No pruning/rotation**: The JSONL file grows forever. After 1000+ runs, lesson retrieval becomes I/O heavy and the "top N" list may be dominated by stale patterns from early (bad) runs.

2. **No "fixed" tracking feedback loop**: The `fixed` field exists but is never updated after recording. There's no mechanism to mark a lesson as "successfully addressed" or "no longer relevant".

3. **String-based deduplication is fragile**: Grouping by `bug_type::description[:80]` means slightly different error messages for the same root cause create separate entries. Example: `"API_MISMATCH: model.py:42 — train() called"` vs `"API_MISMATCH: model.py:87 — train() called"` would be two separate lessons even though they're the same bug.

4. **Recording happens at two disjoint points**:
   - `code_testing_node` records errors from static analysis (phase: `static_check`)  
   - `code_review_agent_node` records issues found by LLM review (phase: `code_review`)
   - But `code_fixing_node` does NOT record what it fixed, so the memory has no "fix_applied" data.

5. **No error categorization taxonomy**: Bug types are ad-hoc strings extracted by substring matching (`if _known in _err_s`). There's no enum or controlled vocabulary.

---

## 5. CODE REVIEW AGENT (Node 7.5) — Detailed Analysis

### What It Does Well
- **Context-rich prompts**: Includes idea, selected_problem, solution architecture — not just raw code
- **Iterative**: Up to 2 review→fix cycles (review, apply fixes, re-review)
- **Concurrent fixes**: Multiple file fixes run in parallel via `asyncio.gather`
- **Error memory integration**: Injects top 10 historical lessons into review prompt
- **15 bug type taxonomy**: Comprehensive coverage of common LLM codegen failures

### What's Missing

1. **No AST verification of LLM-reported issues**: The review agent asks the LLM to find bugs, but doesn't verify the LLM's claims with actual AST analysis. The LLM might report "WRONG_CALL: model.train() doesn't exist" when `train()` is actually defined. There's no ground-truth check.

2. **Fix quality not validated**: After fixing, the code isn't re-parsed or tested. The fix might introduce new syntax errors. The next opportunity for checking is code_testing_node.

3. **Severity conflation**: All issues are treated as fixable. A `TRUNCATED` file (mid-function cutoff) gets the same "fix this file" treatment as a `MISSING_EXPORT` (simple import fix). Truncated files should probably be regenerated, not patched.

4. **No diff tracking**: The review records issues to error memory but doesn't record what the fix changed. There's no diff or before/after comparison.

5. **Prompt is very long** (~2000 tokens of instructions) — for free-tier models with 4K context windows, the actual code content gets squeezed.

---

## 6. INTERFACE CONTRACTS — Assessment

### Architecture (in code_generation_node, lines ~2200–2270)

The contract generation step asks the LLM to produce a JSON dict:
```json
{
  "filename.py": {
    "ClassName": {
      "constructor": "__init__(self, param1: type, param2: type)",
      "methods": ["method1(self, x: int) -> float", "method2(self) -> None"],
      "description": "..."
    }
  }
}
```

This contract is injected into every file generation prompt as: `"INTERFACE CONTRACT — you MUST implement these EXACT signatures"`.

### Strengths
- Ensures all files agree on API before any code is written
- Prevents the most common cross-file bug class (wrong method name, wrong constructor args)
- The contract is generated from the architecture spec, creating a planning → contract → code chain

### Weaknesses

1. **Single LLM call, no validation**: The contract itself is generated by one LLM call with no AST or type checking. If the LLM generates an inconsistent contract (class A calls B.foo() but B's contract doesn't list foo()), this inconsistency propagates to all generated files.

2. **Contract violations aren't checked**: After code generation, there's no step that verifies generated code matches the contract. The cross-file import validator checks exports exist, but doesn't check method signatures match the contract.

3. **No module-level contract**: The contract covers classes and methods but not module-level functions, constants, or global variables. `from utils import DEVICE, SEED` won't be covered.

4. **Failure is silent**: If contract generation fails (LLM returns invalid JSON), the code generation proceeds without contracts. There's no warning that the contract step was skipped.

---

## 7. TODO, FIXME, HACK, and Incomplete Code

### Active TODOs in Core Pipeline

| File | Line | TODO |
|---|---|---|
| `src/utils/code_validator.py` | 844 | `# TODO: Implement test` — test generation stub |
| `src/utils/code_validator.py` | 853 | `# TODO: Implement test` — another test stub |
| `src/cli/claude_code_cli.py` | 80 | `# TODO: Call LLM with thinking prompt` |
| `src/cli/claude_code_cli.py` | 186 | `# TODO: Actually start MCP server process` |
| `src/cli/claude_code_cli.py` | 203 | `# TODO: Query actual MCP server for tools` |
| `src/cli/claude_code_cli.py` | 229 | `# TODO: Check if tool exists in server` |
| `src/cli/claude_code_cli.py` | 230 | `# TODO: Execute tool via MCP protocol` |
| `src/cli/claude_code_cli.py` | 508 | `# TODO: Route to appropriate handler` |
| `src/knowledge_graph/pattern_learner.py` | 346 | `# TODO: Link errors to fixes via graph edges` |
| `src/agents/specialists/specialist_agents.py` | 72 | `# TODO: Implement actual functionality` |
| `src/agents/specialists/specialist_agents.py` | 123 | `# TODO: Implement test` |
| `src/agents/specialists/specialist_agents.py` | 128 | `# TODO: Implement edge case tests` |
| `src/agents/specialists/specialist_agents.py` | 133 | `# TODO: Implement error tests` |
| `src/agents/tier3_generation/quality_assessor.py` | 557 | `# TODO: Integrate with HybridRouter when ready` |

### Summary
- **6 TODOs** in `claude_code_cli.py` — MCP integration is non-functional
- **2 TODOs** in `code_validator.py` — test generation stubs (the pipeline's own validation can't generate tests)
- **4 TODOs** in `specialist_agents.py` — entire module is stub code
- **1 TODO** in `pattern_learner.py` — knowledge graph integration incomplete
- **1 TODO** in `quality_assessor.py` — hybrid router integration pending

### Dead Stub Modules
- `src/agents/specialists/specialist_agents.py`: 4 TODO stubs. The `specialist_run()` function body is `# TODO: Implement actual functionality`. This module appears to be legacy and unused by the pipeline.

---

## 8. DEAD CODE & UNREACHABLE PATHS

### 1. `get_model_manager()` Defined Twice (model_manager.py:763 and :787)

```python
# Line 763 — FIRST definition (DEAD CODE):
def get_model_manager() -> ModelManager:
    """Return the global ModelManager singleton."""
    global _manager
    # <-- EMPTY BODY, returns None implicitly

# Lines 774-785: get_profile_primary() defined between the two

# Line 787 — SECOND definition (the real one):
def get_model_manager() -> ModelManager:
    """Return the global ModelManager singleton."""
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager
```

Python uses the last definition, so this works accidentally. But the first definition is dead code and would cause a `None` return + crash if the second were ever removed.

### 2. `run_basic_tests()` Always Returns True (code_executor.py)

The method exists and is called, but its return value is always `True`:
```python
def run_basic_tests(self, ...):
    # ... runs tests ...
    return True  # "Don't fail on test warnings"
```
This makes the function a no-op for pass/fail decisions. It's called in `run_full_test_suite()` but its result is never used to fail the test suite.

### 3. `consensus_check_node` Direct State Mutation (nodes.py:~1215)

```python
state["should_continue_debate"] = False  # Has no effect
```
LangGraph state is immutable between nodes. Only the returned dict matters. This line executes pointlessly.

### 4. Option 6 Self-Review Duplicated by Node 7.5

`code_generation_node` contains an "LLM self-review pass" (phase 10, lines ~2700-2750) that checks for cross-file issues. `code_review_agent_node` (Node 7.5) does the same thing more thoroughly with 15 bug types. The Option 6 self-review is now redundant — it catches a subset of what Node 7.5 catches.

### 5. `_build_research_report()` helper (nodes.py:~1400-1715)

This 315-line function generates a RESEARCH_REPORT.md. It's only called from within `code_generation_node` to inject the report into the generated files. The function is not dead code, but it's an unusually large helper embedded in a 4839-line file rather than being a utility function.

### 6. Shadow File Sets Duplicated

Three separate shadow file lists exist:
- `_SHADOW_PKG_STEMS` in `code_generation_node` (line ~2060)
- `_SHADOW_PKG_STEMS_FIX` in `code_fixing_node` (line ~4135)
- `_SHADOW_SAVE` in `git_publishing_node` (line ~4690)

These have **different members**. For example, `_SHADOW_SAVE` has only 10 entries while `_SHADOW_PKG_STEMS_FIX` has 60+. A file like `jwt.py` would be caught by `code_fixing_node` but not by `git_publishing_node`.

### 7. `_STDLIB_MODULES` and `_STDLIB_FIX` and `_STDLIB_AND_THIRDPARTY` Duplicated

Three separate stdlib/third-party sets:
- `_STDLIB_MODULES` (line ~86): Used in code_generation requirements cleaning
- `_STDLIB_AND_THIRDPARTY` (line ~2850 area): Used in cross-file import validation
- `_STDLIB_FIX` (line ~4395): Used in post-fix import repair

Each has slightly different members. Inconsistencies mean the same import could be treated as "local project module" in one context and "third-party package" in another.

---

## 9. SILENT FAILURE POINTS

### Tier 1: Failures That Masquerade as Success

| Location | Behavior | Impact |
|---|---|---|
| **EnhancedValidator: missing mypy/bandit/ruff** | Returns score 100/100 | Files with type errors, security vulns, or lint issues get perfect scores |
| **code_testing_node: pip timeout grace** | If only failure is pip timeout AND quality ≥ 80 → `passed = True` | Code that was never actually executed gets marked as passing |
| **code_fixing_node: pip-only fast path** | Sets `tests_passed: True` without re-testing | Requirements fix assumed to work without verification |
| **pipeline_self_eval_node: exception handler** | Exception → `self_eval_approved` with score -1 | Broken self-eval = automatic approval |
| **research_node: all sources fail** | Returns empty context, no error logged | Downstream nodes operate on zero research |
| **run_basic_tests()** | Always returns True | Test execution results are discarded |

### Tier 2: Failures That Are Logged But Don't Affect Flow

| Location | Behavior | Impact |
|---|---|---|
| **code_review_agent_node failure** | Returns original code, logs warning | Buggy code proceeds to testing without review |
| **architect_spec_node failure** | Sets `architect_failed` stage, continues | Code generation uses LLM-decided file plan instead of architectural spec |
| **strategy_reasoner_node failure** | Returns `strategy_fallback`, code_fixing proceeds without strategy | Fix attempts are blind (no root cause analysis) |
| **Interface contract generation failure** | Proceeds without contracts | Cross-file API mismatches likely |
| **Error memory recording failure** | `except Exception` swallowed | Lessons from this run are lost |

### Tier 3: Swallowed Exceptions in nodes.py

The file has **50+ `except Exception` blocks**. Many follow this pattern:
```python
try:
    # important operation
except Exception:
    pass  # or continue
```

Notable instances:
- Line 21: Top-level import fallback (acceptable)
- Line 249: Ollama model check (swallowed)
- Line 524: Research deep-dive failure (swallowed)
- Line 898: Solution gen perspective failure (swallowed)
- Line 1022: Critique pair failure (swallowed)
- Line 1391, 1395: Solution selection emergency fallback (acceptable for last-resort)
- Line 1918, 1996: Code gen sub-phase failures (individually swallowed)

---

## 10. RESOURCE MANAGEMENT

### Model Loading Strategy

**FallbackLLM** creates `ChatOpenAI` (for OpenRouter/Groq/OpenAI) or `ChatOllama` instances on each `ainvoke()` call, inside the retry loop. There is **no instance caching** — each LLM call creates a new HTTP client. For cloud providers this is mostly harmless (HTTP is stateless), but for Ollama it triggers model loading if the model isn't hot.

The `get_llm("profile")` convenience function calls `get_fallback_llm(profile)` which calls `get_model_manager().get_fallback_llm(profile)`, which returns a new `FallbackLLM` wrapper each time. The `FallbackLLM` itself is lightweight (just config), but the underlying `ChatOpenAI`/`ChatOllama` instances are created fresh per invocation.

### Memory Management

- **gc.collect()** is called:
  - After code_generation_node completes (in workflow_enhanced.py)
  - On error in code_generation_node
  - In model_manager when switching models (Ollama only)
- **No explicit memory limits**: There's no cap on how large `generated_code` or `research_context` can grow in state
- **State accumulation**: Multiple nodes append to `errors` and `warnings` (append-only via `operator.add`). These lists grow unboundedly across fix iterations.

### Token Tracking

`TOKEN_STATS` dict in model_manager.py tracks:
- `prompt_tokens`, `completion_tokens`, `total_tokens`, `calls`

Extraction via `_track_tokens()` which reads from LangChain response metadata. Works for OpenRouter/Groq/OpenAI but not for Ollama (Ollama doesn't return usage metadata in the same format).

### Timeout Management

Per-model timeouts via `MODEL_TIMEOUT_OVERRIDES`:
| Pattern | Timeout |
|---|---|
| deepseek-r1 | 300s |
| qwq | 240s |
| -thinking | 180s |
| compound-beta | 90s |
| qwen3-235b | 90s |
| qwen3-coder | 90s |
| flash | 30s |
| instant | 25s |
| Default | 45s |

**Weakness**: The timeout is per-LLM-call, not per-node. A node that makes 6 sequential LLM calls (e.g., code_fixing for 6 files) could take 6 × 300s = 30 minutes if using deepseek-r1. There's no node-level timeout.

### Groq Key Pool

`_GROQ_KEY_POOL` reads `GROQ_API_KEY` + `GROQ_API_KEY_1` through `GROQ_API_KEY_7` from environment. Each Groq candidate in the model config is expanded to one entry per key. Rate-limited keys (429) get a 60-second cooldown.

**Weakness**: The cooldown is stored in `_health_cache` (in-memory dict). If the process restarts, all cooldowns reset and all keys are retried — potentially hitting rate limits again immediately.

### Venv Lifecycle

`CodeExecutor` creates a venv per test run:
1. Creates `venv_dir` in temp directory
2. Installs requirements via pip (180s timeout)
3. Runs tests
4. Calls `cleanup()` to delete venv

**Weakness**: If the process crashes between step 2 and step 4, the venv is orphaned in the temp directory. There's no cleanup-on-startup mechanism.

---

## CROSS-CUTTING CONCERNS

### A. God File Problem

`nodes.py` is **4,839 lines**. It contains:
- All 11 pipeline nodes
- 315-line `_build_research_report()` helper
- 200+ lines of constants (`_IMPORT_TO_PKG`, `_STDLIB_MODULES`, shadow lists)
- Complex AST analysis logic inline in nodes
- 3 separate import validator implementations (in code_generation, code_review, code_fixing)

This creates severe maintenance risk:
- Merge conflicts on any parallel development
- SyntaxError anywhere breaks ALL nodes
- Finding a function requires searching through 4800+ lines
- Import blocks and constants are scattered throughout

### B. Validation Score Inflation

The quality scores reported by the pipeline are inflated:

1. **EnhancedValidator silently passes when tools missing**: If mypy/bandit/ruff aren't installed, each returns 100/100. The weighted score becomes 100/100 even for code with type errors and security vulns.

2. **Pip timeout grace**: Code that was never executed can score 80+ on static analysis alone and be marked as passing.

3. **`run_basic_tests()` always true**: Even if generated tests fail with assertions, the test suite result is True.

4. **Self-eval uses truncated files**: Only first 200 lines per file are evaluated. Large files with bugs past line 200 get clean evaluations.

**Net effect**: The pipeline reports quality scores of 85-99/100 on code that sometimes doesn't run at all (as documented in Session 4's "2.5/10 actual quality vs 99.2/100 validator score").

### C. Error Handling Philosophy

The codebase follows a "never crash" philosophy where every exception is caught and the pipeline continues. This is good for completion rate but bad for correctness — the pipeline will produce and potentially publish code that silently failed multiple quality gates.

A better approach would be: catch and continue for **optional** stages (research, review, spec), but **fail loudly** for **mandatory** stages (code generation, testing).

### D. Duplicated Logic

| Logic | Locations | Risk |
|---|---|---|
| Shadow file detection | 3 different sets in 3 nodes | Inconsistent filtering |
| Stdlib/third-party module list | 3 different sets | Import treated differently per context |
| Cross-file import validation | code_generation, code_fixing (and partly code_review) | Bug fixed in one location but not the other |
| Code extraction from LLM response | code_generation, code_fixing, code_review | Different regex patterns |
| Unicode sanitization (`_FIX_TYPO`) | code_generation, code_fixing | Must be kept in sync |

### E. LLM Prompt Brittleness

Every node uses custom prompt engineering with specific JSON output formats. There's no:
- Schema validation library (e.g., Pydantic models for LLM output)
- Retry-on-bad-JSON logic (some nodes have manual JSON extraction, others don't)
- Prompt versioning or A/B testing infrastructure
- Token budget management (prompts can exceed context windows for small models)

The `<think>...</think>` stripping logic (for reasoning models) is duplicated in multiple nodes rather than centralized.

---

## RECOMMENDATIONS (Priority Order)

1. **Extract nodes.py into separate files** — One file per node, shared constants in a `constants.py`, shared utilities in `node_utils.py`. This is the single highest-impact refactor.

2. **Fix validation score inflation** — Make EnhancedValidator fail (not silently pass) when tools are missing. Add a `--strict` mode that requires all 4 validators to be present.

3. **Centralize shadow/stdlib/third-party sets** — One canonical source of truth, imported everywhere.

4. **Add node-level timeouts** — Wrap each node in a timeout decorator. A single node taking 30+ minutes should be killed.

5. **Make self-eval a real gate** — Raise threshold from < 4 to < 6 and increase MAX_SELF_EVAL to 2. Alternatively, implement a non-LLM scoring function that checks concrete properties (file count, main.py runs, no stubs).

6. **Fix `git_publishing_node` shadow filter** — Apply `_SHADOW_SAVE` in ALL save paths, not just the tests-failed path.

7. **Add structured output parsing** — Use Pydantic models + LangChain's `with_structured_output()` instead of manual JSON extraction. This eliminates the regex-based code extraction and `<think>` stripping.

8. **Implement error memory pruning** — Add a max-entries cap (e.g., 500) and/or age-based expiry. Mark lessons as "addressed" when the same bug_type doesn't recur for N runs.

9. **Delete dead code** — Remove first `get_model_manager()` definition, Option 6 self-review (superseded by Node 7.5), stub modules in `specialist_agents.py`.

10. **Add integration tests** — The pipeline has unit-test stubs but no actual integration tests that run a mini-pipeline end-to-end with mocked LLMs.
