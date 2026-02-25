"""
Logfire Configuration
======================

One-line setup for automatic distributed tracing with Logfire.

Logfire provides:
- Automatic LLM call tracing
- Performance metrics
- Error tracking
- Request/response logging
- Distributed tracing across agents

Setup:
    ```python
    from src.observability import configure_logfire
    
    # One-line setup
    configure_logfire()
    
    # Now all Pydantic AI agents automatically get traced!
    ```
"""

import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def configure_logfire(
    token: Optional[str] = None,
    service_name: str = "auto-git",
    environment: str = "development",
    enable_console: bool = True,
    log_level: str = "INFO"
) -> None:
    """
    Configure Logfire for automatic observability.
    
    This enables:
    - Automatic tracing of all Pydantic AI agents
    - LLM call logging (prompts, responses, tokens)
    - Performance metrics (latency, token usage)
    - Error tracking with stack traces
    - Distributed tracing across agents
    
    Args:
        token: Logfire API token (or set LOGFIRE_TOKEN env var)
        service_name: Service name for identifying logs
        environment: Environment (development/staging/production)
        enable_console: Also log to console
        log_level: Logging level (DEBUG/INFO/WARNING/ERROR)
    
    Example:
        ```python
        # Set token via environment variable
        export LOGFIRE_TOKEN="your-token-here"
        
        # Or pass directly
        configure_logfire(token="your-token-here")
        
        # All Pydantic AI agents now automatically traced!
        agent = CodeGeneratorAgent()
        result = await agent.generate("Write code")  # ← Automatically traced
        ```
    
    To get a Logfire token:
        1. Go to https://logfire.pydantic.dev
        2. Sign up (free tier available)
        3. Create new project
        4. Copy API token
        5. Set LOGFIRE_TOKEN environment variable
    """
    try:
        import logfire
        
        # Get token from argument or environment
        api_token = token or os.getenv("LOGFIRE_TOKEN")
        
        if not api_token:
            logger.warning(
                "No Logfire token provided. Tracing will be disabled.\n"
                "To enable:\n"
                "  1. Get token from https://logfire.pydantic.dev\n"
                "  2. Set LOGFIRE_TOKEN environment variable\n"
                "  3. Or pass token to configure_logfire()"
            )
            return
        
        # Configure Logfire
        logfire.configure(
            token=api_token,
            service_name=service_name,
            environment=environment,
            console=enable_console,
            send_to_logfire=True,
        )
        
        # Instrument Pydantic AI automatically
        logfire.instrument_pydantic()
        
        # Optional: Instrument other libraries
        try:
            logfire.instrument_asyncio()
        except Exception:
            pass  # Not critical if this fails
        
        logger.info(
            f"✅ Logfire configured successfully!\n"
            f"   Service: {service_name}\n"
            f"   Environment: {environment}\n"
            f"   Dashboard: https://logfire.pydantic.dev"
        )
    
    except ImportError:
        logger.error(
            "Logfire not installed. Install with:\n"
            "  pip install logfire\n"
            "Or:\n"
            "  pip install -r requirements-upgrade.txt"
        )
        raise
    
    except Exception as e:
        logger.error(f"Failed to configure Logfire: {e}")
        raise


def configure_logfire_offline() -> None:
    """
    Configure Logfire in offline mode (no data sent to cloud).
    
    Useful for:
    - Local development without internet
    - Testing without using token quota
    - Privacy-sensitive environments
    
    Logs will still be written to console but NOT sent to Logfire dashboard.
    """
    try:
        import logfire
        
        logfire.configure(
            send_to_logfire=False,
            console=True,
        )
        
        logfire.instrument_pydantic()
        
        logger.info("✅ Logfire configured in OFFLINE mode (console only)")
    
    except ImportError:
        logger.error("Logfire not installed. Install with: pip install logfire")
        raise


def get_current_trace_id() -> Optional[str]:
    """
    Get the current trace ID for linking logs.
    
    Returns:
        Trace ID string or None
    """
    try:
        import logfire
        from logfire import get_current_span
        
        span = get_current_span()
        if span:
            return span.get_span_context().trace_id
        
        return None
    
    except Exception:
        return None


# Auto-configure on import if token is set
if os.getenv("LOGFIRE_TOKEN"):
    try:
        configure_logfire()
    except Exception as e:
        logger.warning(f"Auto-configuration of Logfire failed: {e}")
