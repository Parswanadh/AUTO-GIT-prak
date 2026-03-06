# 🤖 CLAUDE.MD - Auto-GIT Session Context & System State

**Last Updated**: March 2, 2026  
**Purpose**: Comprehensive session context for AI agents working on Auto-GIT  
**Status**: System is ~90% complete, pipeline hardened with artifact stripping + silent failure fixes  

---

## 🎯 CURRENT SESSION CONTEXT (Read This First!)

### What We're Working On RIGHT NOW
**Priority**: 🔥 CRITICAL - Fixing stability issues before adding features

1. **Enhanced Validation** (✅ INTEGRATED)
   - Created: `src/utils/enhanced_validator.py` - 5-stage validation (syntax, types, security, linting)
   - Integrated: `code_testing_node` in nodes.py now uses EnhancedValidator
   - Test Results: 95/100 quality on test code (85/100 security, 96/100 lint)
   - Features:
     - Type checking via mypy
     - Security scanning via bandit (detects eval, hardcoded passwords, etc.)
     - Linting via ruff (PEP8 compliance)
     - Quality scoring (weighted: 40% syntax, 20% types, 25% security, 15% lint)
     - Auto-fix support for linting issues
   - Impact: Expected first-time correctness improvement 45% → 85%
   - Status: ✅ COMPLETE - Ready for pipeline testing

2. **VRAM Thrashing Fix** (IN PROGRESS)
   - Created: `src/utils/model_manager.py` - Keeps models loaded
   - Updated: All nodes in `src/langraph_pipeline/nodes.py` use model manager
   - Status: Code written, needs testing
   - Next: Test with real pipeline execution

3. **Pipeline Bug Fixes** (PARTIALLY COMPLETE)
   - ✅ Fixed: consensus_check_node IndexError (empty list check)
   - ✅ Fixed: problem_extraction_node NoneType errors (null checking)
   - ❌ TODO: Fix GGML assertion failures during code generation
   - ❌ TODO: Add comprehensive error handling to all nodes

4. **Resource Monitoring** (TOOL CREATED, NOT INTEGRATED)
   - Created: `src/utils/resource_monitor.py` - Tracks CPU/RAM/VRAM
   - Created: `test_with_monitoring.py` - Test script
   - Status: Needs integration into pipeline nodes
   - Next: Add monitoring checks before heavy operations

5. **End-to-End Testing** (CURRENTLY BROKEN)
   - Last test: URL shortener API - FAILED (multiple errors)
   - Fixed 2 of ~5 bugs, more remain
   - Next: Test with simple cases after bug fixes

---

## 🏗️ SYSTEM ARCHITECTURE OVERVIEW

### What Auto-GIT Does
**One-Line Summary**: Research → Multi-Agent Debate → Code Generation → GitHub Publishing

**Pipeline Flow**:
```
1. Research Node → Gathers arXiv papers + web + GitHub repos
2. Problem Extraction → Identifies novel problems from research
3. Solution Generation → 3 expert perspectives propose solutions
4. Critique Node → Each expert critiques all proposals
5. Consensus Check → Determines if more debate needed
6. Solution Selection → Picks best solution via weighted voting
7. Code Generation → Creates production-ready code
8. Validation → Checks syntax, imports, execution
9. GitHub Publishing → Creates repo, pushes code
```

### Key Technologies
- **Orchestration**: LangGraph (state machine workflow)
- **LLMs**: Ollama (local), Groq/OpenAI (cloud fallback)
- **Research**: arXiv API, DuckDuckGo, SearXNG, GitHub
- **Multi-Agent**: 3 perspectives (ML Researcher, Systems Engineer, Applied Scientist)
- **Validation**: Python AST, imports, sandbox execution
- **Storage**: JSON state, memory checkpoints

---

## 📂 PROJECT STRUCTURE (What's Where)

