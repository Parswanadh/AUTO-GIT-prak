"""
Mutation Testing - Test the quality of tests by mutating code

Introduces small changes (mutations) to code and checks if tests catch them.
"""

import ast
import copy
from typing import List, Dict, Callable, Any
from dataclasses import dataclass
import random


@dataclass
class Mutation:
    """Represents a code mutation"""
    mutation_type: str
    original: str
    mutated: str
    line_number: int
    description: str


@dataclass
class MutationResult:
    """Result of testing a mutation"""
    mutation: Mutation
    detected: bool  # True if test failed (good!)
    test_output: str


class MutationTester:
    """
    Simple mutation testing without external dependencies.
    Tests the quality of tests by mutating code and checking if tests catch mutations.
    """
    
    def __init__(self):
        self.mutations: List[Mutation] = []
        self.results: List[MutationResult] = []
    
    def generate_mutations(self, code: str, language: str = "python") -> List[Mutation]:
        """
        Generate mutations for the given code.
        
        Mutation types:
        - Arithmetic operators: + -> -, * -> /, etc.
        - Comparison operators: == -> !=, < -> >, etc.
        - Boolean operators: and -> or, True -> False
        - Constants: numbers, strings
        - Return statements
        """
        mutations = []
        
        if language == "python":
            lines = code.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                # Arithmetic operator mutations
                if '+' in line and not '=+' in line:
                    mutated = line.replace('+', '-', 1)
                    mutations.append(Mutation(
                        mutation_type='arithmetic',
                        original=line.strip(),
                        mutated=mutated.strip(),
                        line_number=line_num,
                        description='Changed + to -'
                    ))
                
                if '-' in line and not '=-' in line and not '->' in line:
                    mutated = line.replace('-', '+', 1)
                    mutations.append(Mutation(
                        mutation_type='arithmetic',
                        original=line.strip(),
                        mutated=mutated.strip(),
                        line_number=line_num,
                        description='Changed - to +'
                    ))
                
                if '*' in line and not '**' in line:
                    mutated = line.replace('*', '/', 1)
                    mutations.append(Mutation(
                        mutation_type='arithmetic',
                        original=line.strip(),
                        mutated=mutated.strip(),
                        line_number=line_num,
                        description='Changed * to /'
                    ))
                
                # Comparison operator mutations
                if '==' in line:
                    mutated = line.replace('==', '!=', 1)
                    mutations.append(Mutation(
                        mutation_type='comparison',
                        original=line.strip(),
                        mutated=mutated.strip(),
                        line_number=line_num,
                        description='Changed == to !='
                    ))
                
                if '<' in line and not '<=' in line and not '<<' in line:
                    mutated = line.replace('<', '>', 1)
                    mutations.append(Mutation(
                        mutation_type='comparison',
                        original=line.strip(),
                        mutated=mutated.strip(),
                        line_number=line_num,
                        description='Changed < to >'
                    ))
                
                # Boolean mutations
                if ' and ' in line:
                    mutated = line.replace(' and ', ' or ', 1)
                    mutations.append(Mutation(
                        mutation_type='boolean',
                        original=line.strip(),
                        mutated=mutated.strip(),
                        line_number=line_num,
                        description='Changed and to or'
                    ))
                
                if ' True' in line or line.strip().startswith('True'):
                    mutated = line.replace('True', 'False', 1)
                    mutations.append(Mutation(
                        mutation_type='boolean',
                        original=line.strip(),
                        mutated=mutated.strip(),
                        line_number=line_num,
                        description='Changed True to False'
                    ))
                
                # Return statement mutations
                if 'return ' in line and 'return None' not in line:
                    mutated = line.replace('return ', 'return None  # ', 1)
                    mutations.append(Mutation(
                        mutation_type='return',
                        original=line.strip(),
                        mutated=mutated.strip(),
                        line_number=line_num,
                        description='Changed return value to None'
                    ))
        
        self.mutations = mutations
        return mutations
    
    def apply_mutation(self, code: str, mutation: Mutation) -> str:
        """Apply a mutation to code"""
        lines = code.split('\n')
        if 1 <= mutation.line_number <= len(lines):
            lines[mutation.line_number - 1] = mutation.mutated
        return '\n'.join(lines)
    
    def test_mutation(self, original_code: str, mutation: Mutation, 
                     test_fn: Callable[[str], bool]) -> MutationResult:
        """
        Test if a mutation is detected by the test function.
        
        Args:
            original_code: Original code
            mutation: Mutation to apply
            test_fn: Function that returns True if code passes tests
        
        Returns:
            MutationResult indicating if mutation was detected
        """
        mutated_code = self.apply_mutation(original_code, mutation)
        
        try:
            # Test should fail on mutated code (mutation detected)
            test_passed = test_fn(mutated_code)
            detected = not test_passed
            output = "Test failed (mutation detected)" if detected else "Test passed (mutation NOT detected)"
        except Exception as e:
            # Exception means test failed (good - mutation detected)
            detected = True
            output = f"Exception raised (mutation detected): {e}"
        
        result = MutationResult(
            mutation=mutation,
            detected=detected,
            test_output=output
        )
        
        self.results.append(result)
        return result
    
    def run_mutation_testing(self, code: str, test_fn: Callable[[str], bool],
                           max_mutations: int = 20) -> Dict[str, Any]:
        """
        Run mutation testing on code with given test function.
        
        Args:
            code: Code to mutate
            test_fn: Function that tests code, returns True if tests pass
            max_mutations: Maximum number of mutations to test
        
        Returns:
            Summary of mutation testing results
        """
        mutations = self.generate_mutations(code)
        
        # Limit mutations if too many
        if len(mutations) > max_mutations:
            mutations = random.sample(mutations, max_mutations)
        
        results = []
        for mutation in mutations:
            result = self.test_mutation(code, mutation, test_fn)
            results.append(result)
        
        detected = sum(1 for r in results if r.detected)
        not_detected = len(results) - detected
        
        mutation_score = detected / len(results) if results else 0
        
        return {
            'total_mutations': len(results),
            'detected': detected,
            'not_detected': not_detected,
            'mutation_score': mutation_score,
            'results': results
        }
    
    def generate_report(self) -> str:
        """Generate mutation testing report"""
        if not self.results:
            return "No mutation testing results available."
        
        report = []
        report.append("=" * 70)
        report.append("MUTATION TESTING REPORT")
        report.append("=" * 70)
        
        detected = sum(1 for r in self.results if r.detected)
        total = len(self.results)
        mutation_score = detected / total if total > 0 else 0
        
        report.append(f"\nTotal mutations: {total}")
        report.append(f"Detected (killed): {detected}")
        report.append(f"Survived: {total - detected}")
        report.append(f"Mutation score: {mutation_score:.1%}")
        
        if mutation_score >= 0.8:
            report.append("\n✅ EXCELLENT: Your tests are very thorough!")
        elif mutation_score >= 0.6:
            report.append("\n⚠️  GOOD: Tests are solid but could be improved")
        else:
            report.append("\n❌ WEAK: Tests need improvement - many mutations survived")
        
        # Show survived mutations (weakness in tests)
        survived = [r for r in self.results if not r.detected]
        if survived:
            report.append(f"\n⚠️  Survived Mutations (test weaknesses):")
            for r in survived[:5]:
                report.append(f"\n  Line {r.mutation.line_number}: {r.mutation.description}")
                report.append(f"  Original: {r.mutation.original}")
                report.append(f"  Mutated:  {r.mutation.mutated}")
        
        report.append("\n" + "=" * 70)
        return '\n'.join(report)
