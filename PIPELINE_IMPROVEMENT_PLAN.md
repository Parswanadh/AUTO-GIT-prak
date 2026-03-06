# 🚀 Auto-GIT Pipeline Improvement Plan
## Web Research Results + MCP Integration Strategy (FREE & LOCAL-ONLY)

**Created**: March 2, 2026  
**Updated**: March 3, 2026 — Expanded to 55 FREE/self-hosted MCPs + ranked technique improvements  
**Current State**: Pipeline ~90% complete, 16 nodes, Sessions 10-12 hardening complete

---

## 📊 Current Pipeline Strengths (What We Already Have)

| Feature | Source | Status |
|---------|--------|--------|
| LLM-as-Judge scoring | MT-Bench/Zheng 2023 | ✅ Integrated |
| Reflexion rollback | Shinn 2023 | ✅ Integrated |
| RAD web search enrichment | SWE-Agent style | ✅ Integrated |
| Auto test generation | AlphaCode/CodeChain | ✅ Integrated |
| CoT requirements extraction | Wei 2022 | ✅ Integrated |
| Error memory across runs | — | ✅ Integrated |
| Contract enforcement via AST | — | ✅ Integrated |
| Cross-file context in fix loop | — | ✅ Integrated |
| XML artifact stripping | Session 11 | ✅ Integrated |
| Circular import detector | Session 11 | ✅ Integrated |
| SQL schema checker | Session 11 | ✅ Integrated |
| 8 silent failure fixes | Session 11 | ✅ Integrated |
| Fix loop retry logic | Session 11 | ✅ Integrated |
| Multi-model parallel gen | OpenRouter | ✅ Integrated |
| Structured output enforcement | Session 13 | ✅ Integrated |
| Traceback parsing + smart context | Session 13 | ✅ Integrated |
| Error pattern auto-fix database | Session 13 | ✅ Integrated |
| Docker sandbox execution | Session 13 | ✅ Integrated |
| Incremental compilation feedback | Session 13 | ✅ Integrated |

---

## 🆓 COMPLETE FREE & LOCALLY-HOSTABLE MCP SERVER CATALOG (55 Servers)

All servers below are 100% free — open-source, self-hosted, no paid API keys required.

### 🎯 TIER 1: CRITICAL FOR PIPELINE (Sandbox + Execution)

| # | Server | Repo | Why |
|---|--------|------|-----|
| 1 | **Docker MCP** | `ckreiling/mcp-server-docker` | Manage containers for sandboxed code execution |
| 2 | **code-sandbox-mcp** | `Automata-Labs-team/code-sandbox-mcp` | Purpose-built Docker sandboxes for LLM code |
| 3 | **Onyx MCP Sandbox** | `avd1729/Onyx` | Multi-language Docker sandbox (Py/Java/C/JS/Rust) |
| 4 | **ipybox** | `gradion-ai/ipybox` | IPython + Docker stateful execution sandbox |
| 5 | **Filesystem MCP** | Official `server-filesystem` | Secure file operations with access controls |
| 6 | **Git MCP** | Official `server-git` | Git operations via MCP protocol |
| 7 | **Node Code Sandbox** | `alfonsograziano/node-code-sandbox-mcp` | Docker JS sandbox with npm deps |
| 8 | **Microsandbox** | `microsandbox/microsandbox` | Self-hosted AI code execution platform |

### 🔍 TIER 2: SECURITY & CODE QUALITY

| # | Server | Repo | Why |
|---|--------|------|-----|
| 9 | **Semgrep MCP** | `semgrep/mcp` | FREE SAST scanning (2000+ rules) |
| 10 | **SonarQube MCP** | `sapientpants/sonarqube-mcp-server` | Code quality (Community Ed. FREE) |
| 11 | **BoostSecurity MCP** | `boost-community/boost-mcp` | Dependency vulnerability detection |
| 12 | **vulnicheck** | `andrasfe/vulnicheck` | Python package CVE scanner |
| 13 | **OSV MCP** | `StacklokLabs/osv-mcp` | Open Source Vulnerability database |
| 14 | **vet (SafeDep)** | `safedep/vet` | AI package vetting (Docker/binary) |
| 15 | **CVE Intelligence** | `gnlds/mcp-cve-intelligence-server-lite` | Multi-source CVE data |

### 🌐 TIER 3: RESEARCH & WEB

| # | Server | Repo | Why |
|---|--------|------|-----|
| 16 | **SearXNG MCP** | `ihor-sokoliuk/mcp-searxng` | Self-hosted privacy search |
| 17 | **Free Web Search** | `pskill9/web-search` | No API key needed at all! |
| 18 | **Fetch MCP** | Official `server-fetch` | Web content fetching |
| 19 | **html2md-mcp** | `sunshad0w/html2md-mcp` | HTML→Markdown (90-95% reduction) |
| 20 | **ArXiv MCP** | `blazickjp/arxiv-mcp-server` | Academic paper access |
| 21 | **OneCite** | `HzaCode/OneCite` | Citation management |

### 🧠 TIER 4: KNOWLEDGE & MEMORY

