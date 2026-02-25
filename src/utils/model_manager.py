"""
Smart Model Manager for Auto-GIT - Free-First + Multi-Key Edition
==================================================================
Priority order (per profile):
  1. OpenRouter FREE models   (if OPENROUTER_API_KEY set)  - $0.00, 27+ models
  2. OpenRouter PAID models   (if OPENROUTER_PAID=true)    - ~$0.07-0.30/1M, faster
  3. Groq (multi-key pool)    (GROQ_API_KEY + KEY_1..KEY_7) - fast LPU, higher combined limits
  4. OpenAI gpt-4o-mini       (if OPENAI_API_KEY set)      - $0.15/1M, last resort
  5. Ollama local             (emergency fallback only)    - slow, OOM-prone

Multi-Groq key pool:
  Set GROQ_API_KEY, GROQ_API_KEY_1, GROQ_API_KEY_2, ... GROQ_API_KEY_7 in .env
  Each key is a separate account with its own rate limits.
  The manager expands Groq entries into one slot per key — a 429 on key-0 does NOT
  block key-1, key-2, etc, so combined TPM ≈ N × single-account limit.

Cheap paid OpenRouter models (opt-in):
  Set OPENROUTER_PAID=true in .env to unlock paid tiers after free models are
  rate-limited.  Approximate costs (Feb 2026, OpenRouter):
    deepseek/deepseek-chat-v3-0324  $0.14/1M in, $0.28/1M out  — fast, top quality
    qwen/qwen3-coder                $0.30/1M  — 480B MoE coder specialist
    deepseek/deepseek-r1-0528       $0.55/1M  — faster than :free, still cheap
    microsoft/phi-4-reasoning-plus  $0.07/1M  — small but strong reasoning
    google/gemini-2.0-flash-001     $0.10/1M  — Google's fast Gemini

Get your free Groq key:       https://console.groq.com/keys
Get your free OpenRouter key: https://openrouter.ai/settings/keys
"""

import os
import asyncio
import logging
import gc
import time
from collections import defaultdict
from typing import Optional, Dict, Any
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

# ── Resolved model tracking (profile → "provider/model_name") ─────────────────
# Populated by ModelManager.get_model() the first time each profile is resolved.
RESOLVED_MODELS: Dict[str, str] = {}

def get_resolved_models() -> Dict[str, str]:
    """Return which actual model was selected for each profile this session."""
    return dict(RESOLVED_MODELS)


# ── Token tracking ─────────────────────────────────────────────────────────────
TOKEN_STATS: Dict[str, Any] = {
    "calls": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "by_model": defaultdict(int),   # model → total_tokens
    "by_profile": defaultdict(int), # profile → total_tokens
    "call_log": [],                 # list of {model, profile, prompt, completion, total, elapsed_s}
}

# ── Timeout tracking (per session) ────────────────────────────────────────────
TIMEOUT_STATS: Dict[str, int] = {}   # model_key → number of timeouts this session

# ── Per-model timeout overrides (seconds) ─────────────────────────────
# Based on real-world latency data from OpenRouter performance dashboard:
#   deepseek-r1-0528: avg latency 101s, E2E 257s → needs 300s
#   Large MoE (235B, 400B, 480B): cold-start 30-60s + generation → needs 90s
#   Flash / instant / small models: <30s
# Matching is substring-based, longest pattern wins.
MODEL_TIMEOUT_OVERRIDES: Dict[str, int] = {
    # ── Reasoning/thinking models ─────────────────────────────────
    # deepseek-r1-0528: OpenRouter measured avg=101s, E2E=257s (ModelRun provider)
    "deepseek-r1":    300,   # entire R1 family (671B, generates long thinking chains)
    "deepseek/r1":    300,
    "-r1-0528":       300,
    "qwq":            240,   # QwQ-32B: reasoning model, ~120-200s typical
    "-thinking":      180,   # any *-thinking variant (qwen3-vl-thinking, etc.)
    "thinking-2507":  180,   # named thinking releases
    "o1-preview":     240,   # OpenAI o1-preview
    "o1-mini":        180,
    # ── Web search models ───────────────────────────────────────────────
    # compound-beta does live grounded web search — Groq infrastructure can be slow
    "compound-beta":   90,  # Groq compound-beta: web search + synthesis = 45-90s
    # ── Cheap paid models (fast by design) ────────────────────────────
    "gemini-2.0-flash":  30,   # Google Gemini Flash — very fast
    "gemini-2.5-flash":  45,   # Gemini 2.5 Flash — slightly slower
    "phi-4-reasoning":   60,   # Phi-4 reasoning — small but chain-of-thought
    "deepseek-chat":     45,   # DeepSeek Chat v3 — fast paid model
    # ── Large MoE models ──────────────────────────────────────────
    # 235B-480B MoE models: routing overhead + generation = 60-90s typical
    "qwen3-coder":     90,   # 480B MoE, 35B active
    "trinity-large":   90,  # 400B MoE, 13B active
    "step-3.5":        75,  # 196B MoE, but "flash"-class fast
    # ── Standard large models ─────────────────────────────────────────
    "llama-3.3-70b":   50,
    "llama-3.1-70b":   50,
    "qwen3-32b":       50,
    "nemotron-3-nano": 45,
    # ── Small / fast / flash models ───────────────────────────────────
    "gpt-oss-20b":     35,
    "trinity-mini":    35,  # 26B MoE, 3B active
    "llama-3.1-8b":    25,
    "gemma2:2b":       20,
    "gemma2-2b":       20,
}


