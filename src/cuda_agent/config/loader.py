from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Union

import yaml

from .errors import ConfigLoadError

PathLike = Union[str, Path]

def load_config(path: PathLike) -> Dict[str, Any]:
    """
    Load a YAML config file and return it as a Python dict.

    Raises:
        ConfigLoadError:
            - if the file cannot be read or parsed
            - or if the YAML root is not a mapping (dict).
    """

    p = Path(path)

    if not p.exists():
        raise ConfigLoadError(f"Config file not found: {p}")
    
    if not p.is_file():
        raise ConfigLoadError(f"Config path is not a file: {p}")
    
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as e:
        raise ConfigLoadError(f"Failed to read config file: {p}") from e
    
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        if mark is not None:
            loc = f"line {mark.line + 1}, col {mark.column + 1}"
            raise ConfigLoadError(f"Failed to parse YAML in {p} ({loc}): {e}") from e
        raise ConfigLoadError(f"Failed to parse YAML in {p}: {e}") from e
    
    if data is None:
        raise ConfigLoadError(f"Config file is empty: {p}")
    
    if not isinstance(data, dict):
        raise ConfigLoadError(
            f"Config root must be a mapping (YAML object/dict), got: {type(data).__name__}"
        )
    
    return data
