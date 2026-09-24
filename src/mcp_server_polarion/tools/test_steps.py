"""Test-step read tool for test-case work items.

API contract quirks: docs/polarion-api/work-items.md
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context
from pydantic import Field

from mcp_server_polarion.core.exceptions import (
    PolarionAuthError,
    PolarionError,
    PolarionNotFoundError,
)
from mcp_server_polarion.models import PaginatedResult, TestStep
from mcp_server_polarion.server import mcp
from mcp_server_polarion.tools._shared.helpers import encode_path_segment, get_client
from mcp_server_polarion.tools._shared.parse import parse_test_steps_page

_DEFAULT_PAGE_SIZE = 20


@mcp.tool(
    tags={"read"},
    timeout=60.0,
    annotations={"readOnlyHint": True},
)
async def list_work_item_test_steps(
    ctx: Context,
    project_id: str = Field(description="Polarion project ID."),
    work_item_id: str = Field(description="Work item ID (e.g. 'MCPT-001')."),
    page_size: Annotated[int, Field(ge=1, le=100)] = _DEFAULT_PAGE_SIZE,
    page_number: Annotated[int, Field(ge=1)] = 1,
) -> PaginatedResult[TestStep]:
    """List a work item's Test Steps table as Markdown cells.

    Preserves configured column keys and row order. For work-item metadata or
    body, use get_work_item or read_work_item instead.
    """
    client = get_client(ctx)
    path = (
        f"/projects/{encode_path_segment(project_id)}"
        f"/workitems/{encode_path_segment(work_item_id)}/teststeps"
    )
    try:
        response = await client.get(
            path,
            params={
                "fields[teststeps]": "index,keys,values",
                "page[size]": page_size,
                "page[number]": page_number,
            },
        )
    except PolarionNotFoundError as exc:
        raise ValueError(
            f"Work item '{work_item_id}' not found in project '{project_id}'. "
            "Use `list_work_items` to discover valid IDs."
        ) from exc
    except PolarionAuthError as exc:
        raise PermissionError(
            "Cannot access work item Test Steps -- check your POLARION_TOKEN "
            "permissions."
        ) from exc
    except PolarionError as exc:
        raise RuntimeError(
            f"Failed to list Test Steps for work item '{work_item_id}': {exc.message}"
        ) from exc

    return parse_test_steps_page(response, page_number, page_size)
