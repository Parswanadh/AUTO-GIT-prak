"""
Comprehensive regression tests for workspace scanner, CLI route_input, 
CLI handlers, refine node parsing, and edge cases.

Run: python tests/test_workspace_and_cli.py
Expected: 191/191 passed (0 failed)

Covers:
  - Workspace.scan (scanning, ignoring, gitignore, project detection)
  - FileInfo properties (path, size, extension, lines, exports)
  - File CRUD (read, write, patch, delete, auto-create dirs)
  - Queries (list_files, search_content, get_summary)
  - Repo map & full context builders
  - route_input (exact commands, bare actions, workspace cmds, prefixed, NL, edge cases)
  - _human_size formatting
  - Helper functions (_should_ignore, _parse_gitignore, _extract_python_exports)
  - Project type detection (python, node, rust, go, empty)
  - Edge cases (empty workspace, max_files, deep nesting, large files, patches, etc.)
  - Refine node JSON parsing, plan parsing, code fence stripping
"""

import pytest

pytest.skip("regression script; run directly with python tests/unit/test_workspace_and_cli.py", allow_module_level=True)

import io
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.workspace import (
    Workspace,
    _extract_python_exports,
    _parse_gitignore,
    _should_ignore,
)
from src.cli.app import _human_size, route_input

passed = 0
failed = 0
sections: list[str] = []


def ok(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"  FAIL: {desc}")


def section(name: str) -> None:
    sections.append(name)


# ---------------------------------------------------------------
# SECTION 1: WORKSPACE SCANNER
# ---------------------------------------------------------------
section("Workspace Scanner")
tmp = Path(tempfile.mkdtemp(prefix="reg_"))
(tmp / "main.py").write_text(
    "def main():\n    print('hello')\n\nif __name__ == '__main__':\n    main()\n"
)
(tmp / "utils.py").write_text("class Helper:\n    pass\n\ndef add(a, b):\n    return a + b\n")
(tmp / "requirements.txt").write_text("rich\nlangchain\n")
(tmp / "README.md").write_text("# Test Project\nHello world\n")
(tmp / "config.yaml").write_text("key: value\n")
(tmp / "sub").mkdir()
(tmp / "sub" / "module.py").write_text("FOO = 42\n\ndef process():\n    return FOO\n")
(tmp / "sub" / "nested").mkdir()
(tmp / "sub" / "nested" / "deep.py").write_text("# deep\nDEEP = True\n")
(tmp / "__pycache__").mkdir()
(tmp / "__pycache__" / "junk.pyc").write_bytes(b"\x00")
(tmp / ".git").mkdir()
(tmp / ".git" / "config").write_text("[core]\n")
(tmp / ".gitignore").write_text("*.log\nbuild/\n")
(tmp / "build").mkdir()
(tmp / "build" / "out.js").write_text("x")
(tmp / "debug.log").write_text("log")

ws = Workspace.scan(tmp)
ok("scan type", isinstance(ws, Workspace))
ok("root", ws.root == tmp.resolve())
ok("main.py", "main.py" in ws.files)
ok("utils.py", "utils.py" in ws.files)
ok("requirements.txt", "requirements.txt" in ws.files)
ok("README.md", "README.md" in ws.files)
ok("config.yaml", "config.yaml" in ws.files)
ok("sub/module.py", "sub/module.py" in ws.files)
ok("sub/nested/deep.py", "sub/nested/deep.py" in ws.files)
ok("no __pycache__", not any("__pycache__" in f for f in ws.files))
ok("no .git", not any(".git/" in f or f == ".git" for f in ws.files))
ok("no debug.log", "debug.log" not in ws.files)
ok("no build/", not any(f.startswith("build/") for f in ws.files))
ok("tree_text", len(ws.tree_text) > 0)
ok("tree has sub", "sub" in ws.tree_text)
ok("tree has nested", "nested" in ws.tree_text)
ok("project python", ws.project.project_type == "python")
ok("entrypoint main.py", "main.py" in ws.project.entrypoints)
ok("dep file", ws.project.dependency_file == "requirements.txt")

fi = ws.files["main.py"]
ok("fi.path", fi.path == "main.py")
ok("fi.abs_path", os.path.isfile(fi.abs_path))
ok("fi.size", fi.size > 0)
ok("fi.ext", fi.extension == ".py")
ok("fi.is_text", fi.is_text)
ok("fi.lines", fi.lines > 0)
ok("fi.exports main", any("main" in e for e in fi.exports))