### Core Directories
```
src/
├── langraph_pipeline/       # Main pipeline (THIS IS THE HEART)
│   ├── workflow_enhanced.py # Pipeline orchestration & entry point
│   ├── nodes.py             # 9 pipeline nodes (research → publish)
│   └── state.py             # AutoGITState definition
│
├── agents/                  # Legacy multi-agent system (still used)
│   ├── tier2_debate/        # Debate agents (solution gen, critique)
│   └── sequential_orchestrator.py
│
├── research/                # Research capabilities
│   ├── extensive_researcher.py  # Multi-iteration research (3 rounds)
│   └── searxng_client.py        # Privacy-first search
│
├── llm/                     # LLM management
│   ├── hybrid_router.py     # Routes to best LLM (cloud vs local)
│   ├── multi_backend_manager.py # Manages Groq/OpenAI/Anthropic
│   └── semantic_cache.py    # Caches LLM responses
│
├── utils/                   # Utilities
│   ├── model_manager.py     # Prevents VRAM thrashing
│   ├── resource_monitor.py  # Tracks CPU/RAM/VRAM
│   ├── traceback_parser.py  # NEW S13: Structured error extraction
│   ├── error_pattern_db.py  # NEW S13: 12 regex auto-fix patterns
│   ├── docker_executor.py   # NEW S13: Docker sandbox execution
│   ├── incremental_compiler.py # NEW S13: Per-file validation
│   ├── code_validator.py    # Validates generated code
│   └── web_search.py        # DuckDuckGo + SearXNG
│
├── cli/                     # Command-line interfaces
│   └── claude_code_cli.py   # Claude Code style CLI (has 6 TODOs)
│
└── pydantic_agents/         # Type-safe agents (newer)
    ├── code_generator.py
    └── code_reviewer.py
```

### Entry Points
- `auto_git_interactive.py` - Interactive CLI (original, working)
- `auto_git_cli.py` - Command-line CLI (working)
- `autogit_claude.py` - Claude Code style (has TODOs, partially working)
- `test_system_integrated.py` - System diagnostic tests

### Important Config Files
- `config.yaml` - Main configuration (models, settings, MCP servers)
- `.env` - API keys (Groq, OpenAI, GitHub)
- `requirements.txt` - Python dependencies

---

## 🔧 HOW THE SYSTEM WORKS (Technical Details)

### 1. Pipeline Execution Flow

**Entry Point**: `src/langraph_pipeline/workflow_enhanced.py::run_auto_git_pipeline()`

**State Management**:
```python
class AutoGITState(TypedDict):
    idea: str                      # User's idea/requirement
    research_context: dict         # Papers, web results, GitHub repos
    problems: List[str]            # Extracted problems
    selected_problem: str          # Chosen problem to solve
    debate_rounds: List[DebateRound]  # Multi-agent debate history
    final_solution: dict           # Selected solution
    generated_code: dict           # {filename: code}
    validation_results: dict       # Validation outcomes
    github_repo: Optional[str]     # Published repo URL
    current_stage: str             # Pipeline stage tracker
    errors: List[str]              # Error accumulator
```

**Node Definitions** (in `nodes.py`):
1. `research_node()` - 3-iteration research with gap identification
2. `problem_extraction_node()` - Extract problems from research
3. `solution_generation_node()` - Multi-perspective proposals
4. `critique_node()` - Cross-examination of proposals
5. `consensus_check_node()` - Determine if more debate needed
6. `solution_selection_node()` - Pick best via weighted voting
7. `code_generation_node()` - Generate multi-file code
8. `validation_node()` - Validate syntax/imports/execution
9. `github_publishing_node()` - Push to GitHub

### 2. Model Management (JUST IMPLEMENTED)

**Problem**: Models were loading/unloading repeatedly → VRAM thrashing → crashes

**Solution**: `src/utils/model_manager.py::ModelManager`

**How It Works**:
```python
# OLD WAY (BAD - reloads every time):
llm = ChatOllama(model="qwen3:4b", temperature=0.7, base_url="http://localhost:11434")

# NEW WAY (GOOD - keeps model loaded):
llm = get_llm("balanced")  # Returns cached model instance
```

