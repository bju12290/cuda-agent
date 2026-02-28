from __future__ import annotations

from typing import Any, Dict

from .loader import load_config as load_config_raw
from .interpolate import interpolate_config
from .validate import validate_config

def load_config_resolved(path: str) -> Dict[str, Any]:
    """
    Load config YAML and apply interpolation.

    v1 pipeline:
        1.) Load YAML into dict
        2.) interploate ${...} into string values
        3.) Validation next
    """
    raw = load_config_raw(path)
    resolved = interpolate_config(raw)
    validate_config(resolved)
    return resolved