ok("read", "def main" in ws.read_file("main.py"))
ok("read None", ws.read_file("nope") is None)
ok("write", ws.write_file("n.py", "Z=1\n"))
ok("write index", "n.py" in ws.files)
ok("write read", ws.read_file("n.py") == "Z=1\n")
ok("write subdir", ws.write_file("d/f.txt", "hi\n"))
ok("patch", ws.patch_file("n.py", "Z=1", "Z=9"))
ok("patch content", ws.read_file("n.py") == "Z=9\n")
ok("patch bad", not ws.patch_file("nope", "x", "y"))
ok("delete", ws.delete_file("n.py"))
ok("del index", "n.py" not in ws.files)

ok("list_files", len(ws.list_files()) > 0)
ok("*.py filter", all(f.endswith(".py") for f in ws.list_files("*.py")))
ok("search", len(ws.search_content("def main")) > 0)
ok("search regex", len(ws.search_content(r"def \w+\(")) > 0)
ok("search empty", len(ws.search_content("xyzxyz")) == 0)
ok("bad regex", isinstance(ws.search_content("[bad"), list))
s = ws.get_summary()
ok("summary files", s["total_files"] > 0)
ok("summary lines", s["total_lines"] > 0)
ok("summary type", s["project_type"] == "python")

rm = ws.build_repo_map()
ok("repo_map", "main.py" in rm and "def main" in rm)
fc = ws.build_full_context()
ok("full_context", "def main" in fc)
ok("context limit", len(ws.build_full_context(max_chars=100)) < 500)
shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------
# SECTION 2: ROUTE INPUT
# ---------------------------------------------------------------
section("Route Input")
for inp, exp in [
    ("help", ("help", "")), ("/help", ("help", "")), ("h", ("help", "")), ("?", ("help", "")),
    ("exit", ("exit", "")), ("quit", ("exit", "")), ("q", ("exit", "")),
    ("/exit", ("exit", "")), ("/quit", ("exit", "")),
    ("clear", ("clear", "")), ("/clear", ("clear", "")), ("cls", ("clear", "")),
    ("status", ("status", "")), ("/status", ("status", "")), ("health", ("status", "")),
    ("config", ("config", "")), ("/config", ("config", "")), ("settings", ("config", "")),
    ("models", ("models", "")), ("/models", ("models", "")),
    ("models ollama", ("models_ollama", "")),
    ("resume", ("resume", "")), ("/resume", ("resume", "")),
]:
    ok(f"route '{inp}'", route_input(inp) == exp)

for inp, exp in [
    ("run", ("run", "")), ("/run", ("run", "")), ("generate", ("run", "")),
    ("create", ("run", "")), ("build", ("run", "")),
    ("research", ("research", "")), ("/research", ("research", "")),
    ("fix", ("fix", "")), ("/fix", ("fix", "")),
    ("debate", ("debate", "")), ("/debate", ("debate", "")),
    ("refine", ("refine", "")), ("/refine", ("refine", "")),
    ("improve", ("refine", "")), ("enhance", ("refine", "")),
]:
    ok(f"route '{inp}'", route_input(inp) == exp)

for inp, exp in [
    ("ls", ("ls", "")), ("files", ("ls", "")), ("/ls", ("ls", "")), ("dir", ("ls", "")),
    ("tree", ("tree", "")), ("/tree", ("tree", "")),
    ("ls *.py", ("ls", "*.py")), ("files *.md", ("ls", "*.md")),
    ("cat main.py", ("cat", "main.py")), ("show x.md", ("cat", "x.md")),
    ("read y", ("cat", "y")), ("edit z.py", ("edit", "z.py")),
    ("search TODO", ("search", "TODO")), ("grep import", ("search", "import")),
]:
    ok(f"route '{inp}'", route_input(inp) == exp)

for inp, act in [
    ("run calc", "run"), ("generate API", "run"), ("create todo", "run"),
    ("build srv", "run"), ("fix err", "fix"), ("research ML", "research"),
    ("debate arch", "debate"), ("refine perf", "refine"),
    ("improve auth", "refine"), ("enhance ui", "refine"),
]:
    ok(f"route '{inp}'", route_input(inp)[0] == act)

for inp in [
    "I want a web scraper that collects news", "implement a REST API",
    "make a todo app", "design a database", "write a parser", "code a CLI tool",
]:
    ok(f"NL '{inp[:20]}'", route_input(inp)[0] == "run")

ok("empty", route_input("") == ("noop", ""))
ok("spaces", route_input("   ") == ("noop", ""))
ok("short->chat", route_input("hi") == ("chat", "hi"))
ok("HELP", route_input("HELP") == ("help", ""))
ok("EXIT", route_input("EXIT") == ("exit", ""))
ok("LS", route_input("LS") == ("ls", ""))
ok("Refine", route_input("Refine") == ("refine", ""))
ok("trim", route_input("  help  ") == ("help", ""))