**Model Profiles**:
- `fast`: qwen3:0.6b (522MB) - Simple tasks, validation
- `balanced`: qwen3:4b (2.5GB) - Most tasks (DEFAULT)
- `powerful`: qwen2.5-coder:7b (4.7GB) - Complex code
- `reasoning`: phi4-mini:3.8b (2.5GB) - Critique, analysis

**Usage in nodes**:
```python
# In nodes.py, all LLM calls now use:
llm = get_llm("balanced")  # or "fast", "powerful", "reasoning"
```

### 3. Multi-Agent Debate System

**Perspectives** (defined in `state.py`):
1. **ML Researcher** - Theory, algorithms, research best practices
2. **Systems Engineer** - Infrastructure, scalability, production
3. **Applied Scientist** - Practical implementation, real-world use

**Debate Process**:
```
Round 1:
  - Each perspective proposes solution
  - Uses research context as grounding
  
Round 2 (Critique):
  - Each perspective critiques ALL proposals (including own)
  - Identifies strengths, weaknesses, risks
  
Round 3 (Consensus Check):
  - Calculate consensus score
  - If low consensus → another debate round
  - If high consensus → proceed to selection
  
Final:
  - Weighted voting (expertise weights: 1.0-1.3x)
  - Security expert has 1.3x weight
  - Select best solution
```

**Consensus Algorithm**:
```python
# Weighted voting
score = Σ(perspective_weight × confidence × quality_metrics)

# Weights:
ML_Researcher: 1.0
Systems_Engineer: 1.2
Security_Expert: 1.3
Applied_Scientist: 1.1
```

### 4. Research System

**ExtensiveResearcher** (3-iteration refinement):
```
Iteration 1:
  - Broad search on original idea
  - Gather initial papers/web results
  
Iteration 2:
  - LLM analyzes gaps in coverage
  - Generate refined queries
  - Target missing aspects
  
Iteration 3:
  - Synthesis and validation
  - Cross-reference findings
  - Final quality check
```

**Sources**:
- **arXiv**: Academic papers (primary source)
- **DuckDuckGo**: Web search (fallback)
- **SearXNG**: Privacy-first search (if available)
- **GitHub**: Code repositories (implementations)

### 5. Validation System (INCOMPLETE - needs work)

**Current Validation** (basic):
```python
1. Syntax Check → Python AST parsing
2. Import Check → Verify imports exist
3. Structure Check → Basic code structure
4. Execution Check → Run in sandbox
```

**Missing** (HIGH PRIORITY to add):
- Type checking (mypy)
- Security scanning (bandit)
- Linting (ruff)
- Test generation
- Coverage analysis

### 6. Resource Monitoring (JUST CREATED)

**ResourceMonitor** (`src/utils/resource_monitor.py`):
```python
monitor = ResourceMonitor()
monitor.start()  # Background thread

# Check before heavy operation
if not monitor.check_safe_to_proceed():
    monitor.wait_for_resources(timeout=60)

# Get current stats
stats = monitor.stats
# Returns: cpu_percent, ram_percent, gpu_vram_used_mb, etc.
```

**Integration Points** (TODO):
- Before research (memory intensive)
- Before code generation (VRAM intensive)
- Before validation (CPU intensive)

---

## 🐛 KNOWN BUGS & ISSUES

### Critical Bugs (Actively Fixing)

1. **GGML Assertion Failures** 🔥
   - **Where**: During solution generation or code generation
   - **Error**: `GGML_ASSERT(ctx->mem_buffer != NULL) failed`
   - **Cause**: Model memory allocation issues
   - **Status**: NOT FIXED
   - **File**: `src/langraph_pipeline/nodes.py` (solution_generation_node, code_generation_node)
   - **Fix**: Use model manager + smaller models + error handling

