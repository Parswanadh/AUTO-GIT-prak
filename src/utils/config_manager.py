"""
Centralized configuration management for AUTO-GIT.

Features:
- YAML-based configuration
- Environment variable overrides
- Validation on load
- Type-safe access with defaults
- Config hot-reload support
"""

import os
import yaml
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, TypeVar, Generic
from functools import lru_cache

from src.utils.logger import get_logger
from src.utils.error_types import ConfigurationError

logger = get_logger("config_manager")


class ConfigProvider(Enum):
    """LLM provider options."""
    OLLAMA = "ollama"
    GLM = "glm"
    CLAUDE = "claude"
    OPENAI = "openai"


@dataclass
class OllamaConfig:
    """Ollama LLM configuration."""
    base_url: str = "http://localhost:11434"
    timeout: int = 120
    default_model: str = "qwen3:8b"
    fallback_model: str = "gemma2:2b"


@dataclass
class RetryConfig:
    """Retry behavior configuration."""
    max_attempts: int = 3
    min_wait_seconds: float = 1.0
    max_wait_seconds: float = 60.0
    exponential_base: int = 2


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    cooldown_seconds: int = 300


@dataclass
class ValidationConfig:
    """Code validation configuration."""
    enabled: bool = True
    min_score: float = 8.0
    enable_syntax_check: bool = True
    enable_type_check: bool = True
    enable_security_scan: bool = True
    enable_quality_check: bool = True
    enable_import_validation: bool = True
    mypy_enabled: bool = True
    pylint_enabled: bool = True
    bandit_enabled: bool = True


@dataclass
class CacheConfig:
    """Caching configuration."""
    enabled: bool = True
    paper_ttl_seconds: int = 86400  # 24 hours
    problem_ttl_seconds: int = 604800  # 7 days
    persona_ttl_seconds: int = 2592000  # 30 days
    template_ttl_seconds: int = 2592000  # 30 days
    db_path: str = "./data/cache.db"
    max_memory_mb: int = 100


@dataclass
class MetricsConfig:
    """Metrics collection configuration."""
    enabled: bool = True
    metrics_dir: str = "./data/metrics"
    aggregate_window_hours: int = 24
    track_llm_tokens: bool = True
    track_timing: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    log_dir: str = "./logs"
    structured_logging: bool = True
    per_paper_logs: bool = True
    console_output: bool = True


@dataclass
class ParallelConfig:
    """Parallel execution configuration."""
    max_concurrent_critiques: int = 5
    critique_timeout_seconds: int = 120
    continue_on_error: bool = True


@dataclass
class GitHubConfig:
    """GitHub API configuration."""
    token: Optional[str] = None
    default_org: Optional[str] = None
    rate_limit_pause: bool = True


@dataclass
class PipelineConfig:
    """Main pipeline configuration."""
    # LLM settings
    llm_provider: ConfigProvider = ConfigProvider.OLLAMA
    execution_mode: str = "local"  # local, cloud, parallel, fallback

    # Retry and circuit breaker
    retry: RetryConfig = field(default_factory=RetryConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)

    # Validation
    validation: ValidationConfig = field(default_factory=ValidationConfig)

    # Caching
    cache: CacheConfig = field(default_factory=CacheConfig)

    # Metrics
    metrics: MetricsConfig = field(default_factory=MetricsConfig)

    # Logging
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # Parallel execution
    parallel: ParallelConfig = field(default_factory=ParallelConfig)

    # GitHub
    github: GitHubConfig = field(default_factory=GitHubConfig)

    # Pipeline control
    max_papers_per_batch: int = 100
    checkpoint_interval_seconds: int = 300
    enable_auto_publish: bool = True


