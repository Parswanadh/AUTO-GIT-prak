"""
Intelligent Model Router

Automatically selects the best model for each task type based on:
- Task characteristics (coding, reasoning, tool calling, etc.)
- Model performance benchmarks
- Resource availability (VRAM, speed requirements)
- Historical performance data
"""

import logging
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of tasks for model selection"""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    CODE_REFACTORING = "code_refactoring"
    DEBUGGING = "debugging"
    REASONING = "reasoning"
    PLANNING = "planning"
    TOOL_CALLING = "tool_calling"
    EMBEDDINGS = "embeddings"
    VISION = "vision"
    GENERAL = "general"
    FAST_RESPONSE = "fast_response"


@dataclass
class ModelCapability:
    """Model capabilities and characteristics"""
    name: str
    task_scores: Dict[TaskType, float]  # 0-100 score for each task
    vram_gb: float
    speed_rating: float  # 1-5, higher is faster
    context_window: int
    special_features: List[str]
    download_count: int  # Popularity indicator
    updated_months_ago: int


class ModelRouter:
    """
    Intelligent router that selects optimal model for each task
    
    Features:
    - Task-based model selection
    - Performance-aware routing
    - Fallback handling
    - Resource-aware selection
    """
    
    def __init__(self):
        """Initialize model router with SOTA model capabilities"""
        self.models = self._initialize_model_registry()
        self.performance_history: Dict[str, List[float]] = {}
        logger.info(f"Model router initialized with {len(self.models)} models")
    
    def _initialize_model_registry(self) -> Dict[str, ModelCapability]:
        """Initialize registry with SOTA models"""
        return {
            # Primary coding model - Best for code generation
            "qwen2.5-coder:7b": ModelCapability(
                name="qwen2.5-coder:7b",
                task_scores={
                    TaskType.CODE_GENERATION: 95,
                    TaskType.CODE_REVIEW: 90,
                    TaskType.CODE_REFACTORING: 92,
                    TaskType.DEBUGGING: 88,
                    TaskType.REASONING: 75,
                    TaskType.PLANNING: 70,
                    TaskType.TOOL_CALLING: 60,
                    TaskType.GENERAL: 80,
                    TaskType.FAST_RESPONSE: 65,
                },
                vram_gb=5.0,
                speed_rating=4.0,
                context_window=32768,
                special_features=["multi-language", "code-repair", "40+ languages"],
                download_count=10_300_000,
                updated_months_ago=8
            ),
            
            # Reasoning specialist - Best for complex logic
            "deepseek-r1:8b": ModelCapability(
                name="deepseek-r1:8b",
                task_scores={
                    TaskType.CODE_GENERATION: 80,
                    TaskType.CODE_REVIEW: 85,
                    TaskType.CODE_REFACTORING: 75,
                    TaskType.DEBUGGING: 90,
                    TaskType.REASONING: 98,
                    TaskType.PLANNING: 95,
                    TaskType.TOOL_CALLING: 70,
                    TaskType.GENERAL: 85,
                    TaskType.FAST_RESPONSE: 50,
                },
                vram_gb=6.0,
                speed_rating=3.0,
                context_window=128000,
                special_features=["thinking-mode", "o3-level-reasoning", "math-expert"],
                download_count=76_900_000,
                updated_months_ago=6
            ),
            
            # Fast tool caller - Best for agent coordination
            "phi4-mini:3.8b": ModelCapability(
                name="phi4-mini:3.8b",
                task_scores={
                    TaskType.CODE_GENERATION: 65,
                    TaskType.CODE_REVIEW: 60,
                    TaskType.CODE_REFACTORING: 55,
                    TaskType.DEBUGGING: 60,
                    TaskType.REASONING: 70,
                    TaskType.PLANNING: 75,
                    TaskType.TOOL_CALLING: 95,
                    TaskType.GENERAL: 75,
                    TaskType.FAST_RESPONSE: 90,
                },
                vram_gb=3.0,
                speed_rating=5.0,
                context_window=16384,
                special_features=["function-calling", "multilingual", "microsoft-enterprise"],
                download_count=786_000,
                updated_months_ago=11
            ),
            
            # Newest flash model - High quality but slow (19GB model)
            "glm-4.7-flash:latest": ModelCapability(
                name="glm-4.7-flash:latest",
                task_scores={
                    TaskType.CODE_GENERATION: 85,
                    TaskType.CODE_REVIEW: 80,
                    TaskType.CODE_REFACTORING: 78,
                    TaskType.DEBUGGING: 82,
                    TaskType.REASONING: 88,
                    TaskType.PLANNING: 85,
                    TaskType.TOOL_CALLING: 75,
                    TaskType.GENERAL: 90,
                    TaskType.FAST_RESPONSE: 40,  # Slow: 2-3 tokens/sec
                },
                vram_gb=7.0,
                speed_rating=2.0,  # Updated: Actually slow (2-3 tokens/sec)
                context_window=28000,
                special_features=["tools", "thinking", "strongest-30B-class", "slow-inference"],
                download_count=28_000,
                updated_months_ago=0
            ),
            
            # General purpose model
            "qwen3:8b": ModelCapability(
                name="qwen3:8b",
                task_scores={
                    TaskType.CODE_GENERATION: 75,
                    TaskType.CODE_REVIEW: 75,
                    TaskType.CODE_REFACTORING: 70,
                    TaskType.DEBUGGING: 70,
                    TaskType.REASONING: 80,
                    TaskType.PLANNING: 78,
                    TaskType.TOOL_CALLING: 65,
                    TaskType.GENERAL: 85,
                    TaskType.FAST_RESPONSE: 70,
                },
                vram_gb=5.2,
                speed_rating=4.0,
                context_window=32768,
                special_features=["moe-architecture", "general-purpose"],
                download_count=18_000_000,
                updated_months_ago=3
            ),
            
            # Lightweight fast model
            "qwen3:4b": ModelCapability(
                name="qwen3:4b",
                task_scores={
                    TaskType.CODE_GENERATION: 60,
                    TaskType.CODE_REVIEW: 55,
                    TaskType.CODE_REFACTORING: 50,
                    TaskType.DEBUGGING: 55,
                    TaskType.REASONING: 65,
                    TaskType.PLANNING: 60,
                    TaskType.TOOL_CALLING: 70,
                    TaskType.GENERAL: 70,
                    TaskType.FAST_RESPONSE: 95,
                },
                vram_gb=2.5,
                speed_rating=5.0,
                context_window=32768,
                special_features=["lightweight", "fast-inference"],
                download_count=5_000_000,
                updated_months_ago=4
            ),
            
            # Ultra-fast model
            "qwen3:0.6b": ModelCapability(
                name="qwen3:0.6b",
                task_scores={
                    TaskType.CODE_GENERATION: 40,
                    TaskType.CODE_REVIEW: 35,
                    TaskType.CODE_REFACTORING: 30,
                    TaskType.DEBUGGING: 35,
                    TaskType.REASONING: 45,
                    TaskType.PLANNING: 40,
                    TaskType.TOOL_CALLING: 60,
                    TaskType.GENERAL: 50,
                    TaskType.FAST_RESPONSE: 100,
                },
                vram_gb=0.5,
                speed_rating=5.0,
                context_window=32768,
                special_features=["ultra-fast", "minimal-vram"],
                download_count=2_000_000,
                updated_months_ago=4
            ),
            
            # Vision model
            "qwen3-vl:4b": ModelCapability(
                name="qwen3-vl:4b",
                task_scores={
                    TaskType.CODE_GENERATION: 50,
                    TaskType.VISION: 90,
                    TaskType.GENERAL: 65,
                    TaskType.FAST_RESPONSE: 70,
                },
                vram_gb=3.3,
                speed_rating=4.0,
                context_window=32768,
                special_features=["vision", "multimodal"],
                download_count=1_000_000,
                updated_months_ago=3
            ),
            
            # Embeddings model
            "nomic-embed-text:latest": ModelCapability(
                name="nomic-embed-text:latest",
                task_scores={
                    TaskType.EMBEDDINGS: 95,
                },
                vram_gb=0.3,
                speed_rating=5.0,
                context_window=8192,
                special_features=["embeddings", "semantic-caching"],
                download_count=5_000_000,
                updated_months_ago=1
            ),
        }
    
    def select_model(
        self,
        task_type: TaskType,
        require_speed: bool = False,
        max_vram_gb: Optional[float] = None,
        context_length: Optional[int] = None
    ) -> str:
        """
        Select best model for task
        
        Args:
            task_type: Type of task to perform
            require_speed: Prioritize speed over quality
            max_vram_gb: Maximum VRAM constraint (None = no limit)
            context_length: Required context window size
            
        Returns:
            Model name
        """
        candidates = []
        
        for name, capability in self.models.items():
            # Filter by task support
            if task_type not in capability.task_scores:
                continue
            
            # Filter by VRAM constraint
            if max_vram_gb and capability.vram_gb > max_vram_gb:
                continue
            
            # Filter by context window
            if context_length and capability.context_window < context_length:
                continue
            
            # Calculate score
            task_score = capability.task_scores[task_type]
            
            # Adjust for speed requirement
            if require_speed:
                speed_weight = 0.4
                quality_weight = 0.6
                final_score = (task_score * quality_weight) + (capability.speed_rating * 20 * speed_weight)
            else:
                final_score = task_score
            
            # Bonus for recent updates (freshness matters)
            freshness_bonus = max(0, 10 - capability.updated_months_ago)
            final_score += freshness_bonus
            
            # Bonus for popularity (community validation)
            if capability.download_count > 10_000_000:
                final_score += 5
            
            candidates.append((name, final_score, capability))
        
        if not candidates:
            logger.warning(f"No model found for {task_type}, using fallback")
            return self._get_fallback_model()
        
        # Sort by score (descending)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        selected_model = candidates[0][0]
        selected_score = candidates[0][1]
        
        logger.info(
            f"Selected '{selected_model}' for {task_type.value} "
            f"(score: {selected_score:.1f}, alternatives: {len(candidates)-1})"
        )
        
        return selected_model
    
    def get_model_for_stage(self, stage: str) -> str:
        """Get optimal model for pipeline stage"""
        stage_mapping = {
            "idea_generation": TaskType.REASONING,
            "planning": TaskType.PLANNING,
            "code_generation": TaskType.CODE_GENERATION,
            "code_review": TaskType.CODE_REVIEW,
            "debugging": TaskType.DEBUGGING,
            "refactoring": TaskType.CODE_REFACTORING,
            "testing": TaskType.CODE_GENERATION,
            "documentation": TaskType.CODE_GENERATION,
        }
        
        task_type = stage_mapping.get(stage, TaskType.GENERAL)
        return self.select_model(task_type)
    
    def get_routing_strategy(self, pipeline_type: str) -> Dict[str, str]:
        """Get complete routing strategy for pipeline"""
        if pipeline_type == "quality":
            return {
                "planning": self.select_model(TaskType.REASONING),
                "code_generation": self.select_model(TaskType.CODE_GENERATION),
                "code_review": self.select_model(TaskType.CODE_REVIEW),
                "refactoring": self.select_model(TaskType.CODE_REFACTORING),
                "debugging": self.select_model(TaskType.DEBUGGING),
            }
        elif pipeline_type == "fast":
            return {
                "planning": self.select_model(TaskType.PLANNING, require_speed=True),
                "code_generation": self.select_model(TaskType.CODE_GENERATION, require_speed=True),
                "code_review": self.select_model(TaskType.CODE_REVIEW, require_speed=True),
            }
        else:  # balanced
            return {
                "planning": self.select_model(TaskType.PLANNING),
                "code_generation": self.select_model(TaskType.CODE_GENERATION),
                "code_review": self.select_model(TaskType.CODE_REVIEW),
                "debugging": self.select_model(TaskType.DEBUGGING),
            }
    
    def _get_fallback_model(self) -> str:
        """Get fallback model when no match found"""
        if "qwen3:8b" in self.models:
            return "qwen3:8b"
        elif "glm-4.7-flash:latest" in self.models:
            return "glm-4.7-flash:latest"
        else:
            return list(self.models.keys())[0]
    
    def get_model_info(self, model: str) -> Optional[ModelCapability]:
        """Get detailed information about a model"""
        return self.models.get(model)
    
    def list_models_for_task(self, task_type: TaskType) -> List[tuple]:
        """List all models capable of handling a task, sorted by suitability"""
        results = []
        
        for name, capability in self.models.items():
            if task_type in capability.task_scores:
                score = capability.task_scores[task_type]
                results.append((name, score, capability))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def get_recommended_models(self) -> Dict[str, List[str]]:
        """Get recommended models for each task category"""
        recommendations = {}
        
        for task_type in TaskType:
            models = self.list_models_for_task(task_type)
            if models:
                recommendations[task_type.value] = [m[0] for m in models[:3]]
        
        return recommendations