def get_model_health_report() -> Dict[str, Any]:
    """
    Return a structured health report of all models encountered this session.

    Returns a dict with:
      dead        – list of permanent-404 models
      cooling     – list of (model_key, remaining_seconds) still rate-limited
      timed_out   – dict model_key → timeout count
      resolved    – dict profile → "provider/model" actually used
      token_usage – per-model token totals (top 20)
    """
    mgr = _manager  # may be None if manager never initialised
    dead: list = []
    cooling: list = []
    if mgr is not None:
        for key, (error_type, expires_at) in mgr._health_cache.items():
            if error_type == "permanent":
                dead.append(key)
            else:
                remaining = expires_at - time.time()
                if remaining > 0:
                    cooling.append({"model": key, "remaining_s": round(remaining)})
    return {
        "dead": dead,
        "cooling": cooling,
        "timed_out": dict(TIMEOUT_STATS),
        "resolved": dict(RESOLVED_MODELS),
        "token_usage": dict(
            sorted(TOKEN_STATS["by_model"].items(), key=lambda x: -x[1])[:20]
        ),
    }


def get_token_stats() -> Dict[str, Any]:
    """Return a copy of the current token stats."""
    return {
        "calls": TOKEN_STATS["calls"],
        "prompt_tokens": TOKEN_STATS["prompt_tokens"],
        "completion_tokens": TOKEN_STATS["completion_tokens"],
        "total_tokens": TOKEN_STATS["total_tokens"],
        "by_model": dict(TOKEN_STATS["by_model"]),
        "by_profile": dict(TOKEN_STATS["by_profile"]),
    }

def print_token_summary():
    """Print a formatted token-usage summary."""
    s = TOKEN_STATS
    print("\n" + "═" * 60)
    print("  📊  TOKEN USAGE SUMMARY")
    print("═" * 60)
    print(f"  Total calls   : {s['calls']}")
    print(f"  Prompt tokens : {s['prompt_tokens']:,}")
    print(f"  Output tokens : {s['completion_tokens']:,}")
    print(f"  Total tokens  : {s['total_tokens']:,}")
    if s["by_profile"]:
        print("\n  By profile:")
        for profile, n in sorted(s["by_profile"].items(), key=lambda x: -x[1]):
            print(f"    {profile:<12} {n:>8,} tokens")
    if s["by_model"]:
        print("\n  By model (top 10):")
        for model, n in sorted(s["by_model"].items(), key=lambda x: -x[1])[:10]:
            display = model if len(model) <= 50 else "…" + model[-49:]
            print(f"    {display:<50} {n:>8,}")
    # Rough cost estimate (free models = $0, groq $0, openai ~0.075/1M)
    print("═" * 60 + "\n")

logger = logging.getLogger(__name__)


def _get_env(key: str, default: str = "") -> str:
    """Get env var without triggering platform detection."""
    return os.environ.get(key, default)


# ── Groq multi-key pool ────────────────────────────────────────────────────────
# Reads GROQ_API_KEY (primary) + GROQ_API_KEY_1 … GROQ_API_KEY_7 (extra accounts).
# Each key is treated as a separate provider slot (groq_0, groq_1 …) so a 429
# on one key does NOT block the others.
_GROQ_KEY_POOL: list = []

def _init_groq_pool():
    """Populate _GROQ_KEY_POOL from env once at import time."""
    pool = []
    primary = os.environ.get("GROQ_API_KEY", "").strip()
    if primary:
        pool.append(primary)
    for i in range(1, 8):  # GROQ_API_KEY_1 … GROQ_API_KEY_7
        k = os.environ.get(f"GROQ_API_KEY_{i}", "").strip()
        if k and k not in pool:
            pool.append(k)
    _GROQ_KEY_POOL.extend(pool)

_init_groq_pool()


