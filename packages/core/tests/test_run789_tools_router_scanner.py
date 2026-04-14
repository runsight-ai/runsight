from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_list_tools_uses_tool_scanner(tmp_path, tools_router_module):
    with tools_router_module() as tools_router:
        tools_router.settings.base_path = str(tmp_path)

        with patch.object(tools_router, "ToolScanner") as mock_scanner:
            mock_scanner.return_value.scan.return_value.ids.return_value = {
                "lookup_profile": SimpleNamespace(
                    name="Lookup Profile",
                    description="Look up a profile.",
                    executor="python",
                )
            }

            items = await tools_router.list_tools()

    assert any(item.id == "lookup_profile" for item in items)
    mock_scanner.assert_called_once_with(str(tmp_path))
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.scan.return_value.ids.assert_called_once()
