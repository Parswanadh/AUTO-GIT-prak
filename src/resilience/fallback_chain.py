"""
Fallback Chain - Integration #16

Implements fallback chain pattern for graceful degradation.
Tries multiple strategies in order until one succeeds.
"""

import asyncio
import logging
from typing import Any, Callable, List, Dict

logger = logging.getLogger(__name__)


class FallbackExhaustedError(Exception):
    """Raised when all fallback strategies have been exhausted"""
    
    def __init__(self, message: str, last_error: Exception = None):
        super().__init__(message)
        self.last_error = last_error


class FallbackChain:
    """
    Fallback chain for graceful degradation.
    
    Tries primary strategy, then falls back to secondary, tertiary, etc.
    until one succeeds or all fail.
    
    Example:
        async def primary():
            return await expensive_api_call()
        
        async def secondary():
            return await cheaper_api_call()
        
        async def tertiary():
            return default_response
        
        chain = FallbackChain([primary, secondary, tertiary])
        result = await chain.execute()
    """
    
    def __init__(self, strategies: List[Callable], name: str = "unnamed"):
        """
        Initialize fallback chain.
        
        Args:
            strategies: List of async functions to try in order
            name: Name for logging/identification
        """
        if not strategies:
            raise ValueError("Fallback chain must have at least one strategy")
        
        self.name = name
        self.strategies = strategies
        self.stats: Dict[int, int] = {i: 0 for i in range(len(strategies))}
        self.total_calls = 0
        self.total_failures = 0
        
        logger.info(
            f"Fallback chain '{name}' initialized with {len(strategies)} strategies"
        )
    
    async def execute(self, *args, **kwargs) -> Any:
        """
        Execute fallback chain, trying each strategy in order.
        
        Args:
            *args: Arguments to pass to strategies
            **kwargs: Keyword arguments to pass to strategies
            
        Returns:
            Result from first successful strategy
            
        Raises:
            FallbackExhaustedError: If all strategies fail
        """
        self.total_calls += 1
        last_error = None
        
        for i, strategy in enumerate(self.strategies):
            strategy_name = getattr(strategy, '__name__', f'strategy_{i}')
            
            try:
                logger.debug(
                    f"Trying {self.name} strategy {i+1}/{len(self.strategies)}: "
                    f"{strategy_name}"
                )
                
                result = await strategy(*args, **kwargs)
                
                # Success!
                self.stats[i] += 1
                
                if i > 0:
                    # Used fallback
                    logger.info(
                        f"✅ {self.name} succeeded with fallback strategy {i+1}: "
                        f"{strategy_name}"
                    )
                else:
                    # Primary succeeded
                    logger.debug(f"✅ {self.name} primary strategy succeeded")
                
                return result
            
            except Exception as e:
                last_error = e
                logger.warning(
                    f"⚠️  {self.name} strategy {i+1}/{len(self.strategies)} failed: "
                    f"{strategy_name}: {e}"
                )
                continue
        
        # All strategies failed
        self.total_failures += 1
        logger.error(
            f"❌ {self.name} all {len(self.strategies)} fallback strategies exhausted"
        )
        
        raise FallbackExhaustedError(
            f"All {len(self.strategies)} fallback strategies failed for '{self.name}'",
            last_error=last_error
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get fallback usage statistics.
        
        Returns:
            Dictionary with stats for each strategy
        """
        return {
            "name": self.name,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "success_rate": (
                (self.total_calls - self.total_failures) / self.total_calls
                if self.total_calls > 0 else 0.0
            ),
            "strategy_usage": {
                f"strategy_{i}": {
                    "count": count,
                    "percentage": (count / self.total_calls * 100)
                    if self.total_calls > 0 else 0.0
                }
                for i, count in self.stats.items()
            },
            "primary_success_rate": (
                self.stats[0] / self.total_calls
                if self.total_calls > 0 else 0.0
            ),
            "fallback_usage_rate": (
                sum(self.stats[i] for i in range(1, len(self.strategies)))
                / self.total_calls
                if self.total_calls > 0 else 0.0
            ),
        }
    
    def reset_statistics(self):
        """Reset all statistics"""
        self.stats = {i: 0 for i in range(len(self.strategies))}
        self.total_calls = 0
        self.total_failures = 0


if __name__ == "__main__":
    # Quick test
    async def test():
        print("Testing Fallback Chain\n")
        
        # Test 1: Primary succeeds
        print("Test 1: Primary strategy succeeds")
        
        async def primary_succeeds():
            return "primary success"
        
        async def secondary():
            return "secondary"
        
        chain = FallbackChain([primary_succeeds, secondary], name="test_chain_1")
        result = await chain.execute()
        print(f"  Result: {result}")
        print(f"  Stats: {chain.get_statistics()}")
        
        # Test 2: Primary fails, secondary succeeds
        print("\nTest 2: Primary fails, secondary succeeds")
        
        async def primary_fails():
            raise Exception("Primary failed")
        
        async def secondary_succeeds():
            return "secondary success"
        
        chain = FallbackChain(
            [primary_fails, secondary_succeeds],
            name="test_chain_2"
        )
        result = await chain.execute()
        print(f"  Result: {result}")
        print(f"  Stats: {chain.get_statistics()}")
        
        # Test 3: All fail
        print("\nTest 3: All strategies fail")
        
        async def fails_1():
            raise Exception("Strategy 1 failed")
        
        async def fails_2():
            raise Exception("Strategy 2 failed")
        
        async def fails_3():
            raise Exception("Strategy 3 failed")
        
        chain = FallbackChain([fails_1, fails_2, fails_3], name="test_chain_3")
        
        try:
            await chain.execute()
        except FallbackExhaustedError as e:
            print(f"  ✅ Correctly raised FallbackExhaustedError: {e}")
            print(f"  Last error: {e.last_error}")
        
        # Test 4: Multiple calls
        print("\nTest 4: Multiple calls with mixed results")
        
        call_count = 0
        
        async def sometimes_fails():
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise Exception("Even call failed")
            return "odd success"
        
        async def always_succeeds():
            return "fallback success"
        
        chain = FallbackChain(
            [sometimes_fails, always_succeeds],
            name="test_chain_4"
        )
        
        for i in range(5):
            result = await chain.execute()
            print(f"  Call {i+1}: {result}")
        
        print(f"\n📊 Final stats: {chain.get_statistics()}")
    
    asyncio.run(test())
