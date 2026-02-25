"""
Cross-Examination Prompt Templates

Structured prompts for multi-round critic debate with:
- Cross-examination between critics
- Confidence tracking
- Focused re-debate on contentious points
- Evidence-based revision

Integration #10: Enhanced Multi-Critic Consensus with Dynamic Debate
"""

from typing import List, Dict
from src.models.schemas import CritiqueReport


# ============================================================================
# ROUND 1: INDEPENDENT CRITIQUE
# ============================================================================

INITIAL_CRITIQUE_PROMPT = """You are a {persona_name} reviewing a proposed AI research solution.

**Your Role**: {persona_description}

**Problem Context**:
{problem_description}

**Proposed Solution**:
Approach: {solution_approach}
Key Innovation: {key_innovation}
Architecture: {architecture_design}
Implementation Plan:
{implementation_steps}

**Your Task**:
Provide an expert critique from your specialized perspective as a {persona_name}.

Focus on:
1. **Technical Soundness**: Is the approach technically valid?
2. **Feasibility**: Can this realistically be implemented?
3. **Innovation**: Is this genuinely novel?
4. **Practical Concerns**: What real-world issues might arise?

**Output Format** (JSON):
{{
    "overall_assessment": "promising|needs_work|flawed",
    "strengths": ["strength1", "strength2", ...],
    "weaknesses": ["weakness1", "weakness2", ...],
    "technical_concerns": ["concern1", "concern2", ...],
    "missing_considerations": ["consideration1", "consideration2", ...],
    "real_world_feasibility": 7.5,  // 0-10 scale
    "optimization_suggestions": ["suggestion1", "suggestion2", ...],
    "verdict": "accept|revise|reject",
    "confidence": 0.85,  // 0.0-1.0: How certain are you?
    "uncertainty_reasons": ["reason1", "reason2"],  // Why uncertain?
    "key_assumptions": ["assumption1", "assumption2"]  // What assumptions are you making?
}}

Provide thoughtful, specific critique. Be direct about flaws but constructive in suggestions.
"""


# ============================================================================
# ROUND 2+: CROSS-EXAMINATION
# ============================================================================

CROSS_EXAMINATION_PROMPT = """You are a {persona_name} in Round {round_num} of a multi-expert debate.

**Reminder of Your Role**: {persona_description}

**Problem**: {problem_description}

**Solution Under Review**:
Approach: {solution_approach}
Key Innovation: {key_innovation}

---

## YOUR PREVIOUS ASSESSMENT (Round {previous_round})

**Verdict**: {your_verdict}
**Feasibility Score**: {your_score}/10
**Confidence**: {your_confidence:.0%}

**Your Main Points**:
Strengths: {your_strengths}
Weaknesses: {your_weaknesses}
Concerns: {your_concerns}

---

## OTHER CRITICS' PERSPECTIVES

{other_critics_opinions}

---

## POINTS OF DISAGREEMENT

The panel has identified these contentious points:
{contentious_points}

**Disagreement Level**: {disagreement_score:.0%}
**Areas Needing Focused Discussion**: {focused_areas}

---

## YOUR TASK: CROSS-EXAMINATION

Consider the perspectives of your fellow experts:

1. **Review their arguments**: Do they raise valid points you overlooked?
2. **Defend your position**: If you disagree, explain why your view is correct
3. **Update your assessment**: Revise your critique based on new insights
4. **Explain changes**: If you changed your mind, explain what convinced you

**Important**:
- Be intellectually honest - it's okay to change your mind with good reason
- If you maintain your position, provide evidence for why you're correct
- Focus on the {focused_areas} that need resolution
- Update your confidence based on the strength of evidence

**Output Format** (JSON):
{{
    "stance": "maintain|revise|agree_with_others",
    "stance_explanation": "Why you're maintaining/revising your position",
    "revised_critique": {{
        "overall_assessment": "promising|needs_work|flawed",
        "strengths": ["updated_strength1", ...],
        "weaknesses": ["updated_weakness1", ...],
        "technical_concerns": ["updated_concern1", ...],
        "missing_considerations": ["updated_consideration1", ...],
        "real_world_feasibility": 7.5,  // Updated score
        "optimization_suggestions": ["updated_suggestion1", ...],
        "verdict": "accept|revise|reject"
    }},
    "confidence": 0.90,  // Updated confidence (can go up or down)
    "changed_mind_because": ["reason1", "reason2"],  // If you revised
    "still_concerned_about": ["issue1", "issue2"],  // Remaining concerns
    "agreed_with": {{"critic_name": "reason_for_agreement", ...}},  // Who convinced you
    "disagreed_with": {{"critic_name": "reason_for_disagreement", ...}}  // Who you still disagree with
}}

Provide a thorough updated assessment considering all perspectives.
"""


# ============================================================================
# ROUND 3: FINAL REFINEMENT
# ============================================================================

FINAL_REFINEMENT_PROMPT = """You are a {persona_name} in the FINAL ROUND ({round_num}) of expert debate.

**Your Role**: {persona_description}

**Problem**: {problem_description}

**Solution**: {solution_approach}

---

## DEBATE HISTORY

**Round 1 (Your Initial Assessment)**:
- Verdict: {round1_verdict}
- Score: {round1_score}/10
- Confidence: {round1_confidence:.0%}

**Round 2 (After Cross-Examination)**:
- Verdict: {round2_verdict}
- Score: {round2_score}/10
- Confidence: {round2_confidence:.0%}
- Changes: {round2_changes}

**Current Consensus Status**:
- Agreement Level: {agreement_level:.0%}
- Avg Feasibility: {avg_feasibility:.1f}/10
- Remaining Contentious Points: {remaining_contentious}

---

## YOUR FINAL TASK

This is your last opportunity to refine your assessment. Consider:

1. **Have your concerns been adequately addressed?**
   - Review the solution's evolution across rounds
   - Check if your suggested improvements were incorporated

2. **Is there consensus among experts?**
   - Current agreement: {agreement_level:.0%}
   - If low agreement, what's blocking consensus?

3. **Final verdict**:
   - Accept: Solution is ready (score ≥ 7.5, high confidence)
   - Revise: Close but needs specific improvements (score 5-7.5)
   - Reject: Fundamental flaws (score < 5)

**Output Format** (JSON):
{{
    "final_verdict": "accept|revise|reject",
    "final_feasibility_score": 8.0,  // Your definitive score
    "final_confidence": 0.95,  // Your certainty in this verdict
    "rationale": "Comprehensive explanation of your final verdict",
    "evolution_summary": "How your assessment evolved across rounds",
    "blocking_issues": ["issue1", "issue2"],  // If rejecting/revising
    "conditions_for_acceptance": ["condition1", "condition2"],  // What would make you accept?
    "consensus_contribution": "How this solution contributes to reaching consensus",
    "dissent_explanation": "If disagreeing with majority, explain why"
}}

Provide your final, considered opinion. This verdict will be final.
"""


# ============================================================================
# HELPER: OTHER CRITICS' OPINIONS FORMATTING
# ============================================================================

def format_other_critics_opinions(
    critics: Dict[str, CritiqueReport],
    exclude_critic: str
) -> str:
    """
    Format other critics' opinions for cross-examination.
    
    Args:
        critics: Dict of all critiques
        exclude_critic: Name of critic receiving this (don't show their own)
    
    Returns:
        Formatted string of other critics' opinions
    """
    opinions = []
    
    for name, critique in critics.items():
        if name == exclude_critic:
            continue
        
        opinion = f"""
**{name}**:
- Verdict: {critique.verdict}
- Feasibility: {critique.real_world_feasibility}/10
- Assessment: {critique.overall_assessment}

Key Strengths: {', '.join(critique.strengths[:3])}
Key Weaknesses: {', '.join(critique.weaknesses[:3])}
Main Concerns: {', '.join(critique.technical_concerns[:2])}

Suggestions: {', '.join(critique.optimization_suggestions[:2])}
"""
        opinions.append(opinion.strip())
    
    return "\n\n".join(opinions)


def format_contentious_points(contentious: List[str]) -> str:
    """Format contentious points list."""
    if not contentious:
        return "None - critics are in agreement"
    
    return "\n".join(f"{i+1}. {point}" for i, point in enumerate(contentious))


def format_focused_areas(focused: List[str]) -> str:
    """Format focused discussion areas."""
    if not focused:
        return "General review"
    
    return ", ".join(focused)


# ============================================================================
# PROMPT BUILDER FUNCTIONS
# ============================================================================