class ConfigManager:
    """
    Centralized configuration manager.

    Loads configuration from YAML file and environment variables.
    Provides type-safe access with validation.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        require_config_file: bool = False,
    ):
        """
        Initialize config manager.

        Args:
            config_path: Path to YAML config file
            require_config_file: Whether to fail if config file doesn't exist
        """
        self.config_path = config_path or os.getenv("AUTO_GIT_CONFIG", "./config.yaml")
        self.require_config_file = require_config_file
        self._config: Optional[PipelineConfig] = None

    def load_config(self) -> PipelineConfig:
        """
        Load configuration from file and environment variables.

        Returns:
            PipelineConfig instance

        Raises:
            ConfigurationError: If config is invalid
        """
        # Start with defaults
        config_dict = {}

        # Load from YAML file if exists
        config_file = Path(self.config_path)
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    config_dict = yaml.safe_load(f) or {}
                logger.info(f"Loaded configuration from {self.config_path}")
            except yaml.YAMLError as e:
                raise ConfigurationError(
                    f"Failed to parse config file: {e}",
                    config_key="config_file",
                )
        elif self.require_config_file:
            raise ConfigurationError(
                f"Config file not found: {self.config_path}",
                config_key="config_file",
            )

        # Override with environment variables
        config_dict = self._apply_env_overrides(config_dict)

        # Validate and create config object
        try:
            self._config = self._create_config_from_dict(config_dict)
            self._validate_config(self._config)
            logger.info("Configuration loaded and validated successfully")
            return self._config
        except Exception as e:
            raise ConfigurationError(
                f"Failed to create configuration: {e}",
                config_key="validation",
            )

    def _apply_env_overrides(self, config_dict: dict[str, Any]) -> dict[str, Any]:
        """Apply environment variable overrides."""
        # Map environment variables to config paths
        env_mappings = {
            "AUTO_GIT_LLM_PROVIDER": ("llm_provider",),
            "AUTO_GIT_EXECUTION_MODE": ("execution_mode",),
            "AUTO_GIT_MAX_RETRIES": ("retry", "max_attempts"),
            "AUTO_GIT_TIMEOUT": ("retry", "max_wait_seconds"),
            "AUTO_GIT_LOG_LEVEL": ("logging", "level"),
            "AUTO_GIT_LOG_DIR": ("logging", "log_dir"),
            "AUTO_GIT_CACHE_ENABLED": ("cache", "enabled"),
            "AUTO_GIT_METRICS_ENABLED": ("metrics", "enabled"),
            "AUTO_GIT_VALIDATION_ENABLED": ("validation", "enabled"),
            "AUTO_GIT_GITHUB_TOKEN": ("github", "token"),
            "AUTO_GIT_MAX_PARALLEL": ("parallel", "max_concurrent_critiques"),
        }

        for env_var, path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Set nested value
                current = config_dict
                for key in path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]

                # Type conversion
                final_key = path[-1]
                if value.lower() in ("true", "false"):
                    current[final_key] = value.lower() == "true"
                elif value.isdigit():
                    current[final_key] = int(value)
                else:
                    current[final_key] = value

                logger.debug(f"Override from env: {env_var}={value}")

        return config_dict

    def _create_config_from_dict(self, d: dict[str, Any]) -> PipelineConfig:
        """Create PipelineConfig from dictionary."""
        # Helper to get nested value or default
        def get_path(*path, default=None):
            current = d
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
            return current

        return PipelineConfig(
            # LLM
            llm_provider=ConfigProvider(
                get_path("llm_provider", default="ollama")
            ),
            execution_mode=get_path("execution_mode", default="local"),

            # Retry
            retry=RetryConfig(
                max_attempts=get_path("retry", "max_attempts", default=3),
                min_wait_seconds=get_path("retry", "min_wait_seconds", default=1.0),
                max_wait_seconds=get_path("retry", "max_wait_seconds", default=60.0),
            ),

            # Circuit breaker
            circuit_breaker=CircuitBreakerConfig(
                failure_threshold=get_path("circuit_breaker", "failure_threshold", default=5),
                cooldown_seconds=get_path("circuit_breaker", "cooldown_seconds", default=300),
            ),

            # Validation
            validation=ValidationConfig(
                enabled=get_path("validation", "enabled", default=True),
                min_score=get_path("validation", "min_score", default=8.0),
                enable_syntax_check=get_path("validation", "enable_syntax_check", default=True),
                enable_type_check=get_path("validation", "enable_type_check", default=True),
                enable_security_scan=get_path("validation", "enable_security_scan", default=True),
                enable_quality_check=get_path("validation", "enable_quality_check", default=True),
                enable_import_validation=get_path("validation", "enable_import_validation", default=True),
            ),

            # Cache
            cache=CacheConfig(
                enabled=get_path("cache", "enabled", default=True),
                paper_ttl_seconds=get_path("cache", "paper_ttl_seconds", default=86400),
                problem_ttl_seconds=get_path("cache", "problem_ttl_seconds", default=604800),
                persona_ttl_seconds=get_path("cache", "persona_ttl_seconds", default=2592000),
                template_ttl_seconds=get_path("cache", "template_ttl_seconds", default=2592000),
                db_path=get_path("cache", "db_path", default="./data/cache.db"),
            ),

            # Metrics
            metrics=MetricsConfig(
                enabled=get_path("metrics", "enabled", default=True),
                metrics_dir=get_path("metrics", "metrics_dir", default="./data/metrics"),
                aggregate_window_hours=get_path("metrics", "aggregate_window_hours", default=24),
            ),

            # Logging
            logging=LoggingConfig(
                level=get_path("logging", "level", default="INFO"),
                log_dir=get_path("logging", "log_dir", default="./logs"),
                structured_logging=get_path("logging", "structured_logging", default=True),
            ),

            # Parallel
            parallel=ParallelConfig(
                max_concurrent_critiques=get_path("parallel", "max_concurrent_critiques", default=5),
                critique_timeout_seconds=get_path("parallel", "critique_timeout_seconds", default=120),
                continue_on_error=get_path("parallel", "continue_on_error", default=True),
            ),

            # GitHub
            github=GitHubConfig(
                token=os.getenv("GITHUB_TOKEN") or get_path("github", "token"),
                default_org=get_path("github", "default_org"),
            ),

            # Pipeline
            max_papers_per_batch=get_path("max_papers_per_batch", default=100),
            checkpoint_interval_seconds=get_path("checkpoint_interval_seconds", default=300),
            enable_auto_publish=get_path("enable_auto_publish", default=True),
        )

    def _validate_config(self, config: PipelineConfig):
        """Validate configuration values."""
        # Validate LLM provider
        if not isinstance(config.llm_provider, ConfigProvider):
            raise ConfigurationError(
                f"Invalid LLM provider: {config.llm_provider}",
                config_key="llm_provider",
            )

        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if config.logging.level.upper() not in valid_levels:
            raise ConfigurationError(
                f"Invalid log level: {config.logging.level}",
                config_key="logging.level",
            )

        # Validate retry settings
        if config.retry.max_attempts < 1:
            raise ConfigurationError(
                f"Invalid max_attempts: {config.retry.max_attempts}",
                config_key="retry.max_attempts",
            )

        if config.retry.min_wait_seconds < 0:
            raise ConfigurationError(
                f"Invalid min_wait_seconds: {config.retry.min_wait_seconds}",
                config_key="retry.min_wait_seconds",
            )

        # Validate validation score
        if not 0 <= config.validation.min_score <= 10:
            raise ConfigurationError(
                f"Invalid validation min_score: {config.validation.min_score}",
                config_key="validation.min_score",
            )

        # Validate parallel settings
        if config.parallel.max_concurrent_critiques < 1:
            raise ConfigurationError(
                f"Invalid max_concurrent_critiques: {config.parallel.max_concurrent_critiques}",
                config_key="parallel.max_concurrent_critiques",
            )

        # Warn if GitHub token missing
        if config.github.token is None:
            logger.warning("GITHUB_TOKEN not configured - GitHub publishing may fail")

    def get_config(self) -> PipelineConfig:
        """
        Get loaded configuration.

        Returns:
            PipelineConfig instance

        Raises:
            ConfigurationError: If config not loaded
        """
        if self._config is None:
            self._config = self.load_config()
        return self._config

    def reload_config(self) -> PipelineConfig:
        """
        Reload configuration from file.

        Returns:
            Updated PipelineConfig instance
        """
        self._config = None
        return self.load_config()


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    """
    Get global config manager instance.

    Args:
        config_path: Optional path to config file

    Returns:
        ConfigManager instance
    """
    global _config_manager

    if _config_manager is None:
        _config_manager = ConfigManager(config_path=config_path)

    return _config_manager


@lru_cache(maxsize=1)
def get_config() -> PipelineConfig:
    """
    Get global configuration (cached).

    Returns:
        PipelineConfig instance
    """
    return get_config_manager().get_config()


def reload_config() -> PipelineConfig:
    """
    Reload global configuration.

    Returns:
        Updated PipelineConfig instance
    """
    global _config_manager
    if _config_manager:
        _config_manager.reload_config()
    get_config.cache_clear()
    return get_config()


def create_default_config(output_path: str = "./config.yaml"):
    """
    Create a default configuration file.

    Args:
        output_path: Path to write config file
    """
    default_config = """
