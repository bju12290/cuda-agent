from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import re


class ParseError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedMetric:
    name: str
    value: Any
    units: str | None = None


def parse_target_output(cfg: Mapping[str, Any], target_id: str, text: str) -> dict[str, ParsedMetric]:
    """
    Parse stdout text for a target using targets.<id>.parse (regex rules).

    v1:
      - kind must be "regex"
      - each rule's pattern should contain a capturing group for the value
      - supports type: float, int, enum, str
    """
    targets = cfg.get("targets", {})
    if not isinstance(targets, dict) or target_id not in targets:
        raise ParseError(f"Unknown target for parsing: {target_id!r}")

    tcfg = targets[target_id]
    if not isinstance(tcfg, dict):
        raise ParseError(f"Invalid target config for {target_id!r}")

    parse_cfg = tcfg.get("parse")
    if parse_cfg is None:
        return {}  # no parsing configured

    if not isinstance(parse_cfg, dict):
        raise ParseError(f"Invalid parse config for target {target_id!r} (must be a mapping)")

    if parse_cfg.get("kind") != "regex":
        raise ParseError(f"Unsupported parse kind for target {target_id!r}: {parse_cfg.get('kind')!r}")

    rules = parse_cfg.get("rules")
    if not isinstance(rules, list):
        raise ParseError(f"Invalid parse.rules for target {target_id!r} (must be a list)")

    out: dict[str, ParsedMetric] = {}

    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ParseError(f"Invalid rule at parse.rules[{i}] (must be a mapping)")

        name = rule.get("name")
        pattern = rule.get("pattern")
        rtype = rule.get("type", "str")
        required = bool(rule.get("required", False))
        units = rule.get("units")

        if not isinstance(name, str) or not name.strip():
            raise ParseError(f"Invalid rule name at parse.rules[{i}]")
        if not isinstance(pattern, str) or not pattern.strip():
            raise ParseError(f"Invalid rule pattern for '{name}' (parse.rules[{i}])")

        rx = re.compile(pattern, flags=re.MULTILINE)
        m = rx.search(text)

        if not m:
            if required:
                raise ParseError(f"Missing required metric '{name}' (pattern did not match)")
            continue

        # Prefer first capture group; fallback to whole match
        raw = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)
        raw = raw.strip()

        # Type conversion
        if rtype == "float":
            try:
                val: Any = float(raw)
            except ValueError as e:
                raise ParseError(f"Metric '{name}' expected float, got {raw!r}") from e

        elif rtype == "int":
            try:
                val = int(raw)
            except ValueError as e:
                raise ParseError(f"Metric '{name}' expected int, got {raw!r}") from e

        elif rtype == "enum":
            enum_vals = rule.get("enum")
            if not isinstance(enum_vals, list) or not all(isinstance(x, str) for x in enum_vals):
                raise ParseError(f"Metric '{name}' has invalid enum list")
            if raw not in enum_vals:
                raise ParseError(f"Metric '{name}' got {raw!r}, expected one of {enum_vals}")
            val = raw

        else:  # "str"
            val = raw

        out[name] = ParsedMetric(name=name, value=val, units=units if isinstance(units, str) else None)

    return out
