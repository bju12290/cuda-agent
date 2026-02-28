from __future__ import annotations
from typing import Any, Mapping
import re

from .errors import InterpolationError

def resolve_ref(cfg: Mapping[str, Any], ref: str) -> Any:
    """
    Resolve a dotted reference path like 'build.build_dir' within a config mapping.

    v1 rules:
      - references traverse dicts only
      - each path segment must exist
      - errors are explicit and human-friendly
    """

    ref = ref.strip()
    if not ref or ref.startswith(".") or ref.endswith("."):
        raise InterpolationError(f"Invalid interpolation reference: '{ref}'")
    
    cur: Any = cfg
    parts = ref.split(".")

    for i, key in enumerate(parts):
        if not isinstance(cur, dict):
            prefix = ".".join(parts[:i]) or "<root>"
            raise InterpolationError(
                f"Cannot resolve '{ref}': '{prefix}' is not a mapping (got {type(cur).__name__})"
            )
        if key not in cur:
            prefix = ".".join(parts[:i]) or "<root>"
            raise InterpolationError(
                f"Cannot resolve '{ref}': missing key '{key}' under '{prefix}'"
            )
        
        cur = cur[key]

    return cur

_PLACEHOLDER_RE = re.compile(r"(?<!\\)\$\{([^{}]+)\}")

def interpolate_str(cfg: Mapping[str, Any], s: str) ->str:
    """
    Replace ${path.to.value} placeholders inside a string.

    v1 rules:
    - ${...} resolves using dotted paths via resolve_ref()
    - backslash + ${...} is treated as a literal (escape)
    - referenced values must be scalar (str/int/float/bool); lists/dicts are errors
    - missing references raise InterpolationError
    - no recursion/multi-pass in v1
    """

    if "${" not in s:
        # Nothing to do
        return s
    
    def _replace(match: re.Match[str]) -> str:
        ref = match.group(1).strip()
        val = resolve_ref(cfg, ref)

        if val is None:
            raise InterpolationError(f"Interpolation reference '{ref}' resolved to null/None")
        
        if isinstance(val, (str, int, float, bool)):
            return str(val)
        
        raise InterpolationError(
            f"Interpolation reference '{ref}' must be a scalar (str/int/float/bool), got {type(val).__name__}"
            )
    
    # Replace unescaped placeholders
    out = _PLACEHOLDER_RE.sub(_replace, s)

    # Unescape literals: \${...} -> ${...}
    out = out.replace(r"\${", "${")

    return out


def interpolate_config(cfg: Mapping[str, Any]) -> dict[str, Any]:
    """
    Walk the entire config tree and interpolate placeholders in all string values.

    Notes (v1):
    - Only values are interpolated (not dict keys).
    - Interpolation resolves against the original root `cfg`.
    - Single pass: if a referenced value itself contains ${...}, we don't
      recursively resolve it inside other fields (multi-pass later?).
    """

    def _walk(node: Any) -> Any:
        if isinstance(node, str):
            return interpolate_str(cfg, node)
        
        if isinstance(node, dict):
            return {k: _walk(v) for k, v in node.items()}
        
        if isinstance(node, list):
            return [_walk(item) for item in node]
        
        # ints, floats bools, None, etc.
        return node
    
    out = _walk(cfg)

    # cfg root is expected to be a mapping, but enforce return type anyway
    if not isinstance(out, dict):
        raise InterpolationError(
            f"Config root must be a mapping after interpolation, got {type(out).__name__}"
        )
    
    return out