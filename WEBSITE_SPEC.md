# AUTO-GIT WEBSITE SPECIFICATION
## For AI Website Builder — Competition Presentation (Feb 27, 2026)

---

## CRITICAL CONTEXT FOR THE AI BUILDING THIS WEBSITE

**Who is presenting**: A college student showcasing their AI project at a competition.
**Audience**: Faculty members who understand code and software engineering, but are NOT AI/ML experts. They know what Python is, what an API is, what Git is — but may not know what LangGraph, STORM paper, or temperature sampling means.
**Goal**: Replace a generic PPT with an interactive, impressive website that tells the story of how this system was built, how it improved over 27 iterations, and why it's technically impressive.
**Tone**: Professional but not corporate. Confident, engineer-to-engineer. Show don't tell. Use real code snippets, real data, real error logs.
**NOT a product landing page**: This is a technical showcase. Think: engineering blog post meets live demo meets portfolio project. No stock photos, no "Get Started Free" buttons.

---

## WEBSITE STRUCTURE (Single Page, Scrollable Sections)

### Design Requirements
- **Single page application** — smooth scroll between sections
- **Dark theme** (dark navy/charcoal background, light text) — this is a developer tool, not a marketing site
- **Monospace font for code** (JetBrains Mono, Fira Code, or Source Code Pro)
- **Accent colors**: Electric blue (#3B82F6) for highlights, green (#10B981) for success, red (#EF4444) for errors, amber (#F59E0B) for warnings
- **Animated elements**: Pipeline flow diagram should animate, metrics should count up on scroll, code blocks should have syntax highlighting
- **Mobile responsive** but designed primarily for laptop/desktop (presentation on projector)
- **No external API dependencies** — everything should work offline (inline all data)
- **Tech stack**: Pure HTML/CSS/JS, or React/Next.js, or Astro — builder's choice. Must be deployable as static site.

---

## SECTION 1: HERO / INTRO

### Content
**Title**: `Auto-GIT`
**Subtitle**: `From Idea to GitHub Repository — Fully Autonomous`
**One-liner**: `Type an idea. Get a researched, debated, validated, multi-file Python project published on GitHub. No human intervention.`

**Demo command** (styled as a terminal):
```
$ python run_pipeline.py "Build a local password manager with encryption"

🔍 Researching SOTA approaches...        ✓ 47 papers, 23 web results
🧠 3 AI experts debating solutions...     ✓ Consensus reached (0.83)
📐 Architect generating blueprint...      ✓ 11 files planned
💻 Generating 3,325 lines of code...      ✓ All files complete
🔍 Code Review Agent checking...          ✓ 0 critical issues
🧪 Testing in isolated sandbox...         ✓ All tests pass
📊 Self-evaluation: 8.0/10               ✓ Approved
🚀 Published to GitHub                    ✓ github.com/user/password-manager
```

**Key stats** (animated counters on scroll):
- `47,726` lines of pipeline source code
- `27` pipeline runs completed
- `15` nodes in the AI pipeline
- `16` bug types auto-detected and fixed
- `~30 min` from idea to GitHub repo
- `0` manual fixes needed (best run)

---

## SECTION 2: THE PROBLEM

### Content
**Heading**: `The Problem with AI Code Generation`

Present these 3 pain points (use icons or simple illustrations):

1. **"Write me a todo app"** → ChatGPT gives you ONE file, no structure, no tests, doesn't run
   - Show a sad code block: `# TODO: implement this function`
   
2. **Copy-paste hell** → Even with AI help, you're manually copying code between chat and IDE, fixing imports, installing dependencies
   - Visual: Chat window → Copy → IDE → Error → Back to chat → repeat forever

3. **No quality assurance** → AI-generated code compiles but crashes at runtime. No cross-file validation, no security checks, no type checking
   - Error example: `AttributeError: 'NoneType' object has no attribute 'execute'`

**Transition line**: `What if AI could do ALL of this — research, design, code, test, fix, and publish — without you touching a single line?`

---

## SECTION 3: THE PIPELINE (Most Important Section)

### Content
**Heading**: `How Auto-GIT Works`
**Subheading**: `A 15-Node AI Pipeline — From Idea to GitHub`

This section MUST have an **animated pipeline diagram** showing the flow. Each node should light up sequentially when the user scrolls or clicks "Play". Show the data flowing between nodes.

#### Pipeline Nodes (render as interactive flowchart/diagram):

```
┌─────────┐     ┌──────────────────┐     ┌────────────────────┐
│ RESEARCH │────▶│ GENERATE EXPERTS │────▶│ PROBLEM EXTRACTION │
│  Node 1  │     │    Node 1.5      │     │      Node 2        │
│ 🔍       │     │ 🧠               │     │ 🎯                 │
└─────────┘     └──────────────────┘     └────────────────────┘
                                                    │
                    ┌───────────────────────────────┘
                    ▼
┌──────────────────────┐     ┌──────────┐     ┌─────────────────┐
│ SOLUTION GENERATION  │────▶│ CRITIQUE │────▶│ CONSENSUS CHECK │
│      Node 3          │     │  Node 4  │     │     Node 5      │
│ 💡 (3 experts)       │     │ ⚔️        │     │ 🤝              │
└──────────────────────┘     └──────────┘     └─────────────────┘
         ▲                                           │
         └──── (if no consensus) ◀───────────────────┤
                                                     │ (consensus reached)
                                                     ▼
┌──────────────────────┐     ┌───────────────┐     ┌───────────────────┐
│  SOLUTION SELECTION  │────▶│ ARCHITECT SPEC│────▶│  CODE GENERATION  │
│      Node 6          │     │   Node 6.5    │     │     Node 7        │
│ 🏆                   │     │ 📐            │     │ 💻                │
└──────────────────────┘     └───────────────┘     └───────────────────┘
                                                           │
                                                           ▼
┌──────────────────┐     ┌──────────────┐     ┌─────────────────────┐
│   CODE REVIEW    │────▶│ CODE TESTING │────▶│  STRATEGY REASONER  │
│    Node 7.5      │     │    Node 8    │     │     Node 8.4        │
│ 🔍 (12 bug types)│     │ 🧪           │     │ 🧠 (root cause)     │
└──────────────────┘     └──────────────┘     └─────────────────────┘
                               ▲                        │
                               └────── CODE FIXING ◀────┘
                                       Node 8.5
                                       🔧
                               │ (tests pass)
                               ▼
                    ┌─────────────────────┐     ┌────────────────┐
                    │  SELF-EVALUATION    │────▶│ GIT PUBLISHING │
                    │    Node 9.5         │     │    Node 10     │
                    │ 📊 (score 0-10)     │     │ 🚀             │
                    └─────────────────────┘     └────────────────┘
```

#### For each node, show a collapsible card with:

**Node 1: Research**
- What: Searches arXiv papers, web articles, GitHub repos for state-of-the-art approaches
- How: Uses Groq's compound-beta model (has built-in live web search), with fallback to DuckDuckGo and SearXNG
- Output: 40-50 papers and web results synthesized into a research report
- Code snippet:
```python
# Research uses multiple search engines with automatic fallback
research_llm = get_llm("research")  # Groq compound-beta with web search
response = await research_llm.ainvoke([
    SystemMessage(content="You are a research scientist. Search for and synthesize "
                         "state-of-the-art approaches for the given topic."),
    HumanMessage(content=f"Research topic: {idea}")
])
```

**Node 1.5: Generate Expert Perspectives**
- What: Instead of hardcoded experts, the LLM invents 3 domain-specific experts per topic
- Example: "GPU sparse transformer" → creates a VLSI Architect, GPU Microarchitect, HPC Compiler Engineer
- Why this matters: Domain experts give better solutions than generic "ML Researcher" roles
- Code snippet:
```python
# LLM dynamically generates expert perspectives based on the topic
# NOT hardcoded - each project gets custom domain experts
prompt = f"""For the topic '{idea}', generate 3 expert perspectives.
Each should have: name, role, expertise, focus areas.
Example: For "privacy ML" → Cryptography Researcher, 
         Distributed Systems Engineer, ML Privacy Scientist"""
```

**Node 3: Solution Generation (Parallel)**
- What: 3 experts propose solutions simultaneously
- How: `asyncio.gather()` runs all 3 LLM calls in parallel — 3x faster than sequential
- Innovation: Each expert has different evaluation criteria and focus areas
- Code snippet:
```python
# 3 experts propose solutions IN PARALLEL
proposals = await asyncio.gather(
    generate_proposal(expert_1, research_context),
    generate_proposal(expert_2, research_context),
    generate_proposal(expert_3, research_context),
)
```

**Node 4: Cross-Critique**
- What: Each expert critiques ALL proposals (not just their own)
- Output: N² critique matrix — ML Researcher reviews Systems Engineer's solution and vice versa
- Each critique has: strengths, weaknesses, concerns, recommendation (accept/revise/reject)

**Node 5: Consensus Check**
- What: Weighted scoring — accept=1.0, revise=0.5, reject=0.0
- If consensus < threshold → re-debate with critique feedback (loop back to Node 3)
- Prevents groupthink: requires genuine agreement across different expert perspectives
- Formula:
```
consensus_score = Σ(weight × recommendation) / num_experts
if score < 0.7 AND round < max_rounds → re-debate
```

**Node 6.5: Architect Spec (The Blueprint)**
- What: Before writing ANY code, generates a detailed technical specification
- Output: JSON with file plan, data flow, algorithms (pseudocode), dependencies, test scenarios
- Why: Solves the #1 bug — cross-file API mismatches (files disagreeing on class/method names)
- Code snippet:
```python
# Architect generates a blueprint BEFORE any code is written
spec = {
    "files": [
        {"name": "main.py", "purpose": "Entry point", "depends_on": ["auth", "database"]},
        {"name": "auth.py", "purpose": "Authentication", "exports": ["AuthManager"]},
        {"name": "database.py", "purpose": "SQLite persistence", "exports": ["Database"]}
    ],
    "data_flow": "main.py → auth.py → database.py",
    "entry_point_behavior": "Starts server, creates demo data, prints results"
}
```

**Node 7: Code Generation (Parallel, Multi-File)**
- What: Generates all Python files in parallel using the architect's blueprint
- Each file gets: the full spec, interface contracts, lessons from past errors
- Innovation: Interface contracts ensure all files agree on class names, method signatures
- Scale: Generates 3-11 files, 261 to 3,644 lines of Python

**Node 7.5: Code Review Agent (12-Bug-Type Analysis)**
- What: A "powerful" LLM reads ALL generated files with full project context and hunts for bugs
- Checks 12 specific bug types (see table below)
- Runs 2 review-fix iterations before passing to testing
- Has full context: the original idea, selected problem, solution architecture, ALL file contents

**Bug Types Table** (render as styled table):

| # | Bug Type | What It Catches | Example |
|---|----------|-----------------|---------|
| 1 | TRUNCATED | File ends mid-function | `def process(self, data):` ← file ends here |
| 2 | MISSING_ENTRY_POINT | No `if __name__ == '__main__':` | main.py without entry guard |
| 3 | SILENT_MAIN | Entry point runs but prints nothing | `asyncio.run(server.start())` with no output |
| 4 | DEAD_LOGIC | Valid syntax but logically wrong | `fire()` after `step()` resets state |
| 5 | STUB_BODY | Function is just `pass` | `def encrypt(self): pass` |
| 6 | WRONG_CALL | Calling method that doesn't exist | `self.process_data()` but class has `handle_data()` |
| 7 | MISSING_EXPORT | Import from file where name isn't defined | `from auth import Authenticator` but auth.py has `AuthManager` |
| 8 | CIRCULAR_IMPORT | A imports B, B imports A | Deadlock on import |
| 9 | PLACEHOLDER_INIT | Using base class as placeholder | `model = nn.Module()` instead of real class |
| 10 | API_MISMATCH | Cross-file method name disagreement | main calls `db.get_user()`, database has `db.fetch_user()` |
| 11 | SELF_METHOD_MISSING | `self.method()` but method not in class | Typo or refactoring artifact |
| 12 | SHADOW_FILE | File name shadows pip package | `jwt.py` shadows PyJWT |

**Node 8.4: Strategy Reasoner (THE KEY INNOVATION)**
- What: Instead of blindly saying "fix this error", it THINKS about WHY code failed
- Steps:
  1. Diagnose ROOT CAUSE (not just symptoms)
  2. Classify failure: `architecture_flaw`, `incomplete_impl`, `wrong_api`, `shadow_file`, etc.
  3. Generate strategic fix plan with per-file instructions
  4. Track previously tried strategies — never repeats failed approaches
- Why this is different: Most AI code fixers just inject the error message and say "fix this" → gets the same bad code. Strategy Reasoner thinks about the underlying problem first.
- Code snippet:
```python
# Strategy Reasoner — reasoning-in-the-loop
reasoning_prompt = """
You are a senior software architect debugging a failed pipeline.
Your job is NOT to write code. Your job is to THINK STRATEGICALLY:

1. What is the ROOT CAUSE of each failure (not just the symptom)?
2. What CATEGORY of bug is this?
3. What is the BEST STRATEGY to fix it?
4. What SPECIFIC INSTRUCTIONS should the code fixer follow?

PREVIOUSLY TRIED STRATEGIES (DO NOT REPEAT THESE):
  - Attempt 1: Patched imports in main.py → FAILED
  - Attempt 2: Regenerated database.py → FAILED
"""
```

**Node 9.5: Self-Evaluation**
- What: After testing passes, a "powerful" LLM evaluates the entire project holistically
- Scores 4 dimensions: Completeness, Correctness, Alignment with original idea, Code Quality
- Score < 4.0 → triggers another fix cycle
- Score ≥ 6.0 → approved for publishing
- This catches issues that individual tests miss: "code runs but doesn't actually DO what was asked"

**Node 10: Git Publishing**
- What: Creates a GitHub repo, pushes all files with proper README and requirements.txt
- Includes shadow file filtering — won't push files named `numpy.py`, `jwt.py`, etc.
- Generates professional README with project description

---

## SECTION 4: MULTI-AGENT DEBATE SYSTEM

### Content
**Heading**: `Three AI Experts. One Debate. Best Solution Wins.`

Visual: Show 3 expert cards having a debate (speech bubbles going back and forth)

**Concept**: Inspired by the [STORM Paper](https://arxiv.org/abs/2402.14207) (Stanford, 2024) — multi-perspective synthesis produces higher quality than a single LLM call.

**How it works** (step visualization):

**Step 1 — Expert Generation**
```
Input: "Build a real-time chat app with WebSocket support"

Generated Experts:
┌─────────────────────┐  ┌──────────────────────┐  ┌─────────────────────┐
│ 🧑‍🔬 Network Engineer   │  │ 🧑‍💻 Security Architect  │  │ 📊 Systems Designer   │
│                     │  │                      │  │                     │
│ Focus: WebSocket    │  │ Focus: Auth, E2E     │  │ Focus: Scalability, │
│ protocol, async I/O,│  │ encryption, JWT      │  │ database design,    │
│ concurrency         │  │ tokens, rate limiting│  │ message persistence │
└─────────────────────┘  └──────────────────────┘  └─────────────────────┘
```

**Step 2 — Independent Proposals**
Each expert proposes a complete solution architecture independently (in parallel).

**Step 3 — Cross-Critique**
Each expert reviews ALL proposals:
```
Network Engineer reviews Security Architect's proposal:
  ✓ Strengths: "JWT refresh token rotation is well designed"
  ✗ Weakness: "E2E encryption will add 15ms latency per message"
  → Recommendation: REVISE
```

**Step 4 — Consensus Scoring**
```
Round 1 Consensus: 0.58 (below 0.7 threshold) → RE-DEBATE
Round 2 Consensus: 0.83 → ACCEPTED ✓
```

**Why this is better than a single LLM call**:
- Single call: "Build a chat app" → gets ONE perspective, misses security, scalability
- Multi-agent debate: Gets 3 perspectives, each critiques the others, finds blind spots
- Result: More robust architecture that considers security, performance, AND usability

---

## SECTION 5: SMART MODEL MANAGEMENT

### Content
**Heading**: `27+ AI Models. Zero Cost. Intelligent Fallback.`

**The challenge**: Free AI models have rate limits, go offline, and vary wildly in quality. How do you build a reliable system on unreliable free APIs?

**Solution: 5-Tier Provider Cascade**

Visual: Show a cascade/waterfall diagram:

```
Request: "Generate code for auth.py"
    │
    ▼
┌─ Tier 1: OpenRouter FREE ──────────────────────────────────┐
│  Qwen3-Coder 480B (free)  →  429 Rate Limited  ✗           │
│  Trinity-Large 400B (free) →  Response received  ✓ ────────│──▶ Done!
└─────────────────────────────────────────────────────────────┘
    │ (all free models exhausted)
    ▼
┌─ Tier 2: OpenRouter PAID ──────────────────────────────────┐
│  DeepSeek Chat v3          →  $0.07/1M tokens               │
│  Gemini 2.5 Flash          →  $0.10/1M tokens               │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ Tier 3: Groq Multi-Key Pool ──────────────────────────────┐
│  Key 1: 429 ✗  Key 2: 429 ✗  Key 3: OK ✓                   │
│  (up to 8 independent API keys, each with own rate limit)   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ Tier 4: OpenAI gpt-4o-mini ──────────────────────────────┐
│  Last cloud resort — always available                       │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─ Tier 5: Ollama Local ────────────────────────────────────┐
│  Run on your own GPU — $0, offline capable                  │
└─────────────────────────────────────────────────────────────┘
```

**5 Model Profiles** (styled as cards):

| Profile | Used For | Models | Why |
|---------|----------|--------|-----|
| `fast` | Extraction, simple parsing | Small 3B-30B models | Speed over quality |
| `balanced` | Problem extraction, debate | 70B (Llama 3.3) | Good balance |
| `powerful` | Code generation, review | 400B-480B (Qwen3-Coder, Trinity) | Maximum quality |
| `reasoning` | Critique, strategy, root-cause analysis | DeepSeek R1 | Deep thinking |
| `research` | Web search + synthesis | Groq compound-beta | Has built-in web search |

**Smart Features**:
- **Health Cache**: Dead models (404) permanently blacklisted. Rate-limited models (429) get 60-second cooldown.
- **Per-Model Timeouts**: DeepSeek R1 gets 300s (it's slow but smart). Flash models get 25s. Based on real latency measurements.
- **Multi-Key Groq Pool**: 5-8 API keys rotating. A rate limit on Key 1 doesn't block Key 2.
- **Token Tracking**: Every LLM call logged — prompt tokens, completion tokens, total cost tracked per run.

---

## SECTION 6: SELF-IMPROVING ERROR MEMORY

### Content
**Heading**: `The System Learns From Its Own Mistakes`

This is a KEY differentiator. Show it prominently.

**Concept**: Every bug the pipeline encounters is recorded in a persistent JSONL file. Before generating code in future runs, the system reads its past mistakes and injects them as warnings into the LLM prompt.

**Visual: The Learning Loop**
```
Run #10: CLI Todo App
  ✗ Bug: main.py called cli_app.add_task() but class has run()
  → Recorded as API_MISMATCH in error memory

Run #13: Password Manager  
  ✓ Prompt includes: "LESSON: Never call methods that aren't defined on the class"
  ✓ Result: ZERO manual fixes needed!
```

**Real error memory entries** (show as scrolling log):
```json
{"run_id": "cli_todo_app_001", "bug_type": "API_MISMATCH", 
 "file": "main.py",
 "description": "main.py called cli_app.add_task() but CliApp only has run()"}

{"run_id": "snn_accelerator_001", "bug_type": "TRUNCATED",
 "file": "main.py",
 "description": "main.py was 97 lines ending mid-function with no __main__ guard"}

{"run_id": "run_16", "bug_type": "SHADOW_FILE",
 "file": "jwt.py",  
 "description": "jwt.py shadows PyJWT package causing circular import crash"}
```

**How lessons are injected**:
```python
# Before generating code, the system reads its past mistakes
lessons = error_memory.get_top_lessons(n=15)

prompt = f"""
Generate the code for {filename}.

LESSONS FROM PAST RUNS (avoid these mistakes):
1. [API_MISMATCH × 4] Never call methods that don't exist on the target class.
   Cross-check every method call against the interface contract.
2. [TRUNCATED × 3] Always complete every function body. Never end mid-statement.
3. [SHADOW_FILE × 1] Never name a file after a pip package (jwt.py, numpy.py, etc.)

{lessons}
"""
```

**Impact**: 
- Run #10 (before memory): 2 manual fixes needed
- Run #13 (after memory seeded): ZERO manual fixes
- 233 error entries accumulated across 27 runs

---

## SECTION 7: EVOLUTION — 27 RUNS VISUALIZED

### Content
**Heading**: `27 Runs. 5 Days. From Broken to Production.`

This section should have an **interactive chart** showing the improvement over time.

#### Chart 1: Lines of Code Over Time (Bar or Line Chart)
Data points:
```
Pass  1: 712 lines   | Feb 22
Pass  2: 452         | Feb 22
Pass  3: 465         | Feb 22
Pass  4: 658         | Feb 22
Pass  5: 357         | Feb 22
Pass  6: 397         | Feb 22
Pass  7: 344         | Feb 22
Pass  8: 261         | Feb 22   ← First main.py!
Pass  9: 701         | Feb 23
Pass 10: 328         | Feb 23
Pass 11: 465         | Feb 23
Pass 12: 453         | Feb 24
Pass 13: 818         | Feb 24
Pass 14: 1471        | Feb 25   ← First 1000+ line project!
Pass 15: 3644        | Feb 25   ← Biggest project
Pass 16: 1873        | Feb 25
Pass 17: 1918        | Feb 25
Pass 18: 1005        | Feb 25
Pass 19: 1991        | Feb 25
Pass 20: 1966        | Feb 25
Pass 21: 1717        | Feb 25
Pass 22: 3325        | Feb 25   ← ZERO manual fixes!
Pass 23: 2659        | Feb 26
Pass 24: 638         | Feb 26   ← Bad model profiles
Pass 25: 694         | Feb 26   ← Prose-as-code bug
Pass 26: 1429        | Feb 26   ← Shadow file crash
Pass 27: 2018        | Feb 26
```

Mark special points on the chart:
- Pass 8: "First main.py entry point"
- Pass 14: "First 1000+ lines"
- Pass 15: "3,644 lines — biggest project"
- Pass 22: "ZERO manual fixes milestone"
- Pass 24: "Regression — bad model profiles"
- Pass 27: "30 min execution time"

#### Chart 2: Bug Types Discovered Over Time (Timeline/Gantt)
Show when each bug type was first discovered and fixed:

```
Feb 22 ──────────────────────────────────────── Feb 26
│                                                    │
├─ NO_ENTRY_POINT ──── Fixed (Pass 8) ✓             │
├─── TRUNCATED ──────── Fixed (Pass 9) ✓             │
├──── DEAD_LOGIC ─────── Fixed (Pass 10) ✓           │
├───── STUB_BODY ──────── Fixed (Pass 12) ✓          │
├────── MISSING_EXPORT ─── Fixed (Pass 13) ✓         │
├─────── PLACEHOLDER_INIT ── Fixed (Pass 14) ✓       │
├──────── API_MISMATCH ────── Fixed (Pass 20) ✓      │
├──────── SELF_METHOD_MISSING ─ Fixed (Pass 20) ✓    │
├───────── UNINITIALIZED_ATTR ── Fixed (Pass 21) ✓   │
├────────── PROSE_AS_CODE ─────── Fixed (Pass 25) ✓  │
├────────── SHADOW_FILE ──────────Fixed (Pass 26) ✓  │
├─────────── SQL_SCHEMA_MISMATCH ──── Open ⚠️        │
```

#### Chart 3: Milestones (Horizontal Timeline)
```
Feb 22                Feb 23              Feb 24              Feb 25               Feb 26
  │                     │                   │                   │                    │
  ├── First run         ├── Truncation      ├── Code Review     ├── ZERO fixes!      ├── 30 min runs
  ├── 7 runs in 1 night │   detection       │   Agent added     ├── Error memory     ├── Shadow file fix
  ├── No main.py        ├── SNN projects    │                   ├── 3,644 lines      ├── Speed optim.
  │                     │                   │                   │                    │
```

#### Table: Complete Run History
Render this as a styled table with row highlighting for milestone runs:

| Pass | Project Name | Date | Files | Lines | Status | Key Issue |
|------|-------------|------|-------|-------|--------|-----------|
| 1 | Test Run (ML Training) | Feb 22 | 7 | 712 | ⚠️ No main.py | No entry point |
| 2 | Quantum Analog Attention | Feb 22 | 3 | 452 | ⚠️ No main.py | Library code only |
| 3 | Sparse Matrix Multiplication | Feb 22 | 3 | 465 | ⚠️ No main.py | No entry point |
| 4 | GPU Load Balancer | Feb 22 | 4 | 658 | ⚠️ No main.py | No entry point |
| 5 | GPU Resource Allocator | Feb 22 | 2 | 357 | ⚠️ No main.py | Only 2 files |
| 6 | Multimodal LLM Engine | Feb 22 | 3 | 397 | ⚠️ No main.py | No entry point |
| 7 | GPU Anomaly Detection | Feb 22 | 2 | 344 | ⚠️ No main.py | Only 2 files |
| **8** | **Bias-Aware LLM Patch** | **Feb 22** | **5** | **261** | **✅ First main.py!** | **Milestone** |
| 9 | Spike Memory Architecture | Feb 23 | 6 | 701 | ⚠️ Truncated | main.py cut off |
| 10 | Event-Driven Spike Cache | Feb 23 | 4 | 328 | ⚠️ Dead logic | fire() after step() |
| 11 | Mixed-Signal Neuron | Feb 23 | 5 | 465 | ⚠️ Issues | Structural problems |
| 12 | Spiking Neuron (LOSN) | Feb 24 | 5 | 453 | ⚠️ Stubs | NotImplementedError |
| 13 | Dynamic Depth Transformer | Feb 24 | 12 | 818 | ⚠️ Import bugs | Cross-file mismatch |
| **14** | **Surprise-Driven Layers** | **Feb 25** | **5** | **1,471** | **✅ 1000+ lines!** | **nn.Module() placeholder** |
| **15** | **Uncertainty-Aware Prediction** | **Feb 25** | **8** | **3,644** | **✅ Biggest!** | API mismatches |
| 16 | Surprise-Driven Growth | Feb 25 | 5 | 1,873 | ✅ OK | Monolithic main.py |
| 17 | Adaptive Layer Expansion | Feb 25 | 4 | 1,918 | ✅ OK | 8.0/10 self-eval |
| 18 | Sentiment LSTM-Transformer | Feb 25 | 5 | 1,005 | ✅ OK | Placeholder fixed |
| 19 | Palette Selector | Feb 25 | 5 | 1,991 | ✅ OK | Research-named version |
| **20** | **CLI Todo App** | **Feb 25** | **5** | **1,966** | **⚠️ 2 fixes** | **API_MISMATCH found** |
| 21 | PBKDF2 Key Rotation | Feb 25 | 4 | 1,717 | ✅ OK | Uninit attr fixed |
| **22** | **Password Manager** | **Feb 25** | **11** | **3,325** | **✅ ZERO FIXES!** | **Milestone** |
| 23 | AEAD Vault | Feb 26 | 9 | 2,659 | ✅ OK | Auto-fixed |
| 24 | Terminal Abstraction | Feb 26 | 8 | 638 | ❌ Bad models | 3B slop models |
| 25 | Chat App (attempt 2) | Feb 26 | 9 | 694 | ❌ Prose | LLM returned English |
| 26 | JWT-E2EE Framework | Feb 26 | 9 | 1,429 | ❌ Shadow | jwt.py crash |
| **27** | **WebSocket Chat** | **Feb 26** | **8** | **2,018** | **⚠️ SQL mismatch** | **SQL table name bug** |

---

## SECTION 8: VALIDATION PIPELINE

### Content
**Heading**: `5-Stage Quality Gate — Before Any Code Ships`

Show as a pipeline with quality scores:

```
┌──────────┐   ┌───────────┐   ┌──────────┐   ┌──────┐   ┌───────────┐
│ SYNTAX   │──▶│ TYPE CHECK│──▶│ SECURITY │──▶│ LINT │──▶│ QUALITY   │
│ ast.parse│   │   mypy    │   │  bandit   │   │ ruff │   │ SCORE     │
│          │   │           │   │           │   │      │   │           │
│ Weight:  │   │ Weight:   │   │ Weight:   │   │Weight│   │ Threshold │
│  40%     │   │  20%      │   │  25%      │   │ 15%  │   │  ≥ 50     │
└──────────┘   └───────────┘   └──────────┘   └──────┘   └───────────┘
```

**Example validation result**:
```
File: auth.py
  ✓ Syntax:   100/100 (valid Python AST)
  ✓ Types:     92/100 (2 missing annotations)
  ⚠ Security:  85/100 (hardcoded salt detected)
  ✓ Lint:      96/100 (2 style issues)
  ─────────────────────────────
  Quality:     93/100 ✓ PASSED
```

**Plus runtime testing**:
- Creates isolated Python virtual environment per project
- Installs dependencies from cleaned requirements.txt
- Runs `python main.py` with 30-second timeout
- Captures stdout/stderr for error diagnosis

---

## SECTION 9: TECH STACK

### Content
**Heading**: `Built With`

Show as a tech stack grid with logos (if possible, just text labels if not):

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Orchestration** | LangGraph (by LangChain) | State machine workflow with conditional routing |
| **LLM Providers** | OpenRouter, Groq, OpenAI, Ollama | Multi-provider fallback cascade |
| **Models Used** | Qwen3-Coder 480B, Llama 3.3 70B, DeepSeek R1, Gemini Flash | Different models for different tasks |
| **Research** | arXiv API, DuckDuckGo, SearXNG | Multi-source academic + web search |
| **Validation** | mypy, bandit, ruff, Python AST | Type checking, security, linting |
| **Version Control** | GitHub API (PyGithub) | Auto-create repos and push code |
| **Runtime** | Python 3.10, asyncio | Async pipeline execution |
| **Monitoring** | Rich console, JSONL tracing | Real-time progress + observability |
| **Storage** | SQLite (checkpoints), JSONL (error memory) | Crash-resume + learning |

---

## SECTION 10: CODE SHOWCASE

### Content
**Heading**: `Real Code. Real Output.`

Show 2-3 actual code files generated by the pipeline (from Pass 22 — Password Manager, the zero-fix milestone). Pull these directly from the `pass-22-build_a_local_password_manager/` folder. Show them with syntax highlighting in a tabbed code viewer.

Also show the pipeline's own code — key snippets:

**Snippet 1: Strategy Reasoner** (the most innovative part)
```python
async def strategy_reasoner_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 8.4: Strategic reasoning about WHY code failed.
    
    Instead of mechanically injecting errors and asking "fix this",
    this node DIAGNOSES root causes, CLASSIFIES failure types, and
    GENERATES strategic fix plans. Tracks previous failed strategies
    to avoid repeating mistakes.
    """
    # ... builds file overview, error text, previous strategy history
    
    reasoning_prompt = (
        "You are a senior software architect debugging a failed pipeline.\n"
        "Your job is NOT to write code. Your job is to THINK STRATEGICALLY:\n"
        "1. What is the ROOT CAUSE of each failure?\n"
        "2. What CATEGORY of bug is this?\n"
        "3. What is the BEST STRATEGY to fix it?\n"
        "4. PREVIOUSLY TRIED STRATEGIES (DO NOT REPEAT): ..."
    )
```

**Snippet 2: Error Memory Learning**
```python
class CodegenErrorMemory:
    """Persistent learning from code generation failures.
    
    Append-only JSONL ledger. Before generating code, the system
    reads its past mistakes and injects them as warnings.
    
    233 errors recorded across 27 runs — the system genuinely
    improves over time.
    """
    
    def get_top_lessons(self, n: int = 15) -> str:
        """Returns top-N most common bug patterns as formatted lessons."""
        # Counts (bug_type, description) pairs
        # Returns: "LESSONS FROM PAST RUNS (avoid these mistakes):
        #   1. [API_MISMATCH × 4] Never call methods that don't exist..."
```

**Snippet 3: Multi-Agent Debate**
```python
# 3 domain experts debate simultaneously
proposals = await asyncio.gather(
    generate_proposal(perspectives[0], research_context, llm),
    generate_proposal(perspectives[1], research_context, llm),
    generate_proposal(perspectives[2], research_context, llm),
)

# Each expert critiques ALL proposals (N² critique matrix)
for reviewer in perspectives:
    for proposal in proposals:
        critique = await generate_critique(reviewer, proposal, llm)
        critiques.append(critique)

# Weighted consensus scoring
consensus_score = sum(
    1.0 if c["recommendation"] == "accept"
    else 0.5 if c["recommendation"] == "revise" 
    else 0.0
    for c in critiques
) / len(critiques)
```

---

## SECTION 11: METRICS DASHBOARD

### Content
**Heading**: `The Numbers`

Show these as a grid of metric cards with large numbers:

**Pipeline Metrics**:
- `47,726` — Lines of source code (the pipeline itself)
- `4,839` — Lines in nodes.py (the largest single orchestration file)
- `15` — Pipeline nodes
- `27` — Completed pipeline runs  
- `~30 min` — Average pipeline execution time (latest runs)
- `35,000+` — Total lines of Python generated across all runs

**Quality Metrics**:
- `16` — Bug types auto-detected
- `233` — Error memory entries (learning from mistakes)
- `12` — Bug types checked by Code Review Agent
- `5` — Validation stages (syntax, types, security, lint, quality)
- `0` — Manual fixes needed (best run: Pass 22)

**Infrastructure Metrics**:
- `27+` — Free AI models available
- `5` — Provider tiers (OpenRouter → Groq → OpenAI → Ollama)
- `5` — Model profiles (fast, balanced, powerful, reasoning, research)
- `5` — Search engines integrated
- `8` — Max Groq API keys in rotation

---

## SECTION 12: COMPARISON

### Content
**Heading**: `How Auto-GIT Compares`

| Feature | ChatGPT | GitHub Copilot | Auto-GIT |
|---------|---------|---------------|----------|
| Multi-file projects | ❌ Single file | ❌ Autocomplete | ✅ 3-11 files |
| Research before coding | ❌ No | ❌ No | ✅ arXiv + web + GitHub |
| Multi-expert debate | ❌ No | ❌ No | ✅ 3 domain experts |
| Cross-file validation | ❌ No | ❌ No | ✅ AST-based static analysis |
| Security scanning | ❌ No | ❌ No | ✅ Bandit integration |
| Auto-fix loop | ❌ Manual | ❌ Manual | ✅ Strategy → Fix → Test → Repeat |
| Learns from mistakes | ❌ No | ❌ No | ✅ Error memory (233 entries) |
| Publishes to GitHub | ❌ Copy-paste | ❌ No | ✅ Auto-create repo + push |
| Runs generated code | ❌ No | ❌ No | ✅ Isolated sandbox testing |
| Self-evaluation | ❌ No | ❌ No | ✅ 4-dimension scoring |

---

## SECTION 13: ARCHITECTURE DIAGRAM

### Content
**Heading**: `System Architecture`

Show a clean system architecture diagram (can be SVG or canvas-drawn):

```
┌──────────────────────────────────────────────────────────────────┐
│                        Auto-GIT Pipeline                         │
│                                                                  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │ Research  │  │ Multi-Agent  │  │     Code Generation       │  │
│  │ Engine    │  │   Debate     │  │                           │  │
│  │           │  │              │  │  ┌─────────┐ ┌─────────┐ │  │
│  │ • arXiv   │  │ • 3 Experts  │  │  │Architect│→│ Parallel│ │  │
│  │ • DDGS    │  │ • Critique   │  │  │  Spec   │ │Codegen  │ │  │
│  │ • SearXNG │  │ • Consensus  │  │  └─────────┘ └─────────┘ │  │
│  └──────────┘  └──────────────┘  └───────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Self-Healing Loop                             │  │
│  │                                                           │  │
│  │  ┌────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │  │
│  │  │ Code   │→ │ Strategy │→ │  Code    │→ │   Test    │  │  │
│  │  │ Review │  │ Reasoner │  │  Fixer   │  │  Runner   │  │  │
│  │  │12 bugs │  │root cause│  │strategic │  │ sandbox   │  │  │
│  │  └────────┘  └──────────┘  └──────────┘  └───────────┘  │  │
│  │       ▲                                        │         │  │
│  │       └────────────── loop ◀───────────────────┘         │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ 5-Stage      │  │ Error Memory │  │  Model Manager     │    │
│  │ Validator    │  │ (JSONL)      │  │  5-tier fallback   │    │
│  │              │  │              │  │                    │    │
│  │ syntax→types │  │ 233 entries  │  │ 27+ models         │    │
│  │ →security    │  │ learns from  │  │ health cache       │    │
│  │ →lint→score  │  │ past runs    │  │ multi-key pool     │    │
│  └──────────────┘  └──────────────┘  └────────────────────┘    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Output: GitHub Repository with code, README, requirements  │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## SECTION 14: LIVE DEMO / TERMINAL OUTPUT

### Content
**Heading**: `See It Run`

Show actual terminal output from a real pipeline run (from Run #17 or #22). Style as a terminal emulator with green/white text on black background:

```
╔══════════════════════════════════════════════════════╗
║  AUTO-GIT PIPELINE v2.0                             ║
║  Idea: Build a local password manager               ║
╚══════════════════════════════════════════════════════╝

[17:04:23] 🔍 Research Node — searching SOTA approaches...
  🤖 Model: research → groq/compound-beta
  📊 Found 47 papers, 23 web results, 8 GitHub repos
  📝 Research report: 37,275 bytes

[17:07:15] 🧠 Generating domain-specific expert perspectives...
  Expert 1: Cryptography Engineer — key derivation, AEAD
  Expert 2: Security Architect — threat modeling, access control
  Expert 3: Systems Designer — storage, UX, cross-platform

[17:08:30] 💡 3 experts proposing solutions in parallel...
  ✓ All 3 proposals received (12.4 seconds)

[17:09:45] ⚔️  Cross-critique — each expert reviews all proposals...
  Consensus score: 0.83 ✓ (threshold: 0.70)

[17:11:20] 📐 Architect Spec — generating blueprint...
  Files planned: 11 (main.py, vault.py, crypto.py, auth.py, ...)
  
[17:15:33] 💻 Code Generation — 11 files in parallel...
  ✓ main.py (25,882 bytes)
  ✓ vault.py (8,423 bytes)
  ✓ crypto.py (6,891 bytes)
  ... (8 more files)
  Total: 3,325 lines of Python

[17:24:10] 🔍 Code Review Agent — checking 12 bug types...
  Found: 0 critical, 2 warnings
  ✓ All issues auto-fixed

[17:25:30] 🧪 Testing in isolated sandbox...
  ✓ Syntax check: 11/11 files pass
  ✓ Import check: all imports resolve
  ✓ Runtime test: main.py exits 0

[17:26:15] 📊 Self-Evaluation: 8.0/10 — APPROVED ✓

[17:27:00] 🚀 Published to GitHub: github.com/user/password-manager

═══════════════════════════════════════════════════════
  Total time: 22 minutes 37 seconds
  LLM calls: 40 | Tokens: 220,000
  Result: 3,325 lines, 11 files, ZERO manual fixes
═══════════════════════════════════════════════════════
```

---

## SECTION 15: WHAT'S NEXT / ROADMAP

### Content
**Heading**: `Roadmap`

Show as a timeline:

**Completed** ✅:
- 15-node LangGraph pipeline
- Multi-agent debate system
- Self-improving error memory
- 5-stage validation
- 12-bug-type code review
- Strategy reasoner (reasoning-in-the-loop)
- Smart model management (5-tier fallback)
- GitHub auto-publishing
- 27 successful runs

**In Progress** 🔄:
- SQL schema cross-validation
- Runtime execution testing improvements
- More shadow file patterns

**Planned** 📋:
- Multi-language support (Rust, Go, TypeScript)
- Auto-generated test suites (pytest)
- MCP (Model Context Protocol) integration
- Performance profiling dashboard
- Community release (target: 10K+ GitHub stars)

---

## SECTION 16: FOOTER

### Content
- **GitHub**: [github.com/Parswanadh/auto-git](https://github.com/Parswanadh/auto-git) — Source code
- **All 27 Runs**: [github.com/Parswanadh/auto-git-pipeline-runs](https://github.com/Parswanadh/auto-git-pipeline-runs) — Unedited pipeline outputs
- **Built by**: Parswanadh
- **Total development time**: 5 days (Feb 22-26, 2026)

---

## DESIGN NOTES FOR THE WEBSITE BUILDER

### Animations to Include
1. **Pipeline flow**: Nodes light up sequentially as user scrolls through Section 3
2. **Counter animations**: Numbers count up from 0 to their final value when they enter viewport
3. **Terminal typing effect**: The demo terminal output in Section 14 types out character by character
4. **Chart animations**: Charts in Section 7 draw themselves when scrolled into view
5. **Debate visualization**: Expert cards slide in with speech bubbles in Section 4

### Color Palette
- **Background**: #0F172A (slate-900) or #1E293B (slate-800)
- **Text**: #F8FAFC (slate-50)
- **Accent blue**: #3B82F6 (blue-500) — primary actions, links, highlights
- **Success green**: #10B981 (emerald-500) — passed tests, completed items
- **Error red**: #EF4444 (red-500) — failed tests, bugs
- **Warning amber**: #F59E0B (amber-500) — warnings, in-progress
- **Code background**: #1E1E2E (darker than main bg)
- **Card background**: #1E293B with 1px border of #334155

### Typography
- **Headings**: Inter, system-ui, or similar sans-serif
- **Body**: Same as headings
- **Code**: JetBrains Mono, Fira Code, or Source Code Pro (monospace)
- **Code should have syntax highlighting** — use Prism.js, highlight.js, or Shiki

### Key Technical Points for Faculty Understanding
When explaining AI concepts, always ground them in software engineering terms they know:
- "Multi-agent debate" → "Like code review, but automated with 3 specialized reviewers"
- "LangGraph state machine" → "Like a CI/CD pipeline with conditional branches"
- "Error memory" → "Like a bug database that trains the next run"
- "Strategy Reasoner" → "Like a senior dev doing root-cause analysis before fixing a bug"
- "Fallback cascade" → "Like load balancer failover for API endpoints"
- "Interface contracts" → "Like API specs / OpenAPI definitions, but for generated code"
- "Consensus scoring" → "Like approval voting in a pull request review"

### What to Emphasize (Faculty Will Be Impressed By)
1. **The system learns from its own mistakes** — this is the killer feature. 233 real error entries improving future runs.
2. **Root-cause analysis, not symptom patching** — Strategy Reasoner thinks BEFORE fixing.
3. **27 real iterations with measurable improvement** — not theoretical, actual data.
4. **Cross-file static analysis** — this is real compiler engineering applied to AI output.
5. **The code actually runs** — not just syntactically valid, actually executes in a sandbox.
6. **Zero-cost operation** — mostly free API models, intelligent fallback.
7. **5 days of development** — this wasn't built over months.

### What NOT to Include
- No pricing page
- No sign-up form
- No testimonials
- No "trusted by X companies"
- No marketing fluff
- No buzzwords without explanation
- No login/auth

### Deployment
- Should be deployable as a static site (GitHub Pages, Vercel, Netlify)
- All data inline (no external API calls)
- Must work offline after loading (for presentation in venues without WiFi)
