"""
Global block-definition and block-builder registries.

IMPORT FIREWALL: This module must NOT import from any ``runsight_core``
module.  Only stdlib ``typing`` (under TYPE_CHECKING) is allowed so that
the registry can be imported without triggering the rest of the package.
"""

from typing import TYPE_CHECKING, Callable, Dict, Optional, Type

if TYPE_CHECKING:
    from typing import Any

# block-type string  →  Pydantic *Def model class
BLOCK_DEF_REGISTRY: Dict[str, Type["Any"]] = {}

# block-type string  →  builder callable
BLOCK_BUILDER_REGISTRY: Dict[str, Callable] = {}


def register_block_def(block_type: str, def_cls: Type["Any"]) -> None:
    """Register a BlockDef subclass for *block_type*.

    Raises ``ValueError`` if *block_type* is already registered with a
    **different** class (re-registering the same class is idempotent).
    """
    existing = BLOCK_DEF_REGISTRY.get(block_type)
    if existing is not None and existing is not def_cls:
        raise ValueError(
            f"Duplicate block-def registration for '{block_type}': {existing!r} vs {def_cls!r}"
        )
    BLOCK_DEF_REGISTRY[block_type] = def_cls


def register_block_builder(block_type: str, builder: Callable) -> None:
    """Register a builder callable for *block_type*."""
    BLOCK_BUILDER_REGISTRY[block_type] = builder


def get_all_block_types() -> Dict[str, Type["Any"]]:
    """Return a shallow copy of the current block-def registry."""
    return dict(BLOCK_DEF_REGISTRY)


def get_builder(block_type: str) -> Optional[Callable]:
    """Return the builder for *block_type*, or ``None``."""
    return BLOCK_BUILDER_REGISTRY.get(block_type)
