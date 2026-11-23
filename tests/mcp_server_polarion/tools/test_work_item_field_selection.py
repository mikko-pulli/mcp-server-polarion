"""Opt-in sparse reads preserve legacy output and source fidelity."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from mcp_server_polarion.core.exceptions import PolarionAuthError
from mcp_server_polarion.server import mcp
from mcp_server_polarion.tools.work_items import get_work_item, read_work_item

_HTML = '<p data-test="keep">Read <strong>exactly</strong>.</p>'
_RICH = {"type": "text/html", "value": '<p class="source">Review</p>'}
_CUSTOM = {
    "riskLevel": "low",
    "reviewNote": _RICH,
    "enabledFlag": False,
    "effortHours": 0,
    "tagsList": ["one", "two"],
    "largeNote": "x" * 50_000,
}


def _response() -> dict[str, object]:
    return {
        "data": {
            "type": "workitems",
            "id": "Sample/TEST-1",
            "attributes": {
                "title": "Example requirement",
                "type": "requirement",
                "status": "draft",
                "created": "2026-01-01T00:00:00Z",
                "updated": "2026-01-02T00:00:00Z",
                "outlineNumber": "1.2",
                "description": {"type": "text/html", "value": _HTML},
                **_CUSTOM,
            },
            "relationships": {
                "module": {"data": {"type": "documents", "id": "Sample/Design/Spec"}},
                "author": {"data": {"type": "users", "id": "writer"}},
                "assignee": {"data": [{"type": "users", "id": "reviewer"}]},
            },
        },
        "included": [
            {"type": "users", "id": "writer", "attributes": {"name": "Writer"}},
            {"type": "users", "id": "reviewer", "attributes": {"name": "Reviewer"}},
        ],
    }


@pytest.mark.parametrize("read", [False, True])
@pytest.mark.parametrize(
    "selection",
    [None, [], ["riskLevel", "reviewNote", "enabledFlag", "effortHours", "tagsList"]],
)
async def test_selection_preserves_body_and_metadata(
    mock_ctx: MagicMock, mock_client: AsyncMock, read: bool, selection: list[str] | None
) -> None:
    # Return all attributes even for sparse requests: response filtering is required.
    mock_client.get.return_value = _response()
    if read:
        result = await read_work_item(
            mock_ctx, "Sample", "TEST-1", custom_field_ids=selection
        )
        assert "**exactly**" in result.description
    else:
        result = await get_work_item(
            mock_ctx,
            "Sample",
            "TEST-1",
            include_description_html=True,
            custom_field_ids=selection,
        )
        assert result.description_html == _HTML
    expected = (
        _CUSTOM if selection is None else {key: _CUSTOM[key] for key in selection}
    )
    assert result.custom_fields == expected
    assert (result.id, result.project_id, result.title, result.status) == (
        "TEST-1",
        "Sample",
        "Example requirement",
        "draft",
    )
    assert (result.space_id, result.document_name, result.outline_number) == (
        "Design",
        "Spec",
        "1.2",
    )
    assert (result.author_id, result.author_name) == ("writer", "Writer")
    assert (result.assignee_ids, result.assignee_names) == (["reviewer"], ["Reviewer"])
    assert result.created == "2026-01-01T00:00:00Z"
    assert result.updated == "2026-01-02T00:00:00Z"
    params = mock_client.get.call_args.kwargs["params"]
    fields = params["fields[workitems]"]
    if selection is None:
        assert fields == "@all"
    else:
        assert "@all" not in fields
        assert {"description", "module", "author", "assignee", *selection} <= set(
            fields.split(",")
        )
    mock_client.get.assert_awaited_once()


@pytest.mark.parametrize("read", [False, True])
async def test_omitted_selector_preserves_legacy_default(
    mock_ctx: MagicMock, mock_client: AsyncMock, read: bool
) -> None:
    mock_client.get.return_value = _response()
    if read:
        result = await read_work_item(mock_ctx, "Sample", "TEST-1")
    else:
        result = await get_work_item(
            mock_ctx, "Sample", "TEST-1", include_description_html=False
        )
        assert result.description_html == ""
    assert result.custom_fields == _CUSTOM
    assert mock_client.get.call_args.kwargs["params"]["fields[workitems]"] == "@all"


async def test_metadata_only_excludes_description_upstream(
    mock_ctx: MagicMock, mock_client: AsyncMock
) -> None:
    mock_client.get.return_value = _response()
    result = await get_work_item(
        mock_ctx,
        "Sample",
        "TEST-1",
        include_description_html=False,
        custom_field_ids=[],
    )
    assert result.description_html == ""
    assert result.custom_fields == {}
    fields = mock_client.get.call_args.kwargs["params"]["fields[workitems]"].split(",")
    assert "description" not in fields
    assert "@all" not in fields


async def test_duplicate_and_missing_ids_do_not_invent_values(
    mock_ctx: MagicMock, mock_client: AsyncMock
) -> None:
    mock_client.get.return_value = _response()
    result = await read_work_item(
        mock_ctx,
        "Sample",
        "TEST-1",
        custom_field_ids=["riskLevel", "riskLevel", "notAvailable"],
    )
    assert result.custom_fields == {"riskLevel": "low"}
    fields = mock_client.get.call_args.kwargs["params"]["fields[workitems]"].split(",")
    assert fields.count("riskLevel") == 1
    assert "notAvailable" in fields


@pytest.mark.parametrize(
    "field_id",
    [
        "",
        "@all",
        "@basic",
        "riskLevel,largeNote",
        " riskLevel",
        "../field",
        "field.name",
        "title",
        "module",
        "customFields",
    ],
)
@pytest.mark.parametrize("read", [False, True])
async def test_invalid_selection_rejected_before_request(
    mock_ctx: MagicMock, mock_client: AsyncMock, field_id: str, read: bool
) -> None:
    with pytest.raises(ValueError, match="custom_field_ids"):
        if read:
            await read_work_item(
                mock_ctx, "Sample", "TEST-1", custom_field_ids=[field_id]
            )
        else:
            await get_work_item(
                mock_ctx,
                "Sample",
                "TEST-1",
                include_description_html=True,
                custom_field_ids=[field_id],
            )
    mock_client.get.assert_not_awaited()


async def test_selection_preserves_access_errors(
    mock_ctx: MagicMock, mock_client: AsyncMock
) -> None:
    mock_client.get.side_effect = PolarionAuthError("Not permitted", status_code=403)
    with pytest.raises(PermissionError, match="Cannot access"):
        await read_work_item(mock_ctx, "Sample", "TEST-1", custom_field_ids=[])


@pytest.mark.parametrize("tool_name", ["get_work_item", "read_work_item"])
async def test_selector_reaches_mcp_schema_and_both_outputs(
    monkeypatch: pytest.MonkeyPatch, tool_name: str
) -> None:
    monkeypatch.setenv("POLARION_URL", "https://polarion.example.com")
    monkeypatch.setenv("POLARION_TOKEN", "test-token")
    monkeypatch.setenv("POLARION_MAX_REQUESTS_PER_SECOND", "0")
    with respx.mock(assert_all_called=True) as router:
        route = router.get(
            "https://polarion.example.com/polarion/rest/v1/projects/Sample/workitems/TEST-1"
        ).mock(return_value=httpx.Response(200, json=_response()))
        async with Client(mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            schema = tools[tool_name].inputSchema
            assert schema["properties"]["custom_field_ids"]["default"] is None
            assert "custom_field_ids" not in schema["required"]
            args = {"project_id": "Sample", "work_item_id": "TEST-1"}
            full = await client.call_tool(tool_name, args)
            compact = await client.call_tool(
                tool_name, {**args, "custom_field_ids": []}
            )
            assert full.structured_content["custom_fields"] == _CUSTOM
            assert compact.structured_content["custom_fields"] == {}
            serialized = json.dumps(
                {
                    "structured": compact.structured_content,
                    "content": [
                        part.model_dump(mode="json") for part in compact.content
                    ],
                }
            )
            assert "x" * 100 not in serialized
            assert len(serialized) < len(json.dumps(full.structured_content)) / 5
            assert "@all" not in route.calls[-1].request.url.params["fields[workitems]"]
            with pytest.raises(ToolError):
                await client.call_tool(
                    tool_name, {**args, "custom_field_ids": "riskLevel"}
                )
            with pytest.raises(ToolError):
                await client.call_tool(
                    tool_name, {**args, "custom_field_ids": ["@all"]}
                )
            assert route.call_count == 2