def _build_openrouter_model(model_name: str, temperature: float) -> BaseChatModel:
    """Build model via OpenRouter (OpenAI-compatible, many free models)."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        api_key=_get_env("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        # No max_tokens cap — each OpenRouter model enforces its own limit (200K-1M+)
        default_headers={
            "HTTP-Referer": "https://github.com/auto-git",
            "X-Title": "Auto-GIT",
        },
    )


def _build_openai_model(model_name: str, temperature: float) -> BaseChatModel:
    """Build OpenAI model (gpt-5-nano etc) — used only as paid fallback."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        api_key=_get_env("OPENAI_API_KEY"),
        # No max_tokens cap — gpt-5-nano supports 400K output natively
    )


def _build_groq_model(model_name: str, temperature: float, key_index: int = 0) -> BaseChatModel:
    """Build Groq model using the key at key_index in _GROQ_KEY_POOL.
    compound-beta has built-in web search — use higher token limit.
    """
    from langchain_groq import ChatGroq
    api_key = _GROQ_KEY_POOL[key_index] if key_index < len(_GROQ_KEY_POOL) else (
        _GROQ_KEY_POOL[0] if _GROQ_KEY_POOL else _get_env("GROQ_API_KEY")
    )
    # Groq models support 8K-131K output tokens depending on model.
    # Never cap below 32K — the model will clip to its own hard limit if needed.
    # compound-beta cap stays at 8192 (it's a search-augmented call, not just codegen).
    max_tokens = 8192 if model_name == "compound-beta" else 32_768
    return ChatGroq(
        model=model_name,
        temperature=temperature,
        api_key=api_key,
        max_tokens=max_tokens,
    )


def _build_ollama_model(model_name: str, temperature: float, base_url: str) -> BaseChatModel:
    """Build Ollama local model (last resort fallback)."""
    from langchain_ollama import ChatOllama
    return ChatOllama(
        model=model_name,
        temperature=temperature,
        base_url=base_url,
        num_ctx=32_768,    # raised from 2048 — needed to fit large code prompts
        num_predict=8_192, # raised from 1024 — allows full file generation
    )