2. **VRAM Thrashing** 🔥
   - **Where**: Throughout pipeline
   - **Symptom**: Models loading/unloading repeatedly, VS Code crashes
   - **Cause**: Creating new ChatOllama instances every call
   - **Status**: FIX IN PROGRESS (model manager created)
   - **Files**: All nodes now use `get_llm()` instead of `ChatOllama()`
   - **Next**: Test with real pipeline

3. **Pipeline Crashes** 🔥
   - **Where**: End-to-end execution
   - **Last Test**: URL shortener API - failed at multiple stages
   - **Causes**: 
     - IndexError in consensus_check_node (FIXED)
     - NoneType in problem_extraction_node (FIXED)
     - GGML assertion failures (NOT FIXED)
   - **Status**: 2 of ~5 bugs fixed

### Known Limitations

1. **Validation is Basic** ⚠️
   - Only syntax/import checking
   - No type checking, linting, security
   - First-time correctness: 45% (should be 85%)

2. **MCP Integration Incomplete** ⚠️
   - Architecture designed, not implemented
   - 6 TODOs in `src/cli/claude_code_cli.py`:
     - Line 80: Sequential thinking LLM call
     - Line 186: MCP server startup
     - Line 203: Tool discovery
     - Line 229-230: Tool execution
     - Line 508: Command routing

3. **Error Recovery Basic** ⚠️
   - Try-catch blocks exist but limited
   - No retry logic
   - No fallback strategies
   - Errors stop pipeline

4. **Python Only** ⚠️
   - Can't generate Rust, Go, JavaScript
   - No multi-language support

---

## 📋 TODO LIST (Priority Order)

### 🔥 CRITICAL (This Week)

- [ ] **Test Model Manager**
  - Run `test_with_monitoring.py`
  - Verify VRAM stays stable
  - Measure improvement
  - File: Already created, needs testing

- [ ] **Fix GGML Assertion Failures**
  - Add error handling to solution_generation_node
  - Add fallback to smaller model on failure
  - Test with different model sizes
  - File: `src/langraph_pipeline/nodes.py`

- [ ] **Integrate Resource Monitoring**
  - Import ResourceMonitor in workflow_enhanced.py
  - Add checks before heavy nodes
  - Log metrics to analytics
  - Files: `src/langraph_pipeline/workflow_enhanced.py`, `nodes.py`

- [ ] **End-to-End Testing**
  - Test simple case: calculator
  - Test moderate case: todo app
  - Document success rate
  - Fix any new issues

### ⚠️ HIGH PRIORITY (Next 2-3 Weeks)

- [ ] **Add Type Checking (mypy)**
  - Install mypy
  - Add to validation_node
  - Configure strict mode
  - Expected: +15% error detection
  - File: `src/langraph_pipeline/nodes.py`, `src/utils/code_validator.py`

- [ ] **Add Security Scanning (bandit)**
  - Install bandit
  - Add to validation_node
  - Configure security rules
  - Expected: Detect all vulnerabilities
  - File: Same as above

- [ ] **Add Linting (ruff)**
  - Install ruff (fastest linter)
  - Add to validation_node
  - Configure PEP 8 rules
  - Expected: +20 quality points
  - File: Same as above

- [ ] **Implement Test Generation**
  - Use LLM to generate pytest tests
  - Generate for each function
  - Measure coverage
  - Expected: 0% → 80% coverage
  - Files: `src/utils/code_validator.py` (has 2 TODOs)

- [ ] **Improve Error Recovery**
  - Add retry logic with exponential backoff
  - Add fallback models
  - Add circuit breaker pattern
  - Expected: 95%+ recovery rate
  - File: `src/resilience/error_recovery.py`, all nodes

### 🟢 MEDIUM PRIORITY (1 Month)

- [ ] **Complete MCP Integration**
  - Implement MCP server process management
  - Implement JSON-RPC 2.0 client
  - Implement tool discovery
  - Implement tool execution
  - Test with 3+ MCP servers
  - File: `src/cli/claude_code_cli.py` (6 TODOs)

- [ ] **Add Performance Profiling**
  - Time each node
  - Track token usage
  - Track memory usage
  - Create performance dashboard
  - Expected: 20-30% faster
  - File: New `src/observability/profiler.py`

