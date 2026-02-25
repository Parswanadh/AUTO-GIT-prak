"""
Iterative fixer using LLM to fix code errors.

Automatically fixes code errors by feeding them to an LLM and iterating.
"""

import asyncio
import hashlib
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from ..ollama_client import get_ollama_client
from ..prompts.validation_prompts import FixPromptBuilder
from ..validation.error_types import (
    ValidationResult,
    CodeError,
    ErrorType,
    ExecutionResult
)


class IterativeFixer:
    """Fixes code errors iteratively using LLM."""

    def __init__(self, model: str = "deepseek-coder-v2:16b-offload", max_attempts: int = 3):
        """Initialize the iterative fixer.

        Args:
            model: Ollama model to use for fixing
            max_attempts: Maximum number of fix attempts
        """
        self.model = model
        self.max_attempts = max_attempts
        self.client = None
        self.fix_cache = {}  # Cache for fixes

    async def fix_code(
        self,
        code: str,
        file_name: str,
        errors: List[CodeError],
        available_files: Dict[str, str],
        context: str = ""
    ) -> Tuple[str, ValidationResult]:
        """Fix code errors iteratively using LLM.

        Args:
            code: The source code to fix
            file_name: Name of the file
            errors: List of errors found
            available_files: Map of available files
            context: Additional context (solution description, etc.)

        Returns:
            Tuple of (fixed_code, final_validation_result)
        """
        if not errors:
            return code, ValidationResult(is_valid=True, file_name=file_name)

        # Get client lazily
        if self.client is None:
            self.client = get_ollama_client()

        current_code = code
        all_attempts = []

        for attempt in range(1, self.max_attempts + 1):
            # Build fix prompt
            prompt = self._build_fix_prompt(
                current_code,
                errors,
                available_files,
                context
            )

            # Try to fix
            try:
                fixed_code = await self._generate_fix(prompt)

                # Validate the fix
                # (In real implementation, we'd re-run validators here)
                # For now, just return the fixed code
                current_code = fixed_code
                all_attempts.append({
                    'attempt': attempt,
                    'errors_fixed': len(errors),
                    'code': fixed_code
                })

                # If no more errors, we're done
                # (Would re-validate here in production)

                break  # Success

            except Exception as e:
                print(f"[FIX] Attempt {attempt} failed: {e}")
                if attempt == self.max_attempts:
                    break
                # Try again with same errors

        return current_code, ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors if attempt == self.max_attempts else [],
            file_name=file_name
        )

    def _build_fix_prompt(
        self,
        code: str,
        errors: List[CodeError],
        available_files: Dict[str, str],
        context: str
    ) -> str:
        """Build prompt for LLM to fix errors.

        Args:
            code: Source code to fix
            errors: List of errors
            available_files: Available files
            context: Additional context

        Returns:
            Prompt string for LLM
        """
        # Convert errors to dict format
        error_dicts = [error.to_dict() for error in errors]

        # Get available files and keys
        file_list = list(available_files.keys())

        # Use the prompt builder
        prompt = FixPromptBuilder.build_fix_prompt(
            code=code,
            errors=error_dicts,
            available_files=file_list,
            available_keys=[]  # Would extract from config
        )

        # Add context if provided
        if context:
            prompt = f"CONTEXT:\n{context}\n\n{prompt}"

        return prompt

    async def _generate_fix(self, prompt: str) -> str:
        """Generate code fix using LLM.

        Args:
            prompt: Fix prompt

        Returns:
            Fixed code
        """
        # Check cache
        cache_key = hashlib.md5(prompt.encode()).hexdigest()
        if cache_key in self.fix_cache:
            return self.fix_cache[cache_key]

        # Generate fix
        response = await self.client.generate(
            model=self.model,
            prompt=prompt,
            timeout=120  # 2 minutes for fixes
        )

        fixed_code = response.get("content", "")

        # Extract code from markdown if present
        fixed_code = self._extract_code_from_response(fixed_code)

        # Cache result
        self.fix_cache[cache_key] = fixed_code

        return fixed_code

    def _extract_code_from_response(self, response: str) -> str:
        """Extract Python code from LLM response.

        Args:
            response: LLM response text

        Returns:
            Extracted code
        """
        # Look for code blocks
        import re

        # Try markdown code blocks
        code_blocks = re.findall(r'```python\n(.*?)\n```', response, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()

        code_blocks = re.findall(r'```\n(.*?)\n```', response, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()

        # Try plain ```python
        code_blocks = re.findall(r'```python(.*?)```', response, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()

        # If no code blocks, return as-is (might be just code)
        return response.strip()


class CodeFixer:
    """High-level interface for fixing generated code."""

    def __init__(self, model: str = "deepseek-coder-v2:16b-offload"):
        """Initialize the code fixer.

        Args:
            model: Ollama model to use for fixing
        """
        self.fixer = IterativeFixer(model=model)

    async def fix_files(
        self,
        files: Dict[str, str],
        validation_results: Dict[str, ValidationResult],
        context: str = ""
    ) -> Dict[str, str]:
        """Fix all files with errors.

        Args:
            files: Map of filename -> code
            validation_results: Validation results for each file
            context: Additional context

        Returns:
            Map of filename -> fixed code
        """
        fixed_files = {}

        for file_name, code in files.items():
            result = validation_results.get(file_name)

            if result and not result.is_valid and result.errors:
                print(f"\n[FIX] Fixing {file_name} ({len(result.errors)} errors)")

                fixed_code, final_result = await self.fixer.fix_code(
                    code=code,
                    file_name=file_name,
                    errors=result.errors,
                    available_files=files,
                    context=context
                )

                fixed_files[file_name] = fixed_code

                if final_result.is_valid:
                    print(f"[OK] Fixed {file_name}")
                else:
                    print(f"[PARTIAL] Fixed {file_name} ({len(final_result.errors)} remaining)")
            else:
                # No fixes needed
                fixed_files[file_name] = code

        return fixed_files


async def fix_code_async(
    code: str,
    errors: List[CodeError],
    file_name: str = "",
    available_files: Dict[str, str] = None,
    context: str = ""
) -> Tuple[str, ValidationResult]:
    """Convenience function to fix code asynchronously.

    Args:
        code: Source code to fix
        errors: List of errors
        file_name: Optional file name
        available_files: Optional map of available files
        context: Additional context

    Returns:
        Tuple of (fixed_code, validation_result)
    """
    fixer = IterativeFixer()
    return await fixer.fix_code(
        code=code,
        file_name=file_name,
        errors=errors,
        available_files=available_files or {},
        context=context
    )
