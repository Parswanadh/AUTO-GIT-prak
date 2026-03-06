"""
Multi-language Support for Auto-GIT
====================================

Detects target language from requirements, provides language-specific scaffolding
(project structure, build files, test runner config), and validation commands.

Supported languages:
  - Python (default, fully supported)
  - Rust (Cargo.toml, cargo test)
  - Go (go.mod, go test)
  - TypeScript/JavaScript (package.json, tsconfig.json, jest/vitest)

Usage:
    from src.utils.language_support import detect_language, get_scaffolding, get_test_command

    lang = detect_language(requirements, idea)
    scaffold_files = get_scaffolding(lang, project_name)
    test_cmd = get_test_command(lang)
"""

import re
from typing import Dict, List, Optional, Tuple


# ── Language detection ────────────────────────────────────────────────────────

# Keywords/signals that indicate a target language
_LANG_SIGNALS: Dict[str, List[str]] = {
    "rust": [
        "rust", "cargo", "crate", "tokio", "actix", "wasm", "webassembly",
        "systems programming", "zero-cost", "borrow checker", "unsafe",
        "no_std", "embedded", ".rs", "rustc", "clippy",
    ],
    "go": [
        "golang", " go ", "goroutine", "go module", "go mod",
        "gin", "echo framework", "cobra", "grpc-go",
        "concurrency", "goroutines", "channels",
        ".go", "go build", "go test",
    ],
    "typescript": [
        "typescript", "ts", "tsx", "react", "next.js", "nextjs",
        "angular", "vue", "svelte", "deno", "bun",
        "npm", "yarn", "pnpm", "node.js", "nodejs",
        "express", "fastify", "nest.js", "nestjs",
        ".ts", ".tsx", "tsconfig", "package.json",
        "javascript", "js",
    ],
    "python": [
        "python", "pip", "conda", "pytorch", "tensorflow",
        "flask", "django", "fastapi", "pandas", "numpy",
        ".py", "requirements.txt", "pyproject.toml",
    ],
}


def detect_language(requirements: Dict, idea: str = "") -> str:
    """
    Detect the target programming language from requirements and idea text.
    Returns one of: 'python', 'rust', 'go', 'typescript'.
    Defaults to 'python' if no strong signal found.
    """
    # Build combined text to search
    text_parts = [idea.lower()]
    if requirements:
        for key in ("project_type", "complexity", "data_flow", "success_criteria"):
            val = requirements.get(key, "")
            if isinstance(val, str):
                text_parts.append(val.lower())
        for key in ("core_components", "key_features", "external_deps", "risk_areas"):
            val = requirements.get(key, [])
            if isinstance(val, list):
                text_parts.extend(str(v).lower() for v in val)
        # Check if language is explicitly specified
        lang_field = requirements.get("language", "").lower()
        if lang_field:
            text_parts.append(lang_field)

    combined = " ".join(text_parts)

    # Score each language
    scores: Dict[str, int] = {}
    for lang, keywords in _LANG_SIGNALS.items():
        score = 0
        for kw in keywords:
            if kw in combined:
                score += 1
                # Exact language name gets extra weight
                if kw in (lang, lang + "script"):
                    score += 3
        scores[lang] = score

    # Require minimum score to override default
    best_lang = max(scores, key=scores.get)  # type: ignore
    if scores[best_lang] < 2:
        return "python"  # default
    return best_lang


# ── Language-specific scaffolding ─────────────────────────────────────────────

def get_scaffolding(language: str, project_name: str = "project") -> Dict[str, str]:
    """
    Return a dict of {filename: content} for language-specific scaffolding files.
    These are the build/config files, NOT the implementation code.
    """
    name = re.sub(r"[^a-z0-9_-]", "-", project_name.lower()).strip("-") or "project"

    if language == "rust":
        return _rust_scaffold(name)
    elif language == "go":
        return _go_scaffold(name)
    elif language == "typescript":
        return _ts_scaffold(name)
    else:
        return _python_scaffold(name)


def _python_scaffold(name: str) -> Dict[str, str]:
    return {
        "requirements.txt": "# Auto-generated dependencies\n",
        "setup.py": (
            f'from setuptools import setup, find_packages\n\n'
            f'setup(\n'
            f'    name="{name}",\n'
            f'    version="0.1.0",\n'
            f'    packages=find_packages(),\n'
            f'    python_requires=">=3.9",\n'
            f')\n'
        ),
    }


def _rust_scaffold(name: str) -> Dict[str, str]:
    return {
        "Cargo.toml": (
            f'[package]\n'
            f'name = "{name}"\n'
            f'version = "0.1.0"\n'
            f'edition = "2021"\n\n'
            f'[dependencies]\n'
            f'serde = {{ version = "1", features = ["derive"] }}\n'
            f'serde_json = "1"\n'
            f'tokio = {{ version = "1", features = ["full"] }}\n'
            f'clap = {{ version = "4", features = ["derive"] }}\n'
        ),
        "src/main.rs": (
            f'//! {name} — Auto-generated by Auto-GIT\n\n'
            f'fn main() {{\n'
            f'    println!("Hello from {name}!");\n'
            f'}}\n'
        ),
        ".gitignore": "/target\n",
    }