- [ ] **Improve Documentation**
  - "Getting Started in 5 Minutes" tutorial
  - Video walkthrough (5-10 mins)
  - Troubleshooting guide (top 10 issues)
  - FAQ (20+ questions)
  - Files: `docs/` directory

---

## 🔑 KEY FILES TO KNOW

### Most Important Files (Work Here Most Often)

1. **`src/langraph_pipeline/nodes.py`** (~8,500 lines)
   - All pipeline nodes (16 nodes)
   - WHERE: Most bugs and TODOs
   - RECENTLY: Session 13 — integrated traceback parser, error pattern DB, Docker sandbox, incremental compiler
   - NEXT: Fix pre-existing bugs (unclosed paren line 7336), implement ranks 6-10

2. **`src/langraph_pipeline/workflow_enhanced.py`** (735 lines)
   - Pipeline orchestration
   - Entry point: `run_auto_git_pipeline()`
   - WHERE: Add resource monitoring integration

3. **`src/utils/traceback_parser.py`** (240 lines)
   - NEW: Session 13
   - Parses Python tracebacks into structured ParsedError objects
   - Provides ±10 line code context around errors
   - Integrated: fix loop in nodes.py

4. **`src/utils/error_pattern_db.py`** (470 lines)
   - NEW: Session 13
   - 12 regex auto-fix patterns (missing_self, imports, encoding, etc.)
   - Fixes common errors WITHOUT LLM calls
   - Integrated: fix loop in nodes.py (runs before LLM)

5. **`src/utils/docker_executor.py`** (340 lines)
   - NEW: Session 13
   - Docker sandbox with CPU/memory/network limits
   - Falls back to local subprocess if Docker unavailable
   - Integrated: code_testing_node in nodes.py

6. **`src/utils/incremental_compiler.py`** (310 lines)
   - NEW: Session 13
   - Per-file AST validation during code generation
   - Tracks exports, detects circular deps, feeds back to next file prompt
   - Integrated: code_generation_node in nodes.py

7. **`src/utils/model_manager.py`** (200 lines)
   - Prevents VRAM thrashing
   - 4 model profiles (fast/balanced/powerful/reasoning)

8. **`config.yaml`** (426 lines)
   - Main configuration
   - Model settings, MCP servers, thresholds
   - MODIFY: When adding new features

### Test Files

1. **`test_system_integrated.py`** - System diagnostic (4 tests)
2. **`test_with_monitoring.py`** - NEW: Test with resource monitoring
3. **`test_model_setup.py`** - NEW: Test model manager setup

### Documentation Files (Keep These)

1. **`claude.md`** - THIS FILE (session context)
2. **`PIPELINE_IMPROVEMENT_PLAN.md`** - 55 free MCPs + 10 ranked improvements
3. **`BUILD_STATUS_TODO.md`** - Detailed TODO list
4. **`COMPLETE_SYSTEM_DOCUMENTATION.md`** - System docs
5. **`PROGRESS.md`** - Detailed session history
6. **`README.md`** - User-facing docs

---

## 🎓 HOW TO WORK ON AUTO-GIT (Best Practices)

### Before Making Changes

1. **Read This File** - Understand current state
2. **Check BUILD_STATUS_TODO.md** - See what's priority
3. **Run Diagnostics** - `python test_system_integrated.py --diagnostic`
4. **Check for Errors** - Use VS Code problems panel

### When Adding Features

1. **Start Small** - Test with simple cases first
2. **Use Model Manager** - Always `get_llm()`, never `ChatOllama()`
3. **Add Monitoring** - Check resources before heavy operations
4. **Handle Errors** - Try-catch with fallbacks
5. **Test Incrementally** - Don't wait until done to test

### When Fixing Bugs

1. **Reproduce First** - Confirm bug exists
2. **Find Root Cause** - Don't just patch symptoms
3. **Add Null Checks** - Many bugs from missing null checks
4. **Add Error Handling** - Try-catch + meaningful errors
5. **Test Fix** - Verify bug actually fixed

