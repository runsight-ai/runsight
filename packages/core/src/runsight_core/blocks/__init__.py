"""Workflow block components."""

import importlib
import logging
import pkgutil
from pathlib import Path

logger = logging.getLogger(__name__)
_PACKAGE_DIR = Path(__file__).parent


def _auto_discover_blocks() -> None:
    """Import all block modules to trigger registration.

    Each block module registers its own BlockDef and builder via explicit
    ``register_block_def()`` and ``register_block_builder()`` calls.
    """
    for module_info in pkgutil.iter_modules([str(_PACKAGE_DIR)]):
        name = module_info.name
        if name.startswith("_") or name in ("base",):
            continue
        try:
            importlib.import_module(f"{__name__}.{name}")
        except Exception:
            logger.warning(f"Failed to import block module: {name}", exc_info=True)


_auto_discover_blocks()