# AUTO-GIT Configuration File
# Override with environment variables (see README)

# LLM Settings
llm_provider: ollama  # ollama, glm, claude, openai
execution_mode: local  # local, cloud, parallel, fallback

# Retry Configuration
retry:
  max_attempts: 3
  min_wait_seconds: 1.0
  max_wait_seconds: 60.0

# Circuit Breaker Configuration
circuit_breaker:
  failure_threshold: 5
  cooldown_seconds: 300

# Code Validation Configuration
validation:
  enabled: true
  min_score: 8.0
  enable_syntax_check: true
  enable_type_check: true
  enable_security_scan: true
  enable_quality_check: true
  enable_import_validation: true

# Caching Configuration
cache:
  enabled: true
  paper_ttl_seconds: 86400  # 24 hours
  problem_ttl_seconds: 604800  # 7 days
  persona_ttl_seconds: 2592000  # 30 days
  template_ttl_seconds: 2592000  # 30 days
  db_path: ./data/cache.db
  max_memory_mb: 100

# Metrics Configuration
metrics:
  enabled: true
  metrics_dir: ./data/metrics
  aggregate_window_hours: 24
  track_llm_tokens: true
  track_timing: true

# Logging Configuration
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  log_dir: ./logs
  structured_logging: true
  per_paper_logs: true
  console_output: true

# Parallel Execution Configuration
parallel:
  max_concurrent_critiques: 5
  critique_timeout_seconds: 120
  continue_on_error: true

# GitHub Configuration
github:
  token: null  # Set GITHUB_TOKEN environment variable
  default_org: null
  rate_limit_pause: true

# Pipeline Configuration
max_papers_per_batch: 100
checkpoint_interval_seconds: 300
enable_auto_publish: true
"""

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(default_config)

    logger.info(f"Created default configuration at {output_path}")


if __name__ == "__main__":
    # Create default config
    create_default_config()