class ModelManager:
    """
    Smart model manager with health cache, per-call timeout, and token tracking.

    Resolution order per profile (v2 — Groq first for speed):
      Groq (fast, reliable) → OpenRouter free → OpenAI gpt-5-nano (paid) → Ollama

    Health cache:
      - 404 (endpoint not found) → skip for the rest of the session  (permanent)
      - 429 (rate limited)       → skip for RATE_LIMIT_COOLDOWN seconds
      - Other retryable errors   → skip for RATE_LIMIT_COOLDOWN seconds

    Per-call timeout: CALL_TIMEOUT_S seconds (skip slow models)

    Profiles:
      fast      - cheap/quick tasks (extraction, validation)
      balanced  - most pipeline tasks (debate, critique, problem extraction)
      powerful  - code generation, architecture design
      reasoning - deep analysis, consensus scoring
    """

    CALL_TIMEOUT_S = 45            # seconds before we give up on a slow model
                                   # (code gen can legitimately take 30-40s for large files)
    RATE_LIMIT_COOLDOWN = 60       # seconds to cool down a 429'd model (1 min)

    # ── Candidate lists ───────────────────────────────────────────────────────
    # Priority strategy (Feb 2026):
    #   • research  → Groq compound-beta FIRST (unique built-in web search)
    #   • all other → openrouter/free FIRST (meta-router auto-picks best free model,
    #                 200K ctx, smart feature filtering, 27+ models in pool),
    #                 then named high-quality free models,
    #                 then Groq as reliable fast fallback.
    #
    # Key new additions:
    #   openrouter/free                    — meta-router, randomly picks best free model
    #   nvidia/nemotron-3-nano-30b-a3b:free — 30B MoE (3B active), built for agentic AI
    #   stepfun/step-3.5-flash:free        — 196B MoE (11B active), fast reasoning, 256K ctx
    #   arcee-ai/trinity-large-preview:free — 400B MoE (13B active), frontier, 128K ctx
    #   arcee-ai/trinity-mini:free         — 26B MoE (3B active), fast, 131K ctx
    # Strategy:
    #   1. Named OpenRouter free models FIRST — direct calls, no meta-routing lag,
    #      no shared rate-limit pool. Spread across many models so no single one
    #      gets hammered.
    #   2. Groq in the MIDDLE — fast LPU but tight rate limits (6K TPM / 1K RPD).
    #      Used as reliable fallback, not primary, so it stays fresh for research.
    #   3. openai/gpt-4o-mini LAST — paid, last resort only.
    #   4. "openrouter/free" meta-router REMOVED — it adds routing latency on top
    #      of inference latency; slower than calling models directly.
    #   5. ollama LOCAL LAST — only works if user has local GPU, good safety net.
    CLOUD_CONFIGS = {
        # ── fast: simple extraction, validation, consensus scoring ────────────
        # Want: small models, quick turnaround, no need for frontier quality.
        "fast": [
            # FREE tier (tried first)
            ("openrouter",      "nvidia/nemotron-3-nano-30b-a3b:free",       0.4),
            ("openrouter",      "arcee-ai/trinity-mini:free",                0.4),
            ("openrouter",      "meta-llama/llama-3.3-70b-instruct:free",    0.4),
            ("openrouter",      "stepfun/step-3.5-flash:free",               0.4),
            # PAID tier (opt-in: OPENROUTER_PAID=true) — ~$0.07-0.14/1M
            ("openrouter_paid", "microsoft/phi-4-reasoning-plus",            0.4),  # $0.07/1M, fast small reasoning
            ("openrouter_paid", "deepseek/deepseek-chat-v3-0324",            0.4),  # $0.14/1M, very fast quality
            ("openrouter_paid", "google/gemini-2.0-flash-001",               0.4),  # $0.10/1M, 1M ctx, blazing fast
            # Groq pool (expanded to groq_0, groq_1… at init time)
            ("groq",            "llama-3.1-8b-instant",                      0.4),
            ("groq",            "llama-3.3-70b-versatile",                   0.4),
            ("openai",          "gpt-4o-mini",                               0.4),
            ("ollama",          "gemma2:2b",                                 0.4),
        ],
        # ── balanced: problem extraction, solution gen, most nodes ────────────
        "balanced": [
            # FREE tier
            ("openrouter",      "nvidia/nemotron-3-nano-30b-a3b:free",       0.7),
            ("openrouter",      "meta-llama/llama-3.3-70b-instruct:free",    0.7),
            ("openrouter",      "stepfun/step-3.5-flash:free",               0.7),
            ("openrouter",      "arcee-ai/trinity-large-preview:free",       0.7),
            ("openrouter",      "qwen/qwen3-coder:free",                     0.7),
            ("openrouter",      "arcee-ai/trinity-mini:free",                0.7),
            # PAID tier (opt-in)
            ("openrouter_paid", "deepseek/deepseek-chat-v3-0324",            0.7),  # $0.14/1M, top balanced model
            ("openrouter_paid", "google/gemini-2.0-flash-001",               0.7),  # $0.10/1M, 1M ctx
            ("openrouter_paid", "qwen/qwen3-coder",                          0.7),  # $0.30/1M, paid 480B coder
            # Groq pool
            ("groq",            "llama-3.3-70b-versatile",                   0.7),
            ("groq",            "llama-3.1-8b-instant",                      0.7),
            ("openai",          "gpt-4o-mini",                               0.7),
            ("ollama",          "phi4-mini:3.8b",                            0.7),
        ],
        # ── powerful: code generation, architecture design ────────────────────
        "powerful": [
            # FREE tier
            ("openrouter",      "qwen/qwen3-coder:free",                     0.7),  # 480B code specialist
            ("openrouter",      "nvidia/nemotron-3-nano-30b-a3b:free",       0.7),
            ("openrouter",      "meta-llama/llama-3.3-70b-instruct:free",    0.7),
            ("openrouter",      "arcee-ai/trinity-large-preview:free",       0.7),
            ("openrouter",      "stepfun/step-3.5-flash:free",               0.7),
            ("openrouter",      "arcee-ai/trinity-mini:free",                0.7),
            # PAID tier (opt-in) — use for code gen when free models are rate-limited
            ("openrouter_paid", "qwen/qwen3-coder",                          0.7),  # $0.30/1M, 480B paid (faster than :free)
            ("openrouter_paid", "deepseek/deepseek-chat-v3-0324",            0.7),  # $0.14/1M, excellent coder
            ("openrouter_paid", "google/gemini-2.5-flash",                   0.7),  # $0.15/1M, fast + long ctx
            # Groq pool
            ("groq",            "llama-3.3-70b-versatile",                   0.7),
            ("openai",          "gpt-4o-mini",                               0.7),
            ("ollama",          "qwen2.5-coder:7b",                          0.7),
        ],
        # ── reasoning: critique, debate, consensus ────────────────────────────
        "reasoning": [
            # FREE tier
            ("openrouter",      "arcee-ai/trinity-large-preview:free",       0.6),
            ("openrouter",      "stepfun/step-3.5-flash:free",               0.6),
            ("openrouter",      "nvidia/nemotron-3-nano-30b-a3b:free",       0.6),
            ("openrouter",      "meta-llama/llama-3.3-70b-instruct:free",    0.6),
            # PAID tier (opt-in) — faster reasoning when R1 free is overloaded
            ("openrouter_paid", "deepseek/deepseek-r1-0528",                 0.6),  # $0.55/1M, much faster than :free
            ("openrouter_paid", "microsoft/phi-4-reasoning-plus",            0.6),  # $0.07/1M, strong small reasoner
            # Groq pool
            ("groq",            "llama-3.3-70b-versatile",                   0.6),
            ("groq",            "llama-3.1-8b-instant",                      0.6),
            ("openai",          "gpt-4o-mini",                               0.6),
            ("ollama",          "phi4-mini:3.8b",                            0.6),
        ],
        # ── research: SOTA web-grounded research ─────────────────────────────
        # ⚠️  Groq compound-beta STAYS FIRST: unique built-in live web search.
        "research": [
            ("groq",            "compound-beta",                             0.3),  # live web search
            # Fallbacks without web search
            ("openrouter",      "arcee-ai/trinity-large-preview:free",       0.5),
            ("openrouter",      "stepfun/step-3.5-flash:free",               0.5),
            ("openrouter",      "qwen/qwen3-32b:free",                       0.5),
            ("openrouter",      "meta-llama/llama-3.3-70b-instruct:free",    0.5),
            ("openrouter_paid", "deepseek/deepseek-chat-v3-0324",            0.5),  # $0.14/1M
            ("groq",            "llama-3.3-70b-versatile",                   0.5),
            ("openai",          "gpt-4o-mini",                               0.5),
            ("ollama",          "phi4-mini:3.8b",                            0.5),
        ],
    }

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self._cache: Dict[str, BaseChatModel] = {}
        self._active_provider: Optional[str] = None

        # Health cache: model_key → (error_type, expires_at)
        # error_type: "permanent" (404) or "temporary" (429)
        self._health_cache: Dict[str, tuple] = {}

        openrouter_key  = bool(_get_env("OPENROUTER_API_KEY"))
        openai_key      = bool(_get_env("OPENAI_API_KEY"))
        groq_pool_size  = len(_GROQ_KEY_POOL)
        paid_enabled    = _get_env("OPENROUTER_PAID", "").lower() in ("true", "1", "yes")

        # ── Expand Groq entries: one slot per key in the pool ─────────────────
        # Original config has ("groq", model, temp) entries.
        # We expand each into ("groq_0", model, temp), ("groq_1", model, temp) …
        # so each key has its own health-cache slot.  A 429 on key-0 won't block key-1.
        expanded: dict = {}
        for profile, candidates in self.CLOUD_CONFIGS.items():
            new_candidates = []
            for provider, model_name, temperature in candidates:
                if provider == "groq":
                    if groq_pool_size == 0:
                        continue  # no keys at all — skip
                    for ki in range(groq_pool_size):
                        new_candidates.append((f"groq_{ki}", model_name, temperature))
                elif provider == "openrouter_paid":
                    if paid_enabled and openrouter_key:
                        new_candidates.append(("openrouter", model_name, temperature))
                    # else skip — paid model, user hasn't opted in
                else:
                    new_candidates.append((provider, model_name, temperature))
            expanded[profile] = new_candidates
        # Replace class-level config with expanded per-instance copy
        self.CLOUD_CONFIGS = expanded

        logger.info("Model Manager v4 (multi-key Groq + paid OR opt-in + health cache) initialized")
        logger.info(f"  OpenRouter: {'✅ PRIMARY (27+ free models)' if openrouter_key else '❌ add OPENROUTER_API_KEY → https://openrouter.ai/settings/keys'}")
        logger.info(f"  Groq pool:  {'✅ ' + str(groq_pool_size) + ' key(s) (compound-beta web search + fast fallback)' if groq_pool_size else '❌ add GROQ_API_KEY → https://console.groq.com/keys'}")
        logger.info(f"  OR Paid:    {'✅ enabled (OPENROUTER_PAID=true)' if paid_enabled else '⚪ disabled — set OPENROUTER_PAID=true to unlock cheap paid models'}")
        logger.info(f"  OpenAI:     {'✅ (paid last-resort)' if openai_key else '⚪ not set (optional)'}")

    def _model_key(self, provider: str, model_name: str) -> str:
        return f"{provider}/{model_name}"

    def _is_healthy(self, provider: str, model_name: str) -> bool:
        """Return True if the model is not currently blacklisted."""
        key = self._model_key(provider, model_name)
        if key not in self._health_cache:
            return True
        error_type, expires_at = self._health_cache[key]
        if error_type == "permanent":
            return False   # 404 — never retry
        if time.time() < expires_at:
            return False   # still in cooldown
        # Cooldown expired — remove from cache
        del self._health_cache[key]
        return True

    def _mark_dead(self, provider: str, model_name: str, is_permanent: bool):
        """Mark a model as temporarily or permanently unavailable."""
        key = self._model_key(provider, model_name)
        if is_permanent:
            self._health_cache[key] = ("permanent", float("inf"))
            logger.warning(f"  🚫 [{key}] marked DEAD (404, will skip forever this session)")
        else:
            expires_at = time.time() + self.RATE_LIMIT_COOLDOWN
            self._health_cache[key] = ("temporary", expires_at)
            logger.info(f"  ⏳ [{key}] rate-limited, cooling down {self.RATE_LIMIT_COOLDOWN}s")

    def _get_model_timeout(self, model_name: str) -> int:
        """
        Return the per-model timeout in seconds.

        Uses MODEL_TIMEOUT_OVERRIDES (module-level dict) with substring matching.
        Longest matching pattern wins; falls back to CALL_TIMEOUT_S if no match.

        Examples
        --------
        deepseek-r1-0528:free  → 300s  (real E2E latency ~257s per OpenRouter)
        qwen3-235b-a22b:free   →  90s  (large MoE, cold start)
        step-3.5-flash:free    →  75s
        llama-3.1-8b-instant   →  25s
        nvidia/nemotron-3-nano →  45s
        """
        name_lower = model_name.lower()
        best_len = 0
        best_timeout = self.CALL_TIMEOUT_S
        for pattern, timeout in MODEL_TIMEOUT_OVERRIDES.items():
            if pattern in name_lower and len(pattern) > best_len:
                best_len = len(pattern)
                best_timeout = timeout
        return best_timeout

    def get_model(self, profile: str = "balanced") -> BaseChatModel:
        """Return best available model for the given profile (cached, synchronous)."""
        if profile not in self.CLOUD_CONFIGS:
            logger.warning(f"Unknown profile '{profile}', using 'balanced'")
            profile = "balanced"
        if profile in self._cache:
            return self._cache[profile]
        candidates = self.CLOUD_CONFIGS[profile]
        for provider, model_name, temperature in candidates:
            if not self._has_key(provider):
                continue
            if not self._is_healthy(provider, model_name):
                continue
            try:
                logger.info(f"Loading [{profile}] via {provider}: {model_name}")
                llm = self._build(provider, model_name, temperature)
                self._cache[profile] = llm
                self._active_provider = provider
                RESOLVED_MODELS[profile] = f"{provider}/{model_name}"
                logger.info(f"  ✅ [{profile}] → {provider}/{model_name}")
                return llm
            except Exception as e:
                logger.warning(f"  ⚠️ {provider}/{model_name} failed: {e}, trying next...")
                continue
        raise RuntimeError(
            f"No LLM available for profile '{profile}'. "
            "Add GROQ_API_KEY (free!) to .env: https://console.groq.com/keys"
        )

    def get_fast_model(self) -> BaseChatModel:
        return self.get_model("fast")

    def get_balanced_model(self) -> BaseChatModel:
        return self.get_model("balanced")

    def get_powerful_model(self) -> BaseChatModel:
        return self.get_model("powerful")

    def get_reasoning_model(self) -> BaseChatModel:
        return self.get_model("reasoning")

    def clear(self):
        """Clear model cache and free memory."""
        self._cache.clear()
        self._active_provider = None
        gc.collect()
        logger.info("Model cache cleared")

    def get_current_info(self) -> Dict[str, str]:
        """Get info about active provider."""
        return {
            "active_provider": self._active_provider or "none",
            "cached_profiles": list(self._cache.keys()),
            "dead_models": [k for k, (t, _) in self._health_cache.items() if t == "permanent"],
            "cooling_models": [k for k, (t, _) in self._health_cache.items() if t == "temporary"],
        }

    def _has_key(self, provider: str) -> bool:
        if provider == "openrouter":
            return bool(_get_env("OPENROUTER_API_KEY"))
        if provider == "openai":
            return bool(_get_env("OPENAI_API_KEY"))
        if provider == "groq" or provider.startswith("groq_"):
            return bool(_GROQ_KEY_POOL)  # True if any key in pool
        return True  # ollama – always available

    def _build(self, provider: str, model_name: str, temperature: float) -> BaseChatModel:
        if provider == "openrouter":
            return _build_openrouter_model(model_name, temperature)
        if provider == "openai":
            return _build_openai_model(model_name, temperature)
        if provider == "groq":
            return _build_groq_model(model_name, temperature, key_index=0)
        if provider.startswith("groq_"):
            # groq_0, groq_1, groq_2 … — extract key index
            try:
                ki = int(provider.split("_", 1)[1])
            except (IndexError, ValueError):
                ki = 0
            return _build_groq_model(model_name, temperature, key_index=ki)
        return _build_ollama_model(model_name, temperature, self.base_url)

    def get_fallback_llm(self, profile: str = "balanced") -> "FallbackLLM":
        """Return a FallbackLLM that retries the full candidate list at call-time."""
        if profile not in self.CLOUD_CONFIGS:
            profile = "balanced"
        return FallbackLLM(self, profile)


