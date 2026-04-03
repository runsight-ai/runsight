from __future__ import annotations

from typing import List

from fastapi import APIRouter

from runsight_core.yaml.discovery import discover_custom_tools

from ...core.config import settings
from ...domain.errors import InputValidationError
from ..schemas.tools import ToolListItemResponse

router = APIRouter(prefix="/tools", tags=["Tools"])

_USER_FACING_BUILTIN_TOOLS = (
    ToolListItemResponse(
        id="http",
        name="HTTP Requests",
        description="Fetch external APIs.",
        origin="builtin",
        executor="native",
    ),
    ToolListItemResponse(
        id="file_io",
        name="Workspace Files",
        description="Read project files.",
        origin="builtin",
        executor="native",
    ),
)


@router.get("", response_model=List[ToolListItemResponse])
async def list_tools() -> List[ToolListItemResponse]:
    items: List[ToolListItemResponse] = list(_USER_FACING_BUILTIN_TOOLS)

    try:
        discovered_tools = discover_custom_tools(settings.base_path)
    except ValueError as exc:
        raise InputValidationError(str(exc)) from exc

    for tool_id, tool_meta in sorted(discovered_tools.items()):
        items.append(
            ToolListItemResponse(
                id=tool_id,
                name=tool_meta.name,
                description=tool_meta.description,
                origin="custom",
                executor=tool_meta.executor,
            )
        )

    return items
