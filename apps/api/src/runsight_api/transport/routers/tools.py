from __future__ import annotations

from typing import List

from fastapi import APIRouter

from runsight_core.yaml.discovery import discover_custom_tools

from ...core.config import settings
from ..schemas.tools import ToolListItemResponse

router = APIRouter(prefix="/tools", tags=["Tools"])

_USER_FACING_BUILTIN_TOOLS = (
    ToolListItemResponse(
        slug="runsight/http",
        name="HTTP Requests",
        description="Fetch external APIs.",
        type="builtin",
    ),
    ToolListItemResponse(
        slug="runsight/file-io",
        name="Workspace Files",
        description="Read project files.",
        type="builtin",
    ),
)


def _format_tool_name(slug: str) -> str:
    parts = [segment for segment in slug.replace("-", " ").replace("_", " ").split() if segment]
    return " ".join(part.capitalize() for part in parts) or slug


@router.get("", response_model=List[ToolListItemResponse])
async def list_tools() -> List[ToolListItemResponse]:
    items: List[ToolListItemResponse] = list(_USER_FACING_BUILTIN_TOOLS)

    for slug, tool_meta in sorted(discover_custom_tools(settings.base_path).items()):
        items.append(
            ToolListItemResponse(
                slug=slug,
                name=_format_tool_name(slug),
                description=f"Discovered {tool_meta.type} tool from custom/tools.",
                type=tool_meta.type,
            )
        )

    return items
