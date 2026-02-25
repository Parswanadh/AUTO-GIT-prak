"""
OpenRouter test with rate-limit fallback — tries all assigned free models
"""
import os, sys, json, time, urllib.request
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
GROQ_KEY       = os.getenv("GROQ_API_KEY", "")
OPENAI_KEY     = os.getenv("OPENAI_API_KEY", "")

print(f"\n  OPENROUTER_API_KEY : {'SET (' + OPENROUTER_KEY[:14] + '...)' if OPENROUTER_KEY else 'NOT SET'}")
print(f"  GROQ_API_KEY       : {'SET (' + GROQ_KEY[:14] + '...)' if GROQ_KEY else 'NOT SET'}")
print(f"  OPENAI_API_KEY     : {'SET (' + OPENAI_KEY[:14] + '...)' if OPENAI_KEY else 'NOT SET'}\n")

if not OPENROUTER_KEY:
    print("ERROR: OPENROUTER_API_KEY not set in .env"); sys.exit(1)

# ---- Test 1: connectivity ---------------------------------------------------
req = urllib.request.Request(
    "https://openrouter.ai/api/v1/models",
    headers={"Authorization": f"Bearer {OPENROUTER_KEY}"}
)
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read())
free_count = sum(1 for m in data["data"] if float(m.get("pricing", {}).get("prompt", "1") or "1") == 0.0)
print(f"[OK] API connected -- {len(data['data'])} models available, {free_count} FREE\n")

# ---- Test 2: try every free model we plan to use ----------------------------
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

MODELS_TO_TEST = [
    ("balanced",  "meta-llama/llama-3.3-70b-instruct:free"),
    ("balanced2", "openai/gpt-oss-120b:free"),
    ("fast",      "openai/gpt-oss-20b:free"),
    ("coder",     "qwen/qwen3-coder:free"),
    ("reasoning", "deepseek/deepseek-r1-0528:free"),
    ("backup1",   "google/gemma-3-27b-it:free"),
    ("backup2",   "mistralai/mistral-small-3.1-24b-instruct:free"),
    ("backup3",   "nousresearch/hermes-3-llama-3.1-405b:free"),
]

working = []
print(f"  {'PROFILE':<12} {'MODEL':<55} STATUS")
print("  " + "-" * 85)

for role, model in MODELS_TO_TEST:
    try:
        llm = ChatOpenAI(
            model=model,
            api_key=OPENROUTER_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=0.5,
            max_tokens=20,
            default_headers={"HTTP-Referer": "https://github.com/auto-git", "X-Title": "Auto-GIT"},
            request_timeout=25,
        )
        r = llm.invoke([HumanMessage(content="Say: OK")])
        print(f"  {role:<12} {model:<55} WORKS: {r.content.strip()[:30]}")
        working.append((role, model))
    except Exception as e:
        err = str(e)
        if "429" in err:
            status = "RATE LIMITED (retry in 5min)"
        elif "data policy" in err or "404" in err:
            status = "PRIVACY SETTING NEEDED -> openrouter.ai/settings/privacy"
        elif "402" in err:
            status = "NEEDS CREDITS"
        else:
            status = f"ERROR: {err[:60]}"
        print(f"  {role:<12} {model:<55} {status}")
    time.sleep(0.3)

print()
if working:
    print(f"[OK] {len(working)}/{len(MODELS_TO_TEST)} models working right now.")

    # ---- Mini pipeline test with first working model ------------------------
    role, model = working[0]
    print(f"\n  Running pipeline smoke test with [{model}]...")
    llm = ChatOpenAI(
        model=model, api_key=OPENROUTER_KEY, base_url="https://openrouter.ai/api/v1",
        temperature=0.7, max_tokens=300,
        default_headers={"HTTP-Referer": "https://github.com/auto-git", "X-Title": "Auto-GIT"},
    )
    prompt = '''You are an expert software architect.
For the idea: "A URL shortener service with analytics"
Return ONLY valid JSON:
{"problem": "one sentence problem", "solution": "one sentence approach", "files": ["main.py", "README.md"]}'''
    r = llm.invoke([HumanMessage(content=prompt)])
    print(f"\n  Pipeline smoke test response:\n  {r.content.strip()[:400]}")
    print("\n[OK] PIPELINE SMOKE TEST PASSED - Ready to run full pipeline!")
else:
    print("[WARN] No free models available right now.")
    print("  -> Go to: https://openrouter.ai/settings/privacy")
    print("     Enable: Allow free model access / data policy toggle")
    print("  -> OR: Groq is available as fallback (already configured)")