### When Testing

1. **Use Monitoring** - Run `test_with_monitoring.py`
2. **Start Simple** - Calculator, todo app first
3. **Check Resources** - Watch VRAM/RAM usage
4. **Log Everything** - Enable debug logging
5. **Document Results** - Note what worked/failed

---

## 🚀 QUICK START COMMANDS

### Activate Environment
```bash
conda activate auto-git
```

### Run Diagnostics
```bash
python test_system_integrated.py --diagnostic
```

### Test with Monitoring
```bash
python test_with_monitoring.py
```

### Run Interactive CLI
```bash
python auto_git_interactive.py
```

### Run Single Command
```bash
python auto_git_cli.py generate "Create a calculator"
```

### Check Ollama Models
```bash
ollama list
```

### Check Python Environment
```bash
conda list | grep langchain
pip list | grep ollama
```

---

## 🔍 DEBUGGING TIPS

### VRAM Issues
- Check: `ollama ps` - See what's loaded
- Monitor: Use ResourceMonitor
- Fix: Use smaller models (qwen3:4b instead of 7b)

### Pipeline Crashes
- Check: `logs/` directory for error logs
- Enable: Debug logging in config.yaml
- Test: With simple cases first

### Import Errors
- Check: `pip list` - Verify packages installed
- Fix: `pip install -r requirements.txt`
- Note: Use conda environment, not system Python

### Model Loading Slow
- Check: First load is always slow (downloads)
- Fix: Models cached after first load
- Location: `~/.ollama/models/`

### LLM Not Responding
- Check: `ollama list` - Is Ollama running?
- Start: `ollama serve` (if not running)
- Test: `ollama run qwen3:4b "Hello"`

---

## 📊 SYSTEM METRICS (Current State)

### Performance
- **Pipeline Duration**: 5-10 minutes (typical)
- **First-time Correctness**: 45% (needs improvement)
- **Auto-fix Success**: 60% (needs improvement)
- **Code Quality Score**: 55/100 (needs improvement)

### Resource Usage
- **RAM**: 4-8 GB typical
- **VRAM**: 2-5 GB (depends on model)
- **CPU**: 30-60% average
- **Disk**: ~500 MB (cached models)

### Code Statistics
- **Total Lines**: ~50,000 (src/ directory)
- **Python Files**: 150+
- **Test Files**: 20+
- **Documentation**: 10+ markdown files

### Completion Status
- **Overall**: 78% complete
- **Core Infrastructure**: 100%
- **Research**: 95%
- **Multi-Agent**: 90%
- **LLM Integration**: 85%
- **Code Generation**: 80%
- **Validation**: 45% (biggest gap)
- **CLI**: 80%
- **Documentation**: 100%

---

## 🎯 SUCCESS CRITERIA (When is it "Done"?)

### Phase 1: Stability (Current Focus)
- ✅ Pipeline completes 80%+ of time
- ✅ No crashes or VRAM issues
- ✅ Clear error messages
- ✅ Resource usage stable

### Phase 2: Quality
- ✅ First-time correctness 85%+
- ✅ Auto-fix success 92%+
- ✅ Code quality score 85/100
- ✅ Test coverage 80%+

### Phase 3: Features
- ✅ MCP integration working (3+ servers)
- ✅ Comprehensive documentation
- ✅ 20-30% faster execution
- ✅ 95%+ error recovery

### Phase 4: Scale
- ✅ Multi-language support (3+ languages)
- ✅ 100+ beta users
- ✅ Community adoption (10K+ stars)
- ✅ Commercial viability

---

## 💡 TIPS FOR NEW AI AGENTS

### Starting a Session
1. **Read claude.md first** (this file)
2. **Check BUILD_STATUS_TODO.md** for current priorities
3. **Run diagnostics** to verify system state
4. **Review recent changes** in git log

