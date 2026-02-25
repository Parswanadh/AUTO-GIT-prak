"""
Base Specialist - Integration #15

Abstract base class for all specialist agents.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseSpecialist(ABC):
    """
    Abstract base class for specialist agents.
    
    Each specialist handles a specific type of subtask:
    - Code Specialist: Implementation
    - Test Specialist: Test generation
    - Doc Specialist: Documentation
    - Architecture Specialist: System design
    - Performance Specialist: Optimization
    """
    
    def __init__(self, specialty: str, llm_router=None):
        """
        Initialize specialist.
        
        Args:
            specialty: Specialty identifier (e.g., "code", "testing")
            llm_router: Optional HybridRouter for LLM calls
        """
        self.specialty = specialty
        self.llm_router = llm_router
        logger.info(f"{self.specialty.capitalize()} specialist initialized")
    
    @abstractmethod
    async def execute(self, subtask) -> Dict[str, Any]:
        """
        Execute a subtask.
        
        Args:
            subtask: Subtask object with description and context
            
        Returns:
            Dictionary with execution results
        """
        pass
    
    def _create_result(self,
                      content: str,
                      metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create standardized result dictionary.
        
        Args:
            content: Main result content
            metadata: Optional metadata
            
        Returns:
            Standardized result dictionary
        """
        return {
            "specialty": self.specialty,
            "content": content,
            "metadata": metadata or {}
        }
