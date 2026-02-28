# Custom exceptions so failures are clean and readable.

class ConfigError(Exception):
    """Base error for configuration problems."""

class ConfigLoadError(ConfigError):
    """Rasied when agent.yaml cannot be read or parsed."""

class InterpolationError(ConfigError):
    """Raised when ${...} references are invalid or cannot be resolved."""

class ValidationError(ConfigError):
    """Raised when config is missing required fiels or has invalid values."""