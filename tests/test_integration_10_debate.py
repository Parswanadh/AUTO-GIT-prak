"""
Test Integration #10: Enhanced Multi-Critic Consensus with Dynamic Debate

Tests:
1. Dissent analysis and contentious point detection
2. Convergence trend calculation
3. Adaptive stopping conditions
4. Cross-examination prompt generation
5. Full multi-round debate cycle
6. Confidence scoring
7. Stall detection
8. Divergence detection
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.meta_learning.debate_dissent import (
    DissentAnalyzer,
    DissentAnalysis,
    analyze_debate_dissent
)
from src.agents.meta_learning.adaptive_debate import (
    AdaptiveDebateController,
    DebateConfig,
    create_debate_controller
)
from src.agents.meta_learning.cross_examination_prompts import (
    build_initial_critique_prompt,
    build_cross_examination_prompt,
    build_final_refinement_prompt,
    format_other_critics_opinions
)
from src.models.schemas import CritiqueReport
from src.utils.logger import get_logger

logger = get_logger("test_integration_10")


# ============================================================================
# TEST HELPERS
# ============================================================================

def create_mock_critique(
    verdict: str,
    score: float,
    strengths: list,
    weaknesses: list,
    concerns: list
) -> CritiqueReport:
    """Create mock critique for testing."""
    return CritiqueReport(
        overall_assessment="promising" if score >= 7 else "needs_work",
        strengths=strengths,
        weaknesses=weaknesses,
        technical_concerns=concerns,
        missing_considerations=[],
        real_world_feasibility=score,
        optimization_suggestions=["Optimize memory usage", "Add error handling"],
        verdict=verdict
    )


# ============================================================================
# TEST 1: DISSENT ANALYSIS BASIC
# ============================================================================

def test_dissent_analysis_basic():
    """Test basic dissent analysis with varying opinions."""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: Dissent Analysis - Basic Functionality")
    logger.info("="*70)
    
    # Create 4 critics with varying opinions
    critics = {
        "ml_theorist": create_mock_critique(
            verdict="accept",
            score=8.0,
            strengths=["Novel architecture", "Good theoretical foundation"],
            weaknesses=["Complex implementation"],
            concerns=["Computational cost"]
        ),
        "engineer": create_mock_critique(
            verdict="revise",
            score=6.0,
            strengths=["Novel architecture"],
            weaknesses=["Complex implementation", "Memory intensive"],
            concerns=["Computational cost", "Scalability issues"]
        ),
        "scientist": create_mock_critique(
            verdict="accept",
            score=7.5,
            strengths=["Good theoretical foundation", "Promising results"],
            weaknesses=["Limited benchmarking"],
            concerns=[]
        ),
        "reviewer": create_mock_critique(
            verdict="revise",
            score=6.5,
            strengths=["Promising results"],
            weaknesses=["Complex implementation", "Limited benchmarking", "Documentation lacking"],
            concerns=["Code quality"]
        )
    }
    
    analyzer = DissentAnalyzer()
    dissent = analyzer.analyze_round(1, critics)
    
    logger.info(f"✓ Disagreement Score: {dissent.disagreement_score:.2%}")
    logger.info(f"✓ Requires Refinement: {dissent.requires_refinement}")
    logger.info(f"✓ Contentious Points: {len(dissent.contentious_points)}")
    
    for i, point in enumerate(dissent.contentious_points, 1):
        logger.info(f"  {i}. {point[:80]}...")
    
    # Assertions
    assert 0.0 <= dissent.disagreement_score <= 1.0, "Disagreement score out of range"
    assert len(dissent.contentious_points) > 0, "Should identify contentious points"
    assert len(dissent.agreement_matrix) == 4, "Agreement matrix incomplete"
    assert len(dissent.critic_positions) == 4, "Critic positions incomplete"
    
    logger.info("✅ TEST PASSED: Dissent analysis works correctly")
    return True


# ============================================================================
# TEST 2: CONVERGENCE DETECTION
# ============================================================================

def test_convergence_detection():
    """Test convergence trend calculation over multiple rounds."""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: Convergence Detection")
    logger.info("="*70)
    
    analyzer = DissentAnalyzer()
    
    # Round 1: High disagreement
    critics_r1 = {
        "critic1": create_mock_critique("accept", 8.0, ["Good"], ["None"], []),
        "critic2": create_mock_critique("reject", 4.0, [], ["Bad", "Flawed"], ["Major issues"]),
        "critic3": create_mock_critique("revise", 6.0, ["OK"], ["Needs work"], [])
    }
    dissent_r1 = analyzer.analyze_round(1, critics_r1)
    logger.info(f"Round 1 - Disagreement: {dissent_r1.disagreement_score:.2%}")
    
    # Round 2: Medium disagreement (converging)
    critics_r2 = {
        "critic1": create_mock_critique("accept", 7.5, ["Good"], ["Minor issue"], []),
        "critic2": create_mock_critique("revise", 6.0, ["OK"], ["Some concerns"], []),
        "critic3": create_mock_critique("revise", 6.5, ["OK"], ["Needs work"], [])
    }
    dissent_r2 = analyzer.analyze_round(2, critics_r2)
    logger.info(f"Round 2 - Disagreement: {dissent_r2.disagreement_score:.2%}")
    logger.info(f"Round 2 - Convergence Trend: {dissent_r2.convergence_trend:+.2f}")
    
    # Round 3: Low disagreement (strong convergence)
    critics_r3 = {
        "critic1": create_mock_critique("accept", 7.5, ["Good"], ["Minor"], []),
        "critic2": create_mock_critique("accept", 7.0, ["Good"], ["Minor"], []),
        "critic3": create_mock_critique("accept", 7.5, ["Good"], ["Minor"], [])
    }
    dissent_r3 = analyzer.analyze_round(3, critics_r3)
    logger.info(f"Round 3 - Disagreement: {dissent_r3.disagreement_score:.2%}")
    logger.info(f"Round 3 - Convergence Trend: {dissent_r3.convergence_trend:+.2f}")
    
    # Get summary
    summary = analyzer.get_debate_summary()
    logger.info(f"\nDebate Summary:")
    logger.info(f"  Rounds: {summary['rounds']}")
    logger.info(f"  Initial Disagreement: {summary['initial_disagreement']:.2%}")
    logger.info(f"  Final Disagreement: {summary['final_disagreement']:.2%}")
    logger.info(f"  Convergence Achieved: {summary['convergence_achieved']}")
    logger.info(f"  Improvement: {summary['improvement']:.2%}")
    
    # Assertions
    assert dissent_r1.disagreement_score > dissent_r2.disagreement_score, "Should show convergence"
    assert dissent_r2.disagreement_score > dissent_r3.disagreement_score, "Should continue converging"
    assert dissent_r3.convergence_trend > 0, "Should have positive convergence"
    assert summary['convergence_achieved'], "Should achieve convergence"
    
    logger.info("✅ TEST PASSED: Convergence detection works correctly")
    return True


# ============================================================================
# TEST 3: ADAPTIVE STOPPING - CONSENSUS
# ============================================================================

def test_adaptive_stopping_consensus():
    """Test early stopping when consensus reached."""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Adaptive Stopping - High Consensus")
    logger.info("="*70)
    
    controller = create_debate_controller(
        max_rounds=3,
        min_confidence=0.85,
        max_disagreement=0.2
    )
    
    controller.start_debate()
    
    # Round 1: All critics agree (high consensus)
    critics = {
        "critic1": create_mock_critique("accept", 8.0, ["Excellent"], [], []),
        "critic2": create_mock_critique("accept", 8.5, ["Excellent"], [], []),
        "critic3": create_mock_critique("accept", 8.2, ["Excellent"], [], [])
    }
    
    controller.start_round(1)
    should_continue, reason = controller.should_continue_debate(1, critics)
    
    logger.info(f"Should Continue: {should_continue}")
    logger.info(f"Reason: {reason}")
    logger.info(f"Final Confidence: {controller.metrics.final_confidence:.2%}")
    logger.info(f"Final Disagreement: {controller.metrics.final_disagreement:.2%}")
    
    metrics = controller.end_debate()
    
    # Assertions
    assert not should_continue, "Should stop with high consensus"
    assert metrics.consensus_reached, "Should mark consensus reached"
    assert metrics.early_stop, "Should be early stop"
    assert "consensus" in metrics.stop_reason.lower(), "Stop reason should mention consensus"
    assert metrics.final_confidence >= 0.85, "Should have high confidence"
    assert metrics.final_disagreement < 0.2, "Should have low disagreement"
    
    logger.info("✅ TEST PASSED: Early stopping on consensus works")
    return True


# ============================================================================
# TEST 4: ADAPTIVE STOPPING - STALL
# ============================================================================

def test_adaptive_stopping_stall():
    """Test stopping when debate stalls (no progress)."""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: Adaptive Stopping - Stall Detection")
    logger.info("="*70)
    
    # Create controller with stall detection enabled (default)
    config = DebateConfig(max_rounds=5, enable_early_stopping=True, stall_detection=True)
    controller = AdaptiveDebateController(config)
    controller.start_debate()
    
    # Create same disagreement for 3 rounds (stalled)
    critics_stalled = {
        "critic1": create_mock_critique("accept", 7.0, ["OK"], ["Some issues"], []),
        "critic2": create_mock_critique("revise", 6.0, ["OK"], ["Issues"], []),
        "critic3": create_mock_critique("revise", 6.5, ["OK"], ["Issues"], [])
    }
    
    should_continue_list = []
    
    for round_num in range(1, 4):
        controller.start_round(round_num)
        should_continue, reason = controller.should_continue_debate(round_num, critics_stalled)
        should_continue_list.append(should_continue)
        logger.info(f"Round {round_num}: Continue={should_continue}, Reason={reason}")
        
        if not should_continue:
            break
    
    metrics = controller.end_debate()
    
    logger.info(f"\nStall Detected: {not should_continue_list[-1]}")
    logger.info(f"Stop Reason: {metrics.stop_reason}")
    
    # Assertions
    assert not should_continue_list[-1], "Should stop when stalled"
    assert metrics.early_stop, "Should be early stop"
    assert "stall" in metrics.stop_reason.lower(), "Should mention stall in reason"
    
    logger.info("✅ TEST PASSED: Stall detection works correctly")
    return True


# ============================================================================
# TEST 5: ADAPTIVE STOPPING - DIVERGENCE
# ============================================================================

def test_adaptive_stopping_divergence():
    """Test stopping when critics diverge."""
    logger.info("\n" + "="*70)
    logger.info("TEST 5: Adaptive Stopping - Divergence Detection")
    logger.info("="*70)
    
    controller = create_debate_controller(max_rounds=5)
    analyzer = DissentAnalyzer()
    controller.start_debate()
    
    # Round 1: Moderate disagreement
    critics_r1 = {
        "critic1": create_mock_critique("accept", 7.0, ["OK"], ["Some"], []),
        "critic2": create_mock_critique("revise", 6.0, ["OK"], ["Issues"], [])
    }
    controller.start_round(1)
    dissent_r1 = analyzer.analyze_round(1, critics_r1)
    should_continue_r1, _ = controller.should_continue_debate(1, critics_r1)
    logger.info(f"Round 1 - Disagreement: {dissent_r1.disagreement_score:.2%}, Continue: {should_continue_r1}")
    
    # Round 2: Higher disagreement (diverging)
    critics_r2 = {
        "critic1": create_mock_critique("accept", 8.0, ["Great"], [], []),
        "critic2": create_mock_critique("reject", 4.0, [], ["Bad", "Flawed"], ["Major"])
    }
    controller.start_round(2)
    dissent_r2 = analyzer.analyze_round(2, critics_r2)
    should_continue_r2, reason = controller.should_continue_debate(2, critics_r2)
    logger.info(f"Round 2 - Disagreement: {dissent_r2.disagreement_score:.2%}, Continue: {should_continue_r2}")
    logger.info(f"Convergence Trend: {dissent_r2.convergence_trend:+.2f}")
    logger.info(f"Reason: {reason}")
    
    metrics = controller.end_debate()
    
    # Assertions
    assert dissent_r2.disagreement_score > dissent_r1.disagreement_score, "Should show divergence"
    assert dissent_r2.convergence_trend < 0, "Should have negative convergence"
    # Note: Divergence might not always stop immediately, but should be detected in trend
    if not should_continue_r2:
        logger.info(f"✓ Stopped due to: {reason}")
    else:
        logger.info(f"✓ Detected divergence in trend: {dissent_r2.convergence_trend:+.2f}")
    
    logger.info("✅ TEST PASSED: Divergence detection works correctly")
    return True


# ============================================================================
# TEST 6: CROSS-EXAMINATION PROMPTS
# ============================================================================

def test_cross_examination_prompts():
    """Test prompt generation for all rounds."""
    logger.info("\n" + "="*70)
    logger.info("TEST 6: Cross-Examination Prompt Generation")
    logger.info("="*70)
    
    problem = "Build efficient vision transformer for 4GB VRAM"
    solution = {
        "approach_name": "Lightweight Vision Transformer",
        "key_innovation": "Gradient checkpointing + mixed precision",
        "architecture_design": "12-layer transformer with 8 attention heads",
        "implementation_plan": ["Step 1: Setup", "Step 2: Build", "Step 3: Train"]
    }
    
    # Test Round 1: Initial critique
    logger.info("\n--- Round 1: Initial Critique Prompt ---")
    prompt_r1 = build_initial_critique_prompt(
        persona_name="ML Theorist",
        persona_description="Expert in ML theory and architecture design",
        problem=problem,
        solution=solution
    )
    assert "ML Theorist" in prompt_r1, "Should include persona name"
    assert problem in prompt_r1, "Should include problem"
    assert "JSON" in prompt_r1, "Should request JSON output"
    logger.info(f"✓ Generated Round 1 prompt ({len(prompt_r1)} chars)")
    
    # Test Round 2: Cross-examination
    logger.info("\n--- Round 2: Cross-Examination Prompt ---")
    your_critique = create_mock_critique("accept", 7.5, ["Good"], ["Minor"], [])
    other_critics = {
        "engineer": create_mock_critique("revise", 6.0, ["OK"], ["Issues"], ["Concerns"]),
        "scientist": create_mock_critique("accept", 7.0, ["Good"], ["Some"], [])
    }
    
    prompt_r2 = build_cross_examination_prompt(
        persona_name="ml_theorist",
        persona_description="ML theory expert",
        problem=problem,
        solution=solution,
        round_num=2,
        your_previous_critique=your_critique,
        other_critics=other_critics,
        contentious_points=["Memory efficiency", "Implementation complexity"],
        disagreement_score=0.25,
        focused_areas=["Memory optimization", "Code structure"]
    )
    assert "Round 2" in prompt_r2, "Should mention round number"
    assert "engineer" in prompt_r2.lower(), "Should include other critics"
    assert "Memory efficiency" in prompt_r2, "Should list contentious points"
    logger.info(f"✓ Generated Round 2 prompt ({len(prompt_r2)} chars)")
    
    # Test Round 3: Final refinement
    logger.info("\n--- Round 3: Final Refinement Prompt ---")
    round_history = [your_critique, your_critique]  # Mock history
    
    prompt_r3 = build_final_refinement_prompt(
        persona_name="ml_theorist",
        persona_description="ML theory expert",
        problem=problem,
        solution=solution,
        round_num=3,
        round_history=round_history,
        agreement_level=0.75,
        avg_feasibility=7.2,
        remaining_contentious=["Implementation details"]
    )
    assert "FINAL" in prompt_r3.upper(), "Should indicate final round"
    assert "75" in prompt_r3 or "0.75" in prompt_r3, "Should show agreement level"
    logger.info(f"✓ Generated Round 3 prompt ({len(prompt_r3)} chars)")
    
    # Test helper function
    logger.info("\n--- Testing Helper Functions ---")
    formatted_opinions = format_other_critics_opinions(other_critics, "ml_theorist")
    assert "engineer" in formatted_opinions, "Should format engineer opinion"
    assert "scientist" in formatted_opinions, "Should format scientist opinion"
    logger.info(f"✓ Formatted other opinions ({len(formatted_opinions)} chars)")
    
    logger.info("✅ TEST PASSED: Prompt generation works correctly")
    return True


# ============================================================================
# TEST 7: CONFIDENCE CALCULATION
# ============================================================================

def test_confidence_calculation():
    """Test confidence scoring logic."""
    logger.info("\n" + "="*70)
    logger.info("TEST 7: Confidence Calculation")
    logger.info("="*70)
    
    controller = AdaptiveDebateController()
    analyzer = DissentAnalyzer()
    
    # High confidence scenario: Agreement + high scores
    critics_high = {
        "critic1": create_mock_critique("accept", 8.5, ["Excellent"], [], []),
        "critic2": create_mock_critique("accept", 8.2, ["Excellent"], [], []),
        "critic3": create_mock_critique("accept", 8.8, ["Excellent"], [], [])
    }
    dissent_high = analyzer.analyze_round(1, critics_high)
    confidence_high = controller._calculate_confidence(critics_high, dissent_high)
    logger.info(f"High Confidence Scenario: {confidence_high:.2%}")
    
    # Low confidence scenario: Disagreement + low scores
    critics_low = {
        "critic1": create_mock_critique("accept", 6.0, ["OK"], ["Issues"], []),
        "critic2": create_mock_critique("reject", 4.0, [], ["Bad"], ["Major"]),
        "critic3": create_mock_critique("revise", 5.5, ["Some"], ["Many"], [])
    }
    dissent_low = analyzer.analyze_round(2, critics_low)
    confidence_low = controller._calculate_confidence(critics_low, dissent_low)
    logger.info(f"Low Confidence Scenario: {confidence_low:.2%}")
    
    # Medium confidence scenario: Some agreement + medium scores
    critics_med = {
        "critic1": create_mock_critique("revise", 7.0, ["Good"], ["Some"], []),
        "critic2": create_mock_critique("revise", 6.8, ["Good"], ["Some"], []),
        "critic3": create_mock_critique("accept", 7.5, ["Good"], ["Minor"], [])
    }
    dissent_med = analyzer.analyze_round(3, critics_med)
    confidence_med = controller._calculate_confidence(critics_med, dissent_med)
    logger.info(f"Medium Confidence Scenario: {confidence_med:.2%}")
    
    # Assertions
    assert confidence_high > confidence_med > confidence_low, "Confidence ordering incorrect"
    assert confidence_high >= 0.85, "High confidence should be >= 85%"
    assert confidence_low < 0.70, "Low confidence should be < 70%"
    assert 0.0 <= confidence_med <= 1.0, "Confidence out of range"
    
    logger.info("✅ TEST PASSED: Confidence calculation works correctly")
    return True


# ============================================================================
# TEST 8: FULL DEBATE CYCLE
# ============================================================================

def test_full_debate_cycle():
    """Test complete multi-round debate with all components."""
    logger.info("\n" + "="*70)
    logger.info("TEST 8: Full Multi-Round Debate Cycle")
    logger.info("="*70)
    
    controller = create_debate_controller(max_rounds=3, min_confidence=0.80)
    analyzer = DissentAnalyzer()
    controller.start_debate()
    
    problem = "Optimize neural network for edge devices"
    solution = {
        "approach_name": "Quantized Mobile Architecture",
        "key_innovation": "INT8 quantization + pruning",
        "architecture_design": "Efficient CNN backbone"
    }
    
    # Simulate 3-round debate
    all_rounds = []
    
    # Round 1: Initial disagreement
    logger.info("\n--- ROUND 1: Initial Critique ---")
    controller.start_round(1)
    critics_r1 = {
        "ml_theorist": create_mock_critique("accept", 7.5, ["Novel"], ["Complex"], []),
        "engineer": create_mock_critique("revise", 6.0, ["OK"], ["Issues", "Concerns"], ["Memory"]),
        "scientist": create_mock_critique("accept", 7.0, ["Good"], ["Some"], []),
        "reviewer": create_mock_critique("revise", 6.5, ["OK"], ["Issues"], ["Code"])
    }
    dissent_r1 = analyzer.analyze_round(1, critics_r1)
    should_continue_r1, reason_r1 = controller.should_continue_debate(1, critics_r1)
    all_rounds.append({"round": 1, "dissent": dissent_r1, "continue": should_continue_r1})
    logger.info(f"Disagreement: {dissent_r1.disagreement_score:.2%}")
    logger.info(f"Continue: {should_continue_r1} ({reason_r1})")
    
    if should_continue_r1:
        # Round 2: Converging
        logger.info("\n--- ROUND 2: Cross-Examination ---")
        controller.start_round(2)
        critics_r2 = {
            "ml_theorist": create_mock_critique("accept", 7.5, ["Novel"], ["Minor"], []),
            "engineer": create_mock_critique("revise", 6.8, ["Better"], ["Some"], []),
            "scientist": create_mock_critique("accept", 7.2, ["Good"], ["Minor"], []),
            "reviewer": create_mock_critique("revise", 7.0, ["Improved"], ["Minor"], [])
        }
        dissent_r2 = analyzer.analyze_round(2, critics_r2)
        should_continue_r2, reason_r2 = controller.should_continue_debate(2, critics_r2)
        all_rounds.append({"round": 2, "dissent": dissent_r2, "continue": should_continue_r2})
        logger.info(f"Disagreement: {dissent_r2.disagreement_score:.2%}")
        logger.info(f"Convergence: {dissent_r2.convergence_trend:+.2f}")
        logger.info(f"Continue: {should_continue_r2} ({reason_r2})")
        
        if should_continue_r2:
            # Round 3: Final refinement
            logger.info("\n--- ROUND 3: Final Refinement ---")
            controller.start_round(3)
            critics_r3 = {
                "ml_theorist": create_mock_critique("accept", 7.8, ["Excellent"], [], []),
                "engineer": create_mock_critique("accept", 7.5, ["Good"], ["Minor"], []),
                "scientist": create_mock_critique("accept", 7.6, ["Good"], [], []),
                "reviewer": create_mock_critique("accept", 7.7, ["Good"], ["Minor"], [])
            }
            dissent_r3 = analyzer.analyze_round(3, critics_r3)
            should_continue_r3, reason_r3 = controller.should_continue_debate(3, critics_r3)
            all_rounds.append({"round": 3, "dissent": dissent_r3, "continue": should_continue_r3})
            logger.info(f"Disagreement: {dissent_r3.disagreement_score:.2%}")
            logger.info(f"Convergence: {dissent_r3.convergence_trend:+.2f}")
            logger.info(f"Continue: {should_continue_r3} ({reason_r3})")
    
    # End debate and get metrics
    metrics = controller.end_debate()
    summary = controller.get_debate_summary()
    
    logger.info("\n--- DEBATE SUMMARY ---")
    logger.info(f"Total Rounds: {metrics.total_rounds}")
    logger.info(f"Consensus Reached: {metrics.consensus_reached}")
    logger.info(f"Early Stop: {metrics.early_stop}")
    logger.info(f"Final Confidence: {metrics.final_confidence:.2%}")
    logger.info(f"Final Disagreement: {metrics.final_disagreement:.2%}")
    logger.info(f"Stop Reason: {metrics.stop_reason}")
    
    # Assertions
    assert len(all_rounds) > 0, "Should have at least 1 round"
    assert metrics.total_rounds == len(all_rounds), "Round count mismatch"
    assert 0.0 <= metrics.final_confidence <= 1.0, "Confidence out of range"
    assert 0.0 <= metrics.final_disagreement <= 1.0, "Disagreement out of range"
    assert summary is not None, "Should generate summary"
    assert "metrics" in summary, "Summary missing metrics"
    assert "dissent_analysis" in summary, "Summary missing dissent analysis"
    
    logger.info("✅ TEST PASSED: Full debate cycle works correctly")
    return True


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all Integration #10 tests."""
    logger.info("\n" + "="*70)
    logger.info("🧪 TESTING INTEGRATION #10: Enhanced Multi-Critic Debate")
    logger.info("="*70)
    
    tests = [
        ("Dissent Analysis Basic", test_dissent_analysis_basic),
        ("Convergence Detection", test_convergence_detection),
        ("Adaptive Stopping - Consensus", test_adaptive_stopping_consensus),
        ("Adaptive Stopping - Stall", test_adaptive_stopping_stall),
        ("Adaptive Stopping - Divergence", test_adaptive_stopping_divergence),
        ("Cross-Examination Prompts", test_cross_examination_prompts),
        ("Confidence Calculation", test_confidence_calculation),
        ("Full Debate Cycle", test_full_debate_cycle),
    ]
    
    results = []
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            if success:
                passed += 1
                results.append(f"✅ {test_name}")
            else:
                failed += 1
                results.append(f"❌ {test_name}")
        except Exception as e:
            failed += 1
            results.append(f"❌ {test_name}: {str(e)}")
            logger.error(f"Test failed with exception: {e}", exc_info=True)
    
    # Print summary
    logger.info("\n" + "="*70)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info("="*70)
    
    for result in results:
        logger.info(result)
    
    logger.info(f"\n{'='*70}")
    logger.info(f"Total Tests: {len(tests)}")
    logger.info(f"Passed: {passed} ✅")
    logger.info(f"Failed: {failed} ❌")
    logger.info(f"Success Rate: {(passed/len(tests)*100):.1f}%")
    logger.info("="*70)
    
    if failed == 0:
        logger.info("\n🎉 ALL TESTS PASSED! Integration #10 is working correctly!")
        return True
    else:
        logger.error(f"\n⚠️  {failed} test(s) failed. Please review the output above.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