def _go_scaffold(name: str) -> Dict[str, str]:
    return {
        "go.mod": (
            f'module github.com/auto-git/{name}\n\n'
            f'go 1.21\n'
        ),
        "main.go": (
            f'// {name} — Auto-generated by Auto-GIT\n'
            f'package main\n\n'
            f'import "fmt"\n\n'
            f'func main() {{\n'
            f'\tfmt.Println("Hello from {name}!")\n'
            f'}}\n'
        ),
        ".gitignore": f"/{name}\n*.exe\n",
    }


def _ts_scaffold(name: str) -> Dict[str, str]:
    return {
        "package.json": (
            '{\n'
            f'  "name": "{name}",\n'
            '  "version": "0.1.0",\n'
            '  "description": "Auto-generated by Auto-GIT",\n'
            '  "main": "dist/index.js",\n'
            '  "scripts": {\n'
            '    "build": "tsc",\n'
            '    "start": "node dist/index.js",\n'
            '    "dev": "ts-node src/index.ts",\n'
            '    "test": "jest"\n'
            '  },\n'
            '  "devDependencies": {\n'
            '    "typescript": "^5.3.0",\n'
            '    "@types/node": "^20.0.0",\n'
            '    "ts-node": "^10.9.0",\n'
            '    "jest": "^29.7.0",\n'
            '    "@types/jest": "^29.5.0",\n'
            '    "ts-jest": "^29.1.0"\n'
            '  }\n'
            '}\n'
        ),
        "tsconfig.json": (
            '{\n'
            '  "compilerOptions": {\n'
            '    "target": "ES2022",\n'
            '    "module": "commonjs",\n'
            '    "lib": ["ES2022"],\n'
            '    "outDir": "./dist",\n'
            '    "rootDir": "./src",\n'
            '    "strict": true,\n'
            '    "esModuleInterop": true,\n'
            '    "skipLibCheck": true,\n'
            '    "forceConsistentCasingInFileNames": true,\n'
            '    "resolveJsonModule": true,\n'
            '    "declaration": true\n'
            '  },\n'
            '  "include": ["src/**/*"],\n'
            '  "exclude": ["node_modules", "dist"]\n'
            '}\n'
        ),
        "src/index.ts": (
            f'// {name} — Auto-generated by Auto-GIT\n\n'
            f'console.log("Hello from {name}!");\n'
        ),
        ".gitignore": "node_modules/\ndist/\n*.js.map\n",
    }


# ── Language-specific test/build commands ─────────────────────────────────────

def get_test_command(language: str) -> List[str]:
    """Return the test command for a given language."""
    cmds = {
        "python": ["python", "-m", "pytest", "-v", "--tb=short"],
        "rust":   ["cargo", "test"],
        "go":     ["go", "test", "./..."],
        "typescript": ["npx", "jest", "--verbose"],
    }
    return cmds.get(language, cmds["python"])


def get_build_command(language: str) -> Optional[List[str]]:
    """Return the build command, or None for interpreted languages."""
    cmds = {
        "rust":       ["cargo", "build", "--release"],
        "go":         ["go", "build", "./..."],
        "typescript": ["npx", "tsc"],
    }
    return cmds.get(language)


def get_run_command(language: str, entry_file: str = "") -> List[str]:
    """Return the run command for a given language."""
    cmds = {
        "python":     ["python", entry_file or "main.py"],
        "rust":       ["cargo", "run"],
        "go":         ["go", "run", entry_file or "main.go"],
        "typescript": ["npx", "ts-node", entry_file or "src/index.ts"],
    }
    return cmds.get(language, cmds["python"])


def get_file_extension(language: str) -> str:
    """Return the primary file extension for a language."""
    return {
        "python": ".py",
        "rust": ".rs",
        "go": ".go",
        "typescript": ".ts",
    }.get(language, ".py")


def get_code_gen_instructions(language: str) -> str:
    """Return language-specific instructions to include in the code generation prompt."""
    instructions = {
        "python": (
            "Generate Python 3.9+ code. Use type hints. Follow PEP 8. "
            "Include if __name__ == '__main__' guard in main.py."
        ),
        "rust": (
            "Generate idiomatic Rust code (edition 2021). Use strong typing, "
            "Result<T, E> for error handling, derive macros for structs. "
            "Do NOT use unwrap() in production code — use ? operator or proper error handling. "
            "Structure: src/main.rs for entry, src/lib.rs for library code."
        ),
        "go": (
            "Generate idiomatic Go code (Go 1.21+). Use error returns (not panics), "
            "proper package naming, and go doc comments. "
            "Structure: main.go for entry, separate packages for core logic."
        ),
        "typescript": (
            "Generate TypeScript code (strict mode). Use proper types (no 'any'). "
            "Use async/await for async operations. "
            "Structure: src/index.ts for entry, separate modules for logic."
        ),
    }
    return instructions.get(language, instructions["python"])
