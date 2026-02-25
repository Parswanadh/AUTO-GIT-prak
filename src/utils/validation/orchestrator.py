"""
Validation orchestrator that coordinates all validators.

Runs validators in sequence and manages the overall validation process.
"""

import asyncio
from typing import Dict, List, Optional

from .error_types import (
    ValidationResult,
    ValidationReport,
    CodeError,
    ErrorType,
    ExecutionResult
)
from .syntax_validator import SyntaxValidator
from .import_validator import ImportValidator
from .execution_sandbox import ExecutionSandbox
from .iterative_fixer import CodeFixer


class ValidationOrchestrator:
    """Orchestrates the entire validation process."""

    def __init__(
        self,
        ollama_client=None,
        fixer_model: str = "deepseek-coder-v2:16b-offload",
        enable_execution: bool = True,
        auto_fix: bool = True
    ):
        """Initialize the validation orchestrator.

        Args:
            ollama_client: Ollama client for LLM fixing
            fixer_model: Model to use for fixing
            enable_execution: Whether to run execution tests
            auto_fix: Whether to automatically fix errors
        """
        self.client = ollama_client
        self.fixer_model = fixer_model
        self.enable_execution = enable_execution
        self.auto_fix = auto_fix

        # Initialize validators
        self.syntax_validator = SyntaxValidator()
        self.import_validator = ImportValidator()
        self.execution_sandbox = ExecutionSandbox(timeout=30)

        # Initialize fixer if auto-fix enabled
        self.code_fixer = CodeFixer(model=fixer_model) if auto_fix else None

    async def validate_and_fix(
        self,
        code_files: Dict[str, str],
        config: Dict = None,
        solution: str = ""
    ) -> Dict:
        """Validate all code files and fix errors.

        Args:
            code_files: Map of filename -> code content
            config: Optional config dict for validation
            solution: Optional solution context for fixing

        Returns:
            Dict with validated_code and validation_report
        """
        report = ValidationReport()
        validated_code = code_files.copy()

        # Phase 1: Validate all files
        print("\n[VALIDATE] Phase 1: Checking syntax and imports...")
        validation_results = {}

        for file_name, code in code_files.items():
            result = await self._validate_file(
                code=code,
                file_name=file_name,
                available_files=code_files
            )
            validation_results[file_name] = result
            report.add_file_result(file_name, result)

        # Phase 2: Fix errors if auto-fix enabled
        if self.auto_fix and report.total_errors > 0:
            print(f"\n[VALIDATE] Phase 2: Fixing {report.total_errors} errors...")

            fixed_code = await self.code_fixer.fix_files(
                files=code_files,
                validation_results=validation_results,
                context=solution
            )

            # Re-validate fixed code
            print("\n[VALIDATE] Phase 3: Re-validating fixed code...")
            validation_results = {}

            for file_name, code in fixed_code.items():
                result = await self._validate_file(
                    code=code,
                    file_name=file_name,
                    available_files=fixed_code
                )
                validation_results[file_name] = result
                report.add_file_result(file_name, result)

            validated_code = fixed_code
            report.fix_attempts = 1

        # Phase 3: Execution testing (if enabled)
        if self.enable_execution:
            print("\n[VALIDATE] Phase 3: Running execution tests...")

            exec_result = self.execution_sandbox.execute(validated_code)

            if not exec_result.success:
                print(f"[WARN] Execution failed: {exec_result.error[:100]}")

                # Parse execution error
                for file_name in validated_code.keys():
                    error = self.execution_sandbox._parse_execution_error(
                        exec_result, file_name
                    )
                    if error:
                        report.errors_by_file.setdefault(file_name, []).append(error)

                # If execution found errors AND auto-fix is enabled, try to fix
                if self.auto_fix and report.total_errors > 0:
                    print(f"\n[VALIDATE] Phase 4: Fixing {report.total_errors} runtime errors...")

                    # Build validation results from execution errors
                    validation_results = {}
                    for file_name in validated_code.keys():
                        errors = report.errors_by_file.get(file_name, [])
                        validation_results[file_name] = ValidationResult(
                            is_valid=len(errors) == 0,
                            errors=errors,
                            file_name=file_name
                        )

                    # Try to fix
                    fixed_code = await self.code_fixer.fix_files(
                        files=validated_code,
                        validation_results=validation_results,
                        context=solution
                    )

                    validated_code = fixed_code
                    report.fix_attempts += 1

                    # Re-validate after fix
                    print("\n[VALIDATE] Phase 5: Re-validating after fix...")
                    exec_result = self.execution_sandbox.execute(validated_code)

                    if not exec_result.success:
                        # Still has errors
                        for file_name in validated_code.keys():
                            error = self.execution_sandbox._parse_execution_error(
                                exec_result, file_name
                            )
                            if error:
                                report.errors_by_file.setdefault(file_name, []).append(error)
                    else:
                        print("[OK] Execution test passed after fix!")
            else:
                print("[OK] Execution test passed")

            report.final_status = report.determine_status()

        # Final status
        report.final_status = report.determine_status()

        return {
            "validated_code": validated_code,
            "validation_report": report
        }

    async def _validate_file(
        self,
        code: str,
        file_name: str,
        available_files: Dict[str, str]
    ) -> ValidationResult:
        """Validate a single file with all validators.

        Args:
            code: Source code to validate
            file_name: Name of the file
            available_files: All available files

        Returns:
            Combined validation result
        """
        all_errors = []
        all_warnings = []

        # 1. Syntax validation (must pass first)
        syntax_result = self.syntax_validator.validate(code, file_name)
        all_errors.extend(syntax_result.errors)
        all_warnings.extend(syntax_result.warnings)

        # If syntax errors, stop here
        if syntax_result.errors:
            return ValidationResult(
                is_valid=False,
                errors=all_errors,
                warnings=all_warnings,
                file_name=file_name
            )

        # 2. Import validation
        import_result = self.import_validator.validate(
            code=code,
            file_name=file_name,
            available_files=available_files
        )
        all_errors.extend(import_result.errors)
        all_warnings.extend(import_result.warnings)

        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            file_name=file_name
        )

    def validate_report_summary(self, report: ValidationReport) -> str:
        """Generate a human-readable summary of validation report.

        Args:
            report: Validation report

        Returns:
            Formatted summary string
        """
        lines = [
            "\n" + "=" * 60,
            "VALIDATION REPORT",
            "=" * 60,
            f"Total Files: {report.total_files}",
            f"Total Errors: {report.total_errors}",
            f"Total Warnings: {report.total_warnings}",
            f"Final Status: {report.final_status}",
        ]

        if report.files_with_errors:
            lines.append("\nFiles with Errors:")
            for f in report.files_with_errors:
                errors = report.errors_by_file[f]
                lines.append(f"  {f}: {len(errors)} error(s)")
                for error in errors[:3]:  # Show first 3
                    lines.append(f"    - Line {error.line}: {error.message[:60]}")
                if len(errors) > 3:
                    lines.append(f"    ... and {len(errors) - 3} more")

        if report.fix_attempts > 0:
            lines.append(f"\nFix Attempts: {report.fix_attempts}")

        lines.append("=" * 60)

        return "\n".join(lines)


# Convenience function
async def validate_code(
    code_files: Dict[str, str],
    ollama_client=None,
    enable_execution: bool = True,
    auto_fix: bool = True
) -> Dict:
    """Convenience function to validate code.

    Args:
        code_files: Map of filename -> code content
        ollama_client: Optional Ollama client
        enable_execution: Whether to run execution tests
        auto_fix: Whether to automatically fix errors

    Returns:
        Dict with validated_code and validation_report
    """
    orchestrator = ValidationOrchestrator(
        ollama_client=ollama_client,
        enable_execution=enable_execution,
        auto_fix=auto_fix
    )

    return await orchestrator.validate_and_fix(code_files)
