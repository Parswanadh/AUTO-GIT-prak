import sys
sys.path.insert(0, '.')
from src.langraph_pipeline.nodes import _clean_requirements_txt

bad = """_bisect
_thread
_collections_abc
torch>=2.0.0
numpy>=1.24
pytorch-lightning==1.6.5
scipy
os
sys
json
re
requests
transformers>=4.30
logging
pathlib"""

py_src = {"main.py": "import torch\nimport numpy as np\nfrom transformers import AutoModel\nimport requests\nfrom scipy import sparse"}

result = _clean_requirements_txt(bad, py_src)
print("=== CLEANED ===")
print(result)
lines = [l for l in result.splitlines() if l.strip() and not l.startswith("#")]
print(f"\nPackages kept: {len(lines)} (was {len(bad.splitlines())})")
assert "_bisect" not in result, "_bisect should be stripped"
assert "os\n" not in result and result != "os", "os (stdlib) should be stripped"
assert "sys" not in result, "sys (stdlib) should be stripped"
assert "re\n" not in result or "\nre\n" not in result, "re (stdlib) should be stripped"
assert "torch" in result, "torch should be kept"
assert "numpy" in result, "numpy should be kept"
assert "requests" in result, "requests should be kept"
print("\n✅ All assertions passed!")