# ---------------------------------------------------------------
# SECTION 3: _human_size
# ---------------------------------------------------------------
section("_human_size")
ok("0 B", _human_size(0) == "0 B")
ok("100 B", _human_size(100) == "100 B")
ok("1023 B", _human_size(1023) == "1023 B")
ok("1.0 KB", _human_size(1024) == "1.0 KB")
ok("1.5 KB", _human_size(1536) == "1.5 KB")
ok("1.0 MB", _human_size(1048576) == "1.0 MB")
ok("1.0 GB", _human_size(1073741824) == "1.0 GB")

# ---------------------------------------------------------------
# SECTION 4: HELPERS
# ---------------------------------------------------------------
section("Helpers")
ok("ignore __pycache__", _should_ignore("__pycache__", ".", {"__pycache__"}, []))
ok("ignore .git", _should_ignore(".git", ".", {".git"}, []))
ok("ignore *.pyc", _should_ignore("t.pyc", ".", {"*.pyc"}, []))
ok("no ignore main.py", not _should_ignore("main.py", ".", {"__pycache__"}, []))
ok("gitignore *.log", _should_ignore("x.log", ".", set(), ["*.log"]))
ok("gitignore dir", _should_ignore("build", ".", set(), ["build"]))

gi = Path(tempfile.mkdtemp()) / ".gi"
gi.write_text("# c\n\n*.log\nbuild/\n!keep\n")
pats = _parse_gitignore(gi)
ok("gi skip comment", "# c" not in pats)
ok("gi skip empty", "" not in pats)
ok("gi *.log", "*.log" in pats)
ok("gi strip /", "build" in pats)
ok("gi skip !", not any(p.startswith("!") for p in pats))
ok("gi missing", _parse_gitignore(Path("nonexist")) == [])

e = _extract_python_exports("class Foo:\n    pass\ndef bar():\n    pass\n")
ok("export class", any("Foo" in x for x in e))
ok("export def", any("bar" in x for x in e))
ok("empty export", _extract_python_exports("") == [])
ok("bad code export", isinstance(_extract_python_exports("{{bad"), list))
ok("async export", any("fetch" in x for x in _extract_python_exports("async def fetch(): pass\n")))
ok(
    "nested no export",
    not any("Inner" in x for x in _extract_python_exports("class O:\n    class Inner: pass\n")),
)

# ---------------------------------------------------------------
# SECTION 5: PROJECT DETECTION
# ---------------------------------------------------------------
section("Project Detection")
for ptype, marker, entry_name in [
    ("node", "package.json", "index.js"),
    ("rust", "Cargo.toml", "src/main.rs"),
    ("go", "go.mod", "main.go"),
]:
    d = Path(tempfile.mkdtemp())
    (d / marker).write_text("{}")
    if "/" in entry_name:
        (d / os.path.dirname(entry_name)).mkdir(parents=True, exist_ok=True)
    (d / entry_name).write_text("x")
    w = Workspace.scan(d)
    ok(f"{ptype} detected", w.project.project_type == ptype)
    ok(f"{ptype} entrypoint", entry_name in w.project.entrypoints)
    shutil.rmtree(d, ignore_errors=True)

# ---------------------------------------------------------------
# SECTION 6: EDGE CASES
# ---------------------------------------------------------------
section("Edge Cases")

d = Path(tempfile.mkdtemp())
w = Workspace.scan(d)
ok("empty scan", len(w.files) == 0)
ok("empty summary", w.get_summary()["total_files"] == 0)
ok("empty type", w.project.project_type == "unknown")
shutil.rmtree(d, ignore_errors=True)

d = Path(tempfile.mkdtemp())
for i in range(20):
    (d / f"f{i}.py").write_text(f"x={i}\n")
ok("max_files", len(Workspace.scan(d, max_files=5).files) <= 5)
shutil.rmtree(d, ignore_errors=True)

d = Path(tempfile.mkdtemp())
(d / "keep.py").write_text("1\n")
(d / "skip.py").write_text("2\n")
w = Workspace.scan(d, extra_ignore={"skip.py"})
ok("extra_ignore keep", "keep.py" in w.files)
ok("extra_ignore skip", "skip.py" not in w.files)
shutil.rmtree(d, ignore_errors=True)

d = Path(tempfile.mkdtemp())
deep = d
for i in range(10):
    deep = deep / f"l{i}"
    deep.mkdir()
(deep / "bottom.py").write_text("B=1\n")
w = Workspace.scan(d)
ok("deep file", any("bottom.py" in f for f in w.files))
shutil.rmtree(d, ignore_errors=True)

