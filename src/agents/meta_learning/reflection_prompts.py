"""Prompt templates for reflection agent."""


REFLECTION_GENERATION_PROMPT = """You are an expert code quality analyst performing root cause analysis on low-quality code.

=== CODE TO ANALYZE ===
{code}

=== QUALITY ASSESSMENT RESULTS ===
Overall Score: {overall_score}/100 (TARGET: 70+)

Dimension Scores:
- Syntax: {syntax_score}/100 {syntax_status}
- Complexity: {complexity_score}/100 {complexity_status}
  • Cyclomatic Complexity: {cyclomatic}
  • Cognitive Complexity: {cognitive}
- Style: {style_score}/100 {style_status}
  • Issues Found: {style_issues_count}
- Documentation: {docs_score}/100 {docs_status}
- Maintainability: {maintainability_score}/100 {maintainability_status}
- Semantic: {semantic_score}/100 {semantic_status}

=== SPECIFIC ISSUES DETECTED ===
{issues_list}

=== PREVIOUS REFLECTION ATTEMPTS ===
{previous_reflections}

=== YOUR TASK ===
Perform structured root cause analysis and create improvement plan.

OUTPUT REQUIREMENTS:
1. Identify PRIMARY failure type (complexity/style/docs/etc)
2. Diagnose ROOT CAUSE (not just symptoms)
3. List SPECIFIC failing components (functions/classes/lines)
4. Create CONCRETE action plan with priority order
5. Set REALISTIC improvement targets per dimension

Output ONLY valid JSON (no markdown, no preamble):
{{
  "failure_type": "complexity|style_violations|documentation|quality_issue",
  "root_cause": "Technical diagnosis with specifics",
  "failing_components": ["function_name", "class_name", "lines_10-15"],
  "evidence": [
    {{
      "dimension": "complexity",
      "current_score": {complexity_score},
      "target_score": 85,
      "specific_problems": [
        "Function 'process_data' has cyclomatic complexity of 15 (threshold: 10)",
        "Deeply nested if-else blocks in lines 42-68"
      ],
      "metrics": {{"cyclomatic": {cyclomatic}, "cognitive": {cognitive}}}
    }}
  ],
  "fix_strategy": "Refactor complex functions using strategy pattern and early returns",
  "specific_changes": [
    "1. Extract nested logic in 'process_data' into helper functions",
    "2. Replace if-else chain with dictionary dispatch",
    "3. Add guard clauses to reduce nesting depth"
  ],
  "priority_order": [1, 2, 3],
  "expected_improvements": {{
    "complexity": 85,
    "maintainability": 80,
    "style": {style_score}
  }},
  "confidence": 0.9,
  "estimated_effort": "medium"
}}

CRITICAL RULES:
- Base analysis ONLY on provided metrics (no hallucination)
- Be SPECIFIC: Reference actual function names, line numbers, metrics
- Prioritize fixes by impact (biggest quality gains first)
- Set REALISTIC targets (don't promise 100/100)
- Focus on TOP 3 issues (not everything at once)
"""


CODE_IMPROVEMENT_PROMPT = """You are a code refactoring expert applying structured improvements.

=== ORIGINAL CODE ===
{original_code}

=== REFLECTION ANALYSIS ===
Failure Type: {failure_type}
Root Cause: {root_cause}

Failing Components:
{failing_components}

Fix Strategy: {fix_strategy}

Specific Changes (in priority order):
{specific_changes}

Expected Improvements:
{expected_improvements}

=== YOUR TASK ===
Apply the specified changes to improve code quality.

RULES:
1. Follow the priority order exactly
2. Make ONLY the changes specified (no extras)
3. Preserve functionality (don't change logic)
4. Maintain existing variable/function names where possible
5. Keep same file structure
6. Add comments explaining significant changes

OUTPUT:
Return ONLY the improved Python code (no explanations, no markdown blocks).

The code should start directly without any prefixes like "Here's the improved code:" or markdown blocks.
"""


STOPPING_DECISION_PROMPT = """You are a reflection coordinator deciding whether to continue improvement cycles.

=== REFLECTION HISTORY ===
Initial Quality Score: {initial_score}/100
Current Quality Score: {current_score}/100
Target Score: 70/100

Iteration History:
{iteration_history}

Recent Improvements:
- Last Cycle: {last_improvement:+.1f} points
- Average per Cycle: {avg_improvement:+.1f} points

=== STOPPING CONDITIONS ===
1. Quality threshold reached (≥70)
2. Max iterations (3)
3. No improvement in last 2 cycles
4. Diminishing returns (<2 points improvement)

=== DECISION ===
Should we continue reflecting?

Output JSON:
{{
  "should_continue": true|false,
  "reason": "threshold_met|max_iterations|no_improvement|diminishing_returns",
  "confidence": 0.9,
  "recommendation": "One-sentence recommendation"
}}
"""
