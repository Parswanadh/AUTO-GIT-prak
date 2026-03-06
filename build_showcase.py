"""Build the auto-git-runs showcase repo from all pipeline outputs."""
import shutil, os, json, re
from pathlib import Path
from datetime import datetime

output_dir = Path(r'd:\Projects\auto-git\output')
staging = Path(r'd:\Projects\auto-git-runs')

# Clean and recreate staging
if staging.exists():
    shutil.rmtree(staging)
staging.mkdir()

# Collect all runs with code
runs = []
all_dirs = sorted(output_dir.iterdir(), key=lambda d: d.stat().st_mtime)

for d in all_dirs:
    if not d.is_dir():
        continue
    py_files = [f for f in d.rglob('*.py') if '__pycache__' not in str(f)]
    if len(py_files) == 0:
        continue
    total_lines = sum(len(f.read_text(encoding='utf-8', errors='replace').splitlines()) for f in py_files)
    if total_lines == 0:
        continue
    
    # Find the actual code subfolder
    code_dir = None
    for sub in sorted(d.iterdir()):
        if sub.is_dir() and sub.name != '__pycache__':
            code_dir = sub
            break
    if code_dir is None:
        code_dir = d
    
    has_main = any(f.name == 'main.py' for f in py_files)
    main_size = 0
    for f in py_files:
        if f.name == 'main.py':
            main_size = f.stat().st_size
    
    runs.append({
        'name': d.name,
        'date': datetime.fromtimestamp(d.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
        'py_count': len(py_files),
        'total_lines': total_lines,
        'code_dir': str(code_dir),
        'has_main': has_main,
        'main_size': main_size,
    })

print(f"Found {len(runs)} runs with code")

# Copy each run to staging as pass-N-name
for i, r in enumerate(runs):
    pass_num = i + 1
    # Clean up the name for folder
    clean_name = r['name'].replace(' ', '-').replace('(', '').replace(')', '')
    folder_name = f"pass-{pass_num:02d}-{clean_name}"
    dest = staging / folder_name
    
    # Copy the code directory contents
    src = Path(r['code_dir'])
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.db'))
    
    print(f"  Pass {pass_num:2d}: {r['py_count']:2d} py, {r['total_lines']:5d} lines | {r['name'][:60]}")
    r['folder'] = folder_name
    r['pass'] = pass_num

# Save metadata
with open(staging / '_run_metadata.json', 'w') as f:
    json.dump(runs, f, indent=2)

print(f"\nCopied {len(runs)} runs to {staging}")
print("Now create README and push to GitHub")
