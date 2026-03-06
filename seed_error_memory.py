"""Seed codegen error memory with known bugs from past pipeline runs."""
from src.utils.codegen_error_memory import get_error_memory

mem = get_error_memory()

# Run #10 (CLI Todo App) - required manual fixes
mem.record("cli_todo_app_001", "CLI Todo App", "code_review", "API_MISMATCH",
    "main.py",
    "main.py called cli_app.add_task(), cli_app.list_tasks() etc but CliApp class only has run() and execute_command(). main.py should call cli_app.run() not invent methods.",
    "Changed to cli_app.run() which delegates internally", True)

mem.record("cli_todo_app_001", "CLI Todo App", "code_review", "API_MISMATCH",
    "cli_handler.py",
    "Used t.id and t.title (dot notation) on results from todo_db.list_tasks() which returns List[Dict]. Should use bracket notation t['id'] and t['title'].",
    "Changed to bracket notation: t['id'], t['title'], t['status']", True)

# Run #12 (Password Manager) - caught by testing
mem.record("password_manager_001", "Local password manager CLI", "static_check", "UNINITIALIZED_ATTR",
    "main.py",
    "self._metadata used in _write_metadata() but __init__ did not set self._metadata = {} before calling _load_or_initialize() which calls _write_metadata()",
    "Added self._metadata = {} and self._credentials = {} before _load_or_initialize()", True)

mem.record("password_manager_001", "Local password manager CLI", "static_check", "SELF_METHOD_MISSING",
    "main.py",
    "Called self._save_metadata() but the class only defines _write_metadata(). Method name mismatch inside same class.",
    "Changed to self._write_metadata(self._metadata)", True)

# Run #9 (Sentiment Analyzer)
mem.record("sentiment_analyzer_001", "Neural network sentiment analyzer", "code_review", "PLACEHOLDER_INIT",
    "train.py",
    "model = nn.Module() used as placeholder instead of model = SentimentLSTM(...) the real class defined in model.py",
    "Replaced with real class instantiation", True)

# Run #8 (SNN Hardware Accelerator)
mem.record("snn_accelerator_001", "SNN hardware accelerator", "code_review", "TRUNCATED",
    "main.py",
    "main.py was 97 lines ending mid-function with no __main__ guard - file truncated during generation",
    "Regenerated file completely", True)

mem.record("snn_accelerator_001", "SNN hardware accelerator", "code_review", "DEAD_LOGIC",
    "main.py",
    "fire() called after step() but step() already resets membrane voltage v=0, so fire() always returns False. 0 spikes recorded.",
    "Reordered: check fire() BEFORE step() mutates the state", True)

# Common patterns across multiple runs
mem.record("multiple_runs", "Various projects", "static_check", "MISSING_EXPORT",
    "unknown",
    "Module imports a name from another file but that name is not defined in that source file. Cross-file import mismatch.",
    "Add the missing definition or fix the import statement", True)

mem.record("multiple_runs", "Various projects", "static_check", "CIRCULAR_IMPORT",
    "unknown",
    "File A imports from file B and file B imports from file A creating a circular dependency that crashes at runtime.",
    "Move shared definitions to a separate utils module", True)

mem.record("multiple_runs", "Various projects", "code_review", "STUB_BODY",
    "unknown",
    "Function body is only pass or raise NotImplementedError where real implementation was expected.",
    "Write actual implementation logic", True)

stats = mem.get_stats()
print(f"Seeded memory: {stats}")
print()
print(mem.get_top_lessons(10))
print()
print("---")
print(mem.get_lessons_for_review(10))
