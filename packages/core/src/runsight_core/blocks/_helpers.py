"""
Shared helper functions used by block builders.

Extracted from ``runsight_core.yaml.parser`` so that block modules can
reuse them without importing the full parser.
"""

from typing import Dict

from runsight_core.conditions.engine import Condition, ConditionGroup
from runsight_core.primitives import Soul
from runsight_core.yaml.schema import ConditionDef, ConditionGroupDef


def resolve_soul(ref: str, souls_map: Dict[str, Soul]) -> Soul:
    """Look up *ref* in *souls_map*.

    Raises:
        ValueError: If *ref* is not found in *souls_map*.
    """
    soul = souls_map.get(ref)
    if soul is None:
        raise ValueError(
            f"Soul reference '{ref}' not found. Available souls: {sorted(souls_map.keys())}"
        )
    return soul


def convert_condition(cond_def: ConditionDef) -> Condition:
    """Convert a ``ConditionDef`` schema model to a runtime ``Condition``."""
    return Condition(
        eval_key=cond_def.eval_key,
        operator=cond_def.operator,
        value=cond_def.value,
    )


def convert_condition_group(group_def: ConditionGroupDef) -> ConditionGroup:
    """Convert a ``ConditionGroupDef`` schema model to a runtime ``ConditionGroup``."""
    return ConditionGroup(
        conditions=[convert_condition(c) for c in group_def.conditions],
        combinator=group_def.combinator,
    )