def _is_retryable(exc: Exception) -> bool:
    """Return True if this is a skip-and-retry error (rate limit, quota, 404, etc.)."""
    msg = str(exc).lower()
    return any(s in msg for s in [
        "429", "402", "404", "524", "503", "502", "529",
        "rate limit", "rate_limit", "ratelimit",
        "data policy", "spend limit", "temporarily",
        "quota", "too many requests", "overloaded",
        "timeout", "timed out", "context deadline",
        "no endpoints found",
        "decommissioned", "deprecated", "no longer supported",
        "connection error", "connection reset", "connection refused",
        "connectionerror", "remotedisconnected", "broken pipe",
        "network", "ssl", "eof occurred",
    ])

def _is_permanent_error(exc: Exception) -> bool:
    """Return True if this is a permanent 'model does not exist' error (404)."""
    msg = str(exc).lower()
    return any(s in msg for s in ["404", "no endpoints found", "model not found"])


class FallbackLLM:
    """
    Inference-time fallback wrapper with health cache, timeout, and token tracking.

    - Skips permanently dead models (404) forever
    - Skips rate-limited models for RATE_LIMIT_COOLDOWN seconds
    - Times out slow models after CALL_TIMEOUT_S seconds
    - Accumulates token usage in global TOKEN_STATS
    """

    def __init__(self, manager: "ModelManager", profile: str):
        self.manager = manager
        self.profile = profile

    async def ainvoke(self, messages, **kwargs):
        candidates = self.manager.CLOUD_CONFIGS.get(self.profile, [])
        last_exc: Optional[Exception] = None
        t0_total = time.time()

        # Outer retry loop: if ALL models fail with network errors, wait and retry
        for _network_attempt in range(3):
            if _network_attempt > 0:
                wait = 30 * _network_attempt
                logger.warning(
                    f"  🌐 Network error on all models, waiting {wait}s before retry "
                    f"{_network_attempt}/2..."
                )
                await asyncio.sleep(wait)

            _all_network = True   # flip to False if any non-network error occurs
            for provider, model_name, temperature in candidates:
                if not self.manager._has_key(provider):
                    continue
                if not self.manager._is_healthy(provider, model_name):
                    continue

                t0 = time.time()
                try:
                    logger.debug(f"  [{self.profile}] trying {provider}/{model_name}…")
                    llm = self.manager._build(provider, model_name, temperature)

                    # Per-model dynamic timeout (reasoning models need 300s, flash need 25s)
                    _timeout = self.manager._get_model_timeout(model_name)
                    response = await asyncio.wait_for(
                        llm.ainvoke(messages, **kwargs),
                        timeout=_timeout,
                    )
                    elapsed = time.time() - t0

                    # ── Token tracking ───────────────────────────────────
                    _track_tokens(provider, model_name, self.profile, response, elapsed)

                    # ── Track resolved model ─────────────────────────────
                    is_first_call = self.profile not in RESOLVED_MODELS
                    RESOLVED_MODELS[self.profile] = f"{provider}/{model_name}"
                    if is_first_call:
                        try:
                            from rich.console import Console as _RichConsole
                            _RichConsole().print(
                                f"  [dim]🤖 [{self.profile}] → [bold]{provider}/{model_name}[/bold][/dim]"
                            )
                        except Exception:
                            pass
                    logger.info(f"  ✅ [{self.profile}] {provider}/{model_name} ({elapsed:.1f}s)")
                    return response

                except asyncio.TimeoutError:
                    elapsed = time.time() - t0
                    _timeout_used = self.manager._get_model_timeout(model_name)
                    logger.warning(
                        f"  ⏱️ [{self.profile}] {provider}/{model_name} timed out after {elapsed:.0f}s (limit={_timeout_used}s), skipping"
                    )
                    _mkey = self.manager._model_key(provider, model_name)
                    TIMEOUT_STATS[_mkey] = TIMEOUT_STATS.get(_mkey, 0) + 1
                    last_exc = asyncio.TimeoutError(f"{provider}/{model_name} timed out")
                    _all_network = False
                    continue

                except Exception as exc:
                    if _is_retryable(exc):
                        is_perm = _is_permanent_error(exc)
                        self.manager._mark_dead(provider, model_name, is_permanent=is_perm)
                        logger.warning(
                            f"  ⚠️ [{self.profile}] {provider}/{model_name} skipped "
                            f"({'dead' if is_perm else '429/net'}: {str(exc)[:70]})"
                        )
                        last_exc = exc
                        # Only keep _all_network=True if this looks like a connection error
                        if not any(s in str(exc).lower() for s in
                                   ["connection", "network", "ssl", "remotedisconnected",
                                    "broken pipe", "eof"]):
                            _all_network = False
                        continue
                    raise  # hard non-retryable error — propagate

            # All candidates exhausted — only retry outer loop on pure network failure
            if not _all_network or last_exc is None:
                break

        raise RuntimeError(
            f"All models for profile '{self.profile}' exhausted after "
            f"{time.time()-t0_total:.1f}s. Last error: {last_exc}"
        )


def _track_tokens(provider: str, model_name: str, profile: str, response, elapsed: float):
    """Extract and accumulate token usage from an LLM response."""
    try:
        usage = {}
        # LangChain stores usage in different places depending on provider
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            # LangChain v0.3+ UsageMetadata is a TypedDict (plain dict),
            # older versions were dataclass objects — handle both
            if isinstance(um, dict):
                usage = {
                    "prompt_tokens":     um.get("input_tokens",  0) or 0,
                    "completion_tokens": um.get("output_tokens", 0) or 0,
                    "total_tokens":      um.get("total_tokens",  0) or 0,
                }
            else:
                usage = {
                    "prompt_tokens":     getattr(um, "input_tokens",  0) or 0,
                    "completion_tokens": getattr(um, "output_tokens", 0) or 0,
                    "total_tokens":      getattr(um, "total_tokens",  0) or 0,
                }
        elif hasattr(response, "response_metadata"):
            rm = response.response_metadata or {}
            tu = rm.get("token_usage") or rm.get("usage") or {}
            if isinstance(tu, dict):
                usage = {
                    "prompt_tokens":     tu.get("prompt_tokens",     tu.get("input_tokens",  0)),
                    "completion_tokens": tu.get("completion_tokens", tu.get("output_tokens", 0)),
                    "total_tokens":      tu.get("total_tokens",      0),
                }

        pt = usage.get("prompt_tokens", 0) or 0
        ct = usage.get("completion_tokens", 0) or 0
        tt = usage.get("total_tokens", 0) or (pt + ct)

        TOKEN_STATS["calls"] += 1
        TOKEN_STATS["prompt_tokens"] += pt
        TOKEN_STATS["completion_tokens"] += ct
        TOKEN_STATS["total_tokens"] += tt
        TOKEN_STATS["by_model"][f"{provider}/{model_name}"] += tt
        TOKEN_STATS["by_profile"][profile] += tt
        TOKEN_STATS["call_log"].append({
            "model": f"{provider}/{model_name}",
            "profile": profile,
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": tt,
            "elapsed_s": round(elapsed, 2),
        })
    except Exception:
        # Never crash the pipeline due to tracking
        TOKEN_STATS["calls"] += 1