### Understanding Codebase
- **Start with**: `workflow_enhanced.py` (entry point)
- **Then read**: `nodes.py` (core logic)
- **Then explore**: `agents/`, `research/`, `llm/` (subsystems)

### Making Changes
- **Test locally first** - Don't break production
- **Use model manager** - Prevent VRAM issues
- **Add monitoring** - Track resources
- **Handle errors** - Don't crash on errors

### Common Pitfalls
- ❌ Creating new ChatOllama instances (use get_llm())
- ❌ Not checking for None values (add null checks)
- ❌ Ignoring VRAM limits (use smaller models)
- ❌ Testing with complex cases first (start simple)
- ❌ Not logging errors (add meaningful logs)

---

## 🔗 USEFUL LINKS

### Documentation
- **System Docs**: `COMPLETE_SYSTEM_DOCUMENTATION.md`
- **Build Status**: `BUILD_STATUS_TODO.md`
- **Competitive Analysis**: `COMPETITIVE_ANALYSIS_PATENT_STRATEGY.md`

### External Resources
- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **Ollama**: https://ollama.ai/
- **MCP Protocol**: https://spec.modelcontextprotocol.io

### Tools
- **Ollama Models**: https://ollama.ai/library
- **MCP Servers**: https://github.com/modelcontextprotocol/servers

---

## 📝 SESSION UPDATE LOG

> **Full session history moved to [`PROGRESS.md`](PROGRESS.md)** to keep this file focused on architecture & current state.
> 
> Latest session: **Session 13 (Mar 3, 2026)** — Free MCP catalog (55 servers) + implemented top 5 pipeline techniques: traceback parser, error pattern DB, Docker sandbox, incremental compiler. See `PIPELINE_IMPROVEMENT_PLAN.md`.

---

## 🎬 NEXT STEPS (What to Do Now)

### Immediate (Next Session)
1. **Fix pre-existing nodes.py bugs**: Unclosed paren line 7336, duplicate timeout/retry code
2. **End-to-End Test**: Run pipeline with all Session 11-13 improvements on a fresh project
3. **Measure Impact**: Target 8.5+/10 self-eval, fewer fix-loop iterations, faster error recovery

### Next Priority (Ranks 6-10 from PIPELINE_IMPROVEMENT_PLAN.md)
1. **Rank 6**: Speculative Diff-Based Editing (30-40% faster fixes)
2. **Rank 7**: Repo Map / Code Graph (cross-file consistency)
3. **Rank 8**: TDD Loop (85%+ correctness)
4. **Rank 9**: Multi-Model Ensemble (-10% error rate)
5. **Rank 10**: Semgrep SAST (security scanning)

### MCP Integration (from PIPELINE_IMPROVEMENT_PLAN.md)
1. **Tier 1**: E2B Code Sandbox, Daytona Sandbox (Docker-based)
2. **Tier 2**: Semgrep, pip-audit (security scanning)
3. **Tier 3**: Brave Search, ArXiv, Exa (research enhancement)
4. **Tier 4-8**: See PIPELINE_IMPROVEMENT_PLAN.md for full 55-server catalog

---

**Remember**: 
- System is ~90% complete
- Pipeline has **16 nodes**: requirements_extraction → research → ... → git_publishing
- Focus on CORRECTNESS (code that runs AND produces correct output)
- **SOTA integrated**: LLM-as-Judge, RAD, Reflexion, auto test gen, CoT requirements, error memory
- **Session 11**: Artifact stripper, circular import detector, SQL schema checker, 8 silent failure fixes, retry logic, fail-safe defaults
- **Session 12**: Web research + MCP strategy → `PIPELINE_IMPROVEMENT_PLAN.md`
- **Session 13**: Implemented top 5 improvements — traceback parser, error pattern DB (12 patterns), Docker sandbox, incremental compiler. All integrated into nodes.py. 55 free MCPs cataloged.
- See [`PROGRESS.md`](PROGRESS.md) for detailed session history

*Update PROGRESS.md (not this file) after each session.*