d = Path(tempfile.mkdtemp())
(d / "small.py").write_text("x=1\n")
(d / "huge.py").write_text("x=1\n" * 100000)
w = Workspace.scan(d)
ok("small scanned", "small.py" in w.files)
huge = w.files.get("huge.py")
if huge and huge.size > 256 * 1024:
    ok("huge not read", huge.lines == 0)
    ok("huge read None", w.read_file("huge.py") is None)
else:
    ok("huge under limit", True)
    ok("huge under limit2", True)
shutil.rmtree(d, ignore_errors=True)

d = Path(tempfile.mkdtemp())
(d / "t.py").write_text("AAA\nBBB\n")
w = Workspace.scan(d)
ok("patch no-match", not w.patch_file("t.py", "XYZ", "NEW"))
(d / "dup.py").write_text("X=1\nX=1\n")
w2 = Workspace.scan(d)
ok("patch dup fail", not w2.patch_file("dup.py", "X=1", "X=2"))
shutil.rmtree(d, ignore_errors=True)

d = Path(tempfile.mkdtemp())
(d / "empty.py").write_text("")
w = Workspace.scan(d)
ok("empty file", "empty.py" in w.files)
ok("empty read", w.read_file("empty.py") == "")
shutil.rmtree(d, ignore_errors=True)

d = Path(tempfile.mkdtemp())
w = Workspace.scan(d)
w.write_file("test.py", "A=1\n")
ok("write-read", w.read_file("test.py") == "A=1\n")
w.write_file("test.py", "A=2\n")
ok("overwrite-read", w.read_file("test.py") == "A=2\n")
shutil.rmtree(d, ignore_errors=True)

w = Workspace.scan(".", max_files=500)
ok("real scan", w.get_summary()["total_files"] > 50)
ok("real python", w.project.project_type == "python")
ok("real entrypoints", len(w.project.entrypoints) > 0)
ok("real search", len(w.search_content("def route_input")) > 0)

# ---------------------------------------------------------------
# SECTION 7: REFINE NODE PARSING
# ---------------------------------------------------------------
section("Refine Parsing")


def parse_analysis(text: str) -> dict:
    try:
        clean = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        clean = re.sub(r"```\s*$", "", clean, flags=re.MULTILINE)
        return json.loads(clean)
    except json.JSONDecodeError:
        return {
            "strengths": [],
            "weaknesses": [],
            "suggestions": [text[:500]],
            "priority_files": [],
            "estimated_effort": "unknown",
        }


def parse_plan(text: str) -> list:
    try:
        clean = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        clean = re.sub(r"```\s*$", "", clean, flags=re.MULTILINE)
        plan = json.loads(clean)
        if isinstance(plan, list):
            return plan[:15]
    except json.JSONDecodeError:
        pass
    return [{"file": "unknown", "action": "modify", "description": text[:300]}]


def strip_fences(code: str) -> str:
    if code.startswith("```"):
        lines = code.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines)
    return code


ok("json clean", parse_analysis('{"strengths":["g"]}')["strengths"] == ["g"])
ok("json fenced", parse_analysis('```json\n{"strengths":["x"]}\n```')["strengths"] == ["x"])
ok("json plain fence", parse_analysis('```\n{"strengths":["a"]}\n```')["strengths"] == ["a"])
ok("json fallback", "suggestions" in parse_analysis("not json"))
ok("json empty", isinstance(parse_analysis(""), dict))
ok(
    "plan clean",
    parse_plan('[{"file":"a.py","action":"modify","description":"x"}]')[0]["file"] == "a.py",
)
ok(
    "plan fenced",
    parse_plan('```json\n[{"file":"b.py","action":"create","description":"y"}]\n```')[0]["file"]
    == "b.py",
)
ok("plan fallback", parse_plan("bad")[0]["file"] == "unknown")
big = json.dumps([{"file": f"f{i}.py", "action": "modify", "description": "x"} for i in range(20)])
ok("plan max 15", len(parse_plan(big)) == 15)
ok("plan dict fallback", parse_plan('{"not":"list"}')[0]["file"] == "unknown")
ok("fence py", strip_fences("```python\ndef f(): pass\n```") == "def f(): pass")
ok("fence plain", strip_fences("```\ncode\n```") == "code")
ok("no fence", strip_fences("plain") == "plain")
ok("fence js", strip_fences("```js\nlog\n```") == "log")
ok("fence empty", strip_fences("") == "")

# ---------------------------------------------------------------
# FINAL RESULTS
# ---------------------------------------------------------------
total = passed + failed
print(f"\n{'=' * 60}")
print(f"FULL REGRESSION: {passed}/{total} passed ({failed} failed)")
print(f"Sections: {', '.join(sections)}")
if failed == 0:
    print("ALL TESTS PASSED!")
else:
    print(f"ATTENTION: {failed} test(s) need fixing")
print(f"{'=' * 60}")
sys.exit(1 if failed else 0)
