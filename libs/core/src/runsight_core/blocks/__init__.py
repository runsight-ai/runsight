"""Workflow block components."""

import importlib
import logging
import pkgutil
from pathlib import Path

logger = logging.getLogger(__name__)
_PACKAGE_DIR = Path(__file__).parent


def _auto_discover_blocks() -> None:
    """Import all block modules to trigger __init_subclass__ registration."""
    for module_info in pkgutil.iter_modules([str(_PACKAGE_DIR)]):
        name = module_info.name
        if name.startswith("_") or name in ("base", "implementations", "registry"):
            continue
        try:
            mod = importlib.import_module(f"{__name__}.{name}")
            # If module has a build() function, register it
            if hasattr(mod, "build"):
                from runsight_core.blocks._registry import register_block_builder

                register_block_builder(name, mod.build)
        except Exception:
            logger.warning(f"Failed to import block module: {name}", exc_info=True)


_auto_discover_blocks()