# ── Singleton ──────────────────────────────────────────────────────────────

_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Return the global ModelManager singleton."""
    global _manager


def get_profile_primary(profile: str) -> str:
    """Return a short label showing the first available candidate for a profile."""
    configs = ModelManager.CLOUD_CONFIGS.get(profile, [])
    openrouter_key = bool(os.environ.get("OPENROUTER_API_KEY"))
    openai_key     = bool(os.environ.get("OPENAI_API_KEY"))
    groq_key       = bool(_GROQ_KEY_POOL)
    paid_enabled   = os.environ.get("OPENROUTER_PAID", "").lower() in ("true", "1", "yes")
    def _has(prov):
        if prov == "openrouter":    return openrouter_key
        if prov == "openrouter_paid": return openrouter_key and paid_enabled
        if prov == "openai":        return openai_key
        if prov == "groq" or prov.startswith("groq_"): return groq_key
        return True
    for provider, model_name, _ in configs:
        if _has(provider):
            return f"{provider}/{model_name}"
    return "(no model available)"


def get_model_manager() -> ModelManager:
    """Return the global ModelManager singleton."""
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager


def get_fallback_llm(profile: str = "balanced") -> "FallbackLLM":
    """
    Return a FallbackLLM for the given profile.

    Retries ALL candidate models at inference time on rate-limit / quota / 404
    errors. Dead models are cached in the session health cache so they're not
    retried on subsequent calls.
    """
    return get_model_manager().get_fallback_llm(profile)


# Re-export for convenience
__all__ = [
    "get_model_manager",
    "get_fallback_llm",
    "get_resolved_models",
    "get_profile_primary",
    "get_token_stats",
    "get_model_health_report",
    "print_token_summary",
    "TOKEN_STATS",
    "TIMEOUT_STATS",
]
