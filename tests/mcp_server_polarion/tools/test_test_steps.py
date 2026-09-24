"""Test-step tool tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_server_polarion.core.exceptions import (
    PolarionAuthError,
    PolarionError,
    PolarionNotFoundError,
)
from mcp_server_polarion.models import PaginatedResult, TestStep
from mcp_server_polarion.tools.test_steps import list_work_item_test_steps


def _step(index: str, *, extra: bool = False) -> dict[str, object]:
    keys = ["step", "description", "expectedResult"]
    values: list[object] = [
        {"type": "text/html", "value": f"<p>Step {index}</p>"},
        {"type": "text/plain", "value": f"Instruction {index}"},
        {"type": "text/html", "value": "<strong>Accepted</strong>"},
    ]
    if extra:
        keys.append("evidence")
        values.append({"type": "text/plain", "value": "Screenshot"})
    return {
        "type": "teststeps",
        "id": f"proj1/MCPT-001/{index}",
        "attributes": {"index": index, "keys": keys, "values": values},
    }


class TestListWorkItemTestSteps:
    async def test_returns_markdown_cells_and_pagination(
        self, mock_ctx: MagicMock, mock_client: AsyncMock
    ) -> None:
        mock_client.get.return_value = {
            "data": [_step("1", extra=True), _step("2")],
            "meta": {"totalCount": 3},
        }

        result = await list_work_item_test_steps(
            mock_ctx, project_id="proj1", work_item_id="MCPT-001", page_size=2
        )

        assert isinstance(result, PaginatedResult)
        assert isinstance(result.items[0], TestStep)
        assert result.items[0].id == "proj1/MCPT-001/1"
        assert result.items[0].index == "1"
        assert [(cell.key, cell.value) for cell in result.items[0].cells] == [
            ("step", "Step 1"),
            ("description", "Instruction 1"),
            ("expectedResult", "**Accepted**"),
            ("evidence", "Screenshot"),
        ]
        assert result.total_count == 3
        assert result.has_more is True

    async def test_request_uses_encoded_path_and_sparse_fields(
        self, mock_ctx: MagicMock, mock_client: AsyncMock
    ) -> None:
        mock_client.get.return_value = {"data": []}

        await list_work_item_test_steps(
            mock_ctx,
            project_id="proj / one",
            work_item_id="MCPT / 1",
            page_number=2,
        )

        args, kwargs = mock_client.get.call_args
        assert args[0] == (
            "/projects/proj%20%2F%20one/workitems/MCPT%20%2F%201/teststeps"
        )
        assert kwargs["params"] == {
            "fields[teststeps]": "index,keys,values",
            "page[size]": 20,
            "page[number]": 2,
        }

    async def test_missing_work_item_maps_to_value_error(
        self, mock_ctx: MagicMock, mock_client: AsyncMock
    ) -> None:
        mock_client.get.side_effect = PolarionNotFoundError("missing", status_code=404)

        with pytest.raises(ValueError, match="MCPT-999"):
            await list_work_item_test_steps(
                mock_ctx, project_id="proj1", work_item_id="MCPT-999"
            )

    async def test_auth_error_maps_to_permission_error(
        self, mock_ctx: MagicMock, mock_client: AsyncMock
    ) -> None:
        mock_client.get.side_effect = PolarionAuthError("denied", status_code=401)

        with pytest.raises(PermissionError):
            await list_work_item_test_steps(
                mock_ctx, project_id="proj1", work_item_id="MCPT-001"
            )

    async def test_backend_error_maps_to_runtime_error(
        self, mock_ctx: MagicMock, mock_client: AsyncMock
    ) -> None:
        mock_client.get.side_effect = PolarionError("boom", status_code=500)

        with pytest.raises(RuntimeError, match="boom"):
            await list_work_item_test_steps(
                mock_ctx, project_id="proj1", work_item_id="MCPT-001"
            )