def build_initial_critique_prompt(
    persona_name: str,
    persona_description: str,
    problem: str,
    solution: Dict[str, any]
) -> str:
    """
    Build initial critique prompt for Round 1.
    
    Args:
        persona_name: Critic's role name
        persona_description: Critic's expertise description
        problem: Problem statement
        solution: Solution proposal dict
    
    Returns:
        Formatted prompt string
    """
    implementation_steps = solution.get('implementation_plan', [])
    if isinstance(implementation_steps, list):
        implementation_steps = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(implementation_steps))
    
    return INITIAL_CRITIQUE_PROMPT.format(
        persona_name=persona_name,
        persona_description=persona_description,
        problem_description=problem,
        solution_approach=solution.get('approach_name', 'N/A'),
        key_innovation=solution.get('key_innovation', 'N/A'),
        architecture_design=solution.get('architecture_design', 'N/A'),
        implementation_steps=implementation_steps
    )


def build_cross_examination_prompt(
    persona_name: str,
    persona_description: str,
    problem: str,
    solution: Dict[str, any],
    round_num: int,
    your_previous_critique: CritiqueReport,
    other_critics: Dict[str, CritiqueReport],
    contentious_points: List[str],
    disagreement_score: float,
    focused_areas: List[str]
) -> str:
    """
    Build cross-examination prompt for Round 2+.
    
    Args:
        persona_name: Critic's role
        persona_description: Critic's expertise
        problem: Problem statement
        solution: Solution proposal
        round_num: Current round number
        your_previous_critique: Critic's previous assessment
        other_critics: Other critics' assessments
        contentious_points: List of disagreement areas
        disagreement_score: Overall disagreement level
        focused_areas: Areas to focus discussion on
    
    Returns:
        Formatted prompt string
    """
    other_opinions = format_other_critics_opinions(other_critics, persona_name)
    contentious_formatted = format_contentious_points(contentious_points)
    focused_formatted = format_focused_areas(focused_areas)
    
    return CROSS_EXAMINATION_PROMPT.format(
        persona_name=persona_name,
        round_num=round_num,
        persona_description=persona_description,
        problem_description=problem,
        solution_approach=solution.get('approach_name', 'N/A'),
        key_innovation=solution.get('key_innovation', 'N/A'),
        previous_round=round_num - 1,
        your_verdict=your_previous_critique.verdict,
        your_score=your_previous_critique.real_world_feasibility,
        your_confidence=getattr(your_previous_critique, 'confidence', 0.5),
        your_strengths=', '.join(your_previous_critique.strengths[:3]),
        your_weaknesses=', '.join(your_previous_critique.weaknesses[:3]),
        your_concerns=', '.join(your_previous_critique.technical_concerns[:2]),
        other_critics_opinions=other_opinions,
        contentious_points=contentious_formatted,
        disagreement_score=disagreement_score,
        focused_areas=focused_formatted
    )


def build_final_refinement_prompt(
    persona_name: str,
    persona_description: str,
    problem: str,
    solution: Dict[str, any],
    round_num: int,
    round_history: List[CritiqueReport],
    agreement_level: float,
    avg_feasibility: float,
    remaining_contentious: List[str]
) -> str:
    """
    Build final refinement prompt for Round 3.
    
    Args:
        persona_name: Critic's role
        persona_description: Critic's expertise
        problem: Problem statement
        solution: Solution proposal
        round_num: Current round (should be 3)
        round_history: List of critic's previous critiques
        agreement_level: Current consensus level
        avg_feasibility: Average feasibility score
        remaining_contentious: Remaining disagreement points
    
    Returns:
        Formatted prompt string
    """
    round1 = round_history[0] if len(round_history) > 0 else None
    round2 = round_history[1] if len(round_history) > 1 else None
    
    round2_changes = "No significant changes" if not round2 else \
        f"Verdict: {round1.verdict} → {round2.verdict}, Score: {round1.real_world_feasibility} → {round2.real_world_feasibility}"
    
    return FINAL_REFINEMENT_PROMPT.format(
        persona_name=persona_name,
        persona_description=persona_description,
        problem_description=problem,
        solution_approach=solution.get('approach_name', 'N/A'),
        round_num=round_num,
        round1_verdict=round1.verdict if round1 else "N/A",
        round1_score=round1.real_world_feasibility if round1 else 0,
        round1_confidence=getattr(round1, 'confidence', 0.5) if round1 else 0,
        round2_verdict=round2.verdict if round2 else "N/A",
        round2_score=round2.real_world_feasibility if round2 else 0,
        round2_confidence=getattr(round2, 'confidence', 0.5) if round2 else 0,
        round2_changes=round2_changes,
        agreement_level=agreement_level,
        avg_feasibility=avg_feasibility,
        remaining_contentious=format_contentious_points(remaining_contentious)
    )