| # | Server | Repo | Why |
|---|--------|------|-----|
| 22 | **Memory MCP** | Official `server-memory` | Knowledge graph persistence |
| 23 | **Sequential Thinking** | Official `server-sequentialthinking` | Reflective problem-solving |
| 24 | **Basic Memory** | `basicmachines-co/basic-memory` | Local semantic graph |
| 25 | **Chroma MCP** | `privetin/chroma` | Vector DB (we use ChromaDB) |
| 26 | **Local FAISS MCP** | `nonatofabio/local_faiss_mcp` | Local vector search |
| 27 | **Local RAG MCP** | `shinpr/mcp-local-rag` | No-Docker doc search |

### 🤖 TIER 5: CODING AGENTS & DEV TOOLS

| # | Server | Repo | Why |
|---|--------|------|-----|
| 28 | **Language Server MCP** | `isaacphi/mcp-language-server` | Semantic code intelligence |
| 29 | **code-context-provider** | `AB498/code-context-provider-mcp` | Tree-sitter code analysis |
| 30 | **CodeGraphContext** | `Shashankss1205/CodeGraphContext` | Code→graph database |
| 31 | **code-to-tree** | `micl2e2/code-to-tree` | Universal AST parser |
| 32 | **DesktopCommander** | `wonderwhy-er/DesktopCommanderMCP` | File/terminal management |
| 33 | **code-executor** | `bazinga012/mcp_code_executor` | Python in conda sandbox |
| 34 | **mcp-run-python** | `pydantic/pydantic-ai/mcp-run-python` | Pyodide sandbox (no Docker) |
| 35 | **Blind Auditor** | `Sim-xia/Blind-Auditor` | Self-correcting AI |
| 36 | **Vibe Check** | `PV-Bhat/vibe-check-mcp-server` | Agent oversight |

### 🧪 TIER 6: TESTING & BROWSER AUTOMATION

| # | Server | Repo | Why |
|---|--------|------|-----|
| 37 | **Playwright MCP** | `microsoft/playwright-mcp` | Browser automation (27K stars) |
| 38 | **browser-use MCP** | `co-browser/browser-use-mcp-server` | Dockerized Playwright + VNC |
| 39 | **WebEvalAgent** | `Operative-Sh/web-eval-agent` | Autonomous web testing |
| 40 | **Locust MCP** | `QAInsights/locust-mcp-server` | Load testing |

### 🗄️ TIER 7: DATABASES

| # | Server | Repo | Why |
|---|--------|------|-----|
| 41 | **SQLite MCP** | Official `server-sqlite` | SQLite operations |
| 42 | **PostgreSQL MCP** | `crystaldba/postgres-mcp` | Postgres (Docker free) |
| 43 | **MySQL MCP** | `designcomputer/mysql_mcp_server` | MySQL (Docker free) |
| 44 | **MongoDB Lens** | `furey/mongodb-lens` | Full MongoDB |
| 45 | **Qdrant MCP** | `qdrant/mcp-server-qdrant` | Vector search engine |

### 📂 TIER 8: ADDITIONAL FREE UTILITIES

| # | Server | Repo | Why |
|---|--------|------|-----|
| 46 | **Everything MCP** | Official `server-everything` | Reference/test server |
| 47 | **Docker Compose MCP** | `0xshariq/docker-mcp-server` | Full Docker orchestration |
| 48 | **MCPShell** | `inercia/mcpshell` | Safe shell execution |
| 49 | **Console Automation** | `ooples/mcp-console-automation` | 40 terminal tools |
| 50 | **Jenkins MCP** | `avisangle/jenkins-mcp-server` | CI/CD (self-hosted) |
| 51 | **ADR Analysis** | `tosin2013/mcp-adr-analysis-server` | Architecture decisions |
| 52 | **Devcontainer MCP** | `AI-QL/mcp-devcontainers` | Dev container generation |
| 53 | **n8n MCP** | `leonardsellem/n8n-mcp-server` | Workflow automation |
| 54 | **Jupyter MCP** | `datalayer/jupyter-mcp-server` | Notebook integration |
| 55 | **Obsidian MCP** | `calclavia/mcp-obsidian` | Markdown knowledge base |

---

## 🏆 RANKED PIPELINE TECHNIQUE IMPROVEMENTS (Implemented)

| Rank | Technique | Impact | Status |
|------|-----------|--------|--------|
| 1 | Structured Output Enforcement | Eliminates parsing failures | ✅ Implemented |
| 2 | Traceback Parsing + Smart Context | +15-20% fix success | ✅ Implemented |
| 3 | Error Pattern Auto-Fix Database | Instant 40%+ recurring fixes | ✅ Implemented |
| 4 | Docker Sandbox Execution | Safe code execution | ✅ Implemented |
| 5 | Incremental Compilation Feedback | Prevents cascading errors | ✅ Implemented |
| 6 | Speculative Diff-Based Editing | 30-40% faster fixes | 🟡 Next |
| 7 | Repo Map / Code Graph | Cross-file consistency | 🟡 Next |
| 8 | TDD Loop | 85%+ correctness | 🔴 Future |
| 9 | Multi-Model Ensemble | -10% error rate | 🔴 Future |
| 10 | Semgrep SAST | Security scanning | 🟡 Next |

---

*All 55 MCP servers listed above are FREE and locally hostable. No paid API keys required.*
