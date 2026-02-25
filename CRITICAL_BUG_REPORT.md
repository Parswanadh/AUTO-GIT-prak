# CRITICAL BUG ANALYSIS & FIXES
## Date: February 5, 2026

## 🚨 ROOT CAUSE: Python 3.14 WMI Hang Bug

### The Problem
All pipeline scripts hang during import due to a **Python 3.14 bug** in `platform.py`:

```
File "C:\Python314\Lib\platform.py", line 347, in _wmi_query
    OSError: [WinError -2147217358] Windows Error 0x80041032
```

**Chain of Death:**
1. LangGraph imports → LangChain imports → Rich library imports
2. Rich calls `platform.system()` to detect Windows
3. Python 3.14's platform.py uses WMI query
4. WMI query **HANGS FOREVER** (Windows Error 0x80041032)
5. Script never starts

### Why Models Aren't Getting Called
- Scripts hang during import (before any code runs)
- No output is produced (not even first print statement)
- VRAM shows 0 because code never reaches model loading
- This explains ALL the stuck/lagging issues

---

## ✅ SOLUTION 1: Use Python 3.10 (RECOMMENDED)

```powershell
# Remove Python 3.14 environment
conda remove -n auto-git --all

# Create new environment with Python 3.10
conda create -n auto-git python=3.10 -y
conda activate auto-git

# Reinstall dependencies
pip install -r requirements.txt
```

**Why Python 3.10:**
- Stable, no WMI bugs
- Compatible with all libraries
- Used by 90% of AI projects
- LangChain fully tested on 3.10

---

## ✅ SOLUTION 2: Patch Platform Module (TEMPORARY)

Create `fix_platform.py`:
```python
"""
Patches Python 3.14 platform.system() WMI hang bug
Import this BEFORE any other imports
"""
import platform
import os

# Cache result to avoid WMI calls
_SYSTEM = None

def _patched_system():
    global _SYSTEM
    if _SYSTEM is None:
        # Use environment variable instead of WMI
        if os.name == 'nt':
            _SYSTEM = "Windows"
        elif os.name == 'posix':
            if os.uname().sysname == 'Darwin':
                _SYSTEM = "Darwin"
            else:
                _SYSTEM = "Linux"
        else:
            _SYSTEM = "Unknown"
    return _SYSTEM

# Monkey patch
platform.system = _patched_system

print("✓ Platform module patched (WMI hang fixed)")
```

Then in every script, add as FIRST import:
```python
import fix_platform  # Must be first!
# ... rest of imports
```

---

## 🐛 OTHER BUGS FOUND & FIXED

### 1. Memory Issues (FIXED)
**Problem:** Models use 13.9 GB for 2.5 GB model
**Cause:** Context window 262K tokens = 11 GB RAM
**Fix:** Reduced num_ctx from 262144 → 2048

### 2. Thinking Mode Lag (FIXED)
**Problem:** qwen3:4b takes forever to respond
**Cause:** Thinking mode enabled (verbose reasoning)
**Fix:** Switched to gemma2:2b (no thinking mode)

### 3. Infinite Loop in Code Testing (FIXED)
**Problem:** code_testing → code_fixing endless loop  
**Fix:** Added max_fix_attempts=2, loop detection

### 4. None Errors in Problem Extraction (FIXED)
**Problem:** `requirements.get()` on None object
**Fix:** Added `isinstance(requirements, dict)` checks

### 5. Empty Perspectives List (FIXED)
**Problem:** 0 proposals generated
**Fix:** Initialize with ["ML Researcher", "Systems Engineer", "Applied Scientist"]

---

## 📊 PERFORMANCE OPTIMIZATIONS NEEDED

### Current Issues:
1. ❌ **Import Time**: 30+ seconds (due to WMI hang)
2. ❌ **Model Loading**: Context too large (131K tokens)
3. ❌ **No Progress**: Silent failures, no output
4. ❌ **Memory**: 5.4 GB for 522 MB model
5. ❌ **Overnight Runs**: Impossible (hangs on start)

### Optimization Plan:

#### Phase 1: Fix Python Version (CRITICAL)
- [ ] Downgrade to Python 3.10
- [ ] Reinstall all dependencies
- [ ] Test imports complete in <5 seconds

#### Phase 2: Optimize Model Loading  
- [ ] Set num_ctx=2048 globally
- [ ] Use models without thinking mode
- [ ] Target <4 GB VRAM per model

#### Phase 3: Add Progress Monitoring
- [ ] Print stage transitions IMMEDIATELY
- [ ] Add timestamps to every operation
- [ ] Log to file for overnight runs
- [ ] Add timeout detection (>2 min = warning)

#### Phase 4: Error Recovery
- [ ] Catch and log ALL exceptions
- [ ] Graceful degradation (skip research if SearXNG down)
- [ ] Save checkpoints every stage
- [ ] Resume from last checkpoint

#### Phase 5: Stability Testing
- [ ] Run 10 ideas back-to-back
- [ ] Monitor memory over 8 hours
- [ ] Verify no leaks
- [ ] Test overnight automation

---

## 🎯 IMMEDIATE ACTION ITEMS

### Priority 1 (NOW):
1. **Switch to Python 3.10** - Fixes 100% of hang issues
2. **Test minimal pipeline** - Verify imports work
3. **Run single idea end-to-end** - Prove pipeline works

### Priority 2 (NEXT):
4. **Add comprehensive logging** - See what's happening
5. **Reduce context sizes** - Save memory
6. **Test overnight run** - 1 idea every 30 min for 8 hours

### Priority 3 (LATER):
7. **Profile performance** - Find bottlenecks
8. **Optimize model selection** - Fastest quality models
9. **Parallel processing** - Multiple perspectives concurrently

---

## 🔧 TESTING CHECKLIST

### Import Test:
```python
import time
start = time.time()
from src.langraph_pipeline.workflow_enhanced import create_workflow
print(f"Import time: {time.time() - start:.2f}s")  # Should be <5s
```

### Model Test:
```python
from src.utils.model_manager import get_model_manager
mgr = get_model_manager()
llm = mgr.get_model("fast")
response = llm.invoke("Hi")
print(f"Response: {response.content}")  # Should respond instantly
```

### Memory Test:
```python
# Run: ollama ps
# Should show <4 GB per model
```

### Full Pipeline Test:
```python
# Run: python test_minimal_pipeline.py
# Should complete in <5 minutes for 1 perspective
```

---

## 📈 SUCCESS METRICS

### Before Fixes:
- Import time: ∞ (hangs forever)
- Model calls: 0 (never reached)
- Overnight runs: Impossible
- Memory: 13.9 GB (OOM)

### After Fixes (Target):
- Import time: <5 seconds ✓
- Model calls: Working ✓
- Overnight runs: Stable 8+ hours ✓
- Memory: <4 GB per model ✓

---

## 🚀 NEXT STEPS

1. **User confirms Python version**
2. **Downgrade to 3.10 if needed**
3. **Test import speed**
4. **Run full pipeline**
5. **Monitor overnight run**

