"""Test-step parser tests."""

from __future__ import annotations

import pytest

from mcp_server_polarion.tools._shared.parse import parse_test_steps_page


def _response(keys: object = None, values: object = None) -> dict[str, object]:
    return {
        "data": [
            {
                "type": "teststeps",
                "id": "P/TC-1/1",
                "attributes": {
                    "index": "1",
                    "keys": ["step", "description"] if keys is None else keys,
                    "values": [
                        {"type": "text/html", "value": "<p>Open <b>app</b></p>"},
                        {"type": "text/plain", "value": "Use a test account"},
                    ]
                    if values is None
                    else values,
                },
            }
        ]
    }


class TestParseTestStepsPage:
    def test_renders_html_and_preserves_plain_text_and_order(self) -> None:
        result = parse_test_steps_page(_response(), page_number=1, page_size=20)

        assert result.items[0].id == "P/TC-1/1"
        assert result.items[0].index == "1"
        assert [(cell.key, cell.value) for cell in result.items[0].cells] == [
            ("step", "Open **app**"),
            ("description", "Use a test account"),
        ]

    def test_empty_collection_is_valid(self) -> None:
        result = parse_test_steps_page({"data": []}, page_number=1, page_size=20)
        assert result.items == []
        assert result.total_count == 0

    def test_non_list_data_fails_loudly(self) -> None:
        with pytest.raises(RuntimeError, match="data must be an array"):
            parse_test_steps_page({"data": {}}, page_number=1, page_size=20)

    def test_missing_arrays_fail_loudly(self) -> None:
        with pytest.raises(RuntimeError, match="keys and values arrays"):
            parse_test_steps_page(
                _response(keys="not-a-list"), page_number=1, page_size=20
            )

    def test_unequal_arrays_fail_loudly(self) -> None:
        with pytest.raises(RuntimeError, match="unequal keys and values"):
            parse_test_steps_page(
                _response(keys=["step"], values=[]), page_number=1, page_size=20
            )

    def test_malformed_cell_fails_loudly(self) -> None:
        with pytest.raises(RuntimeError, match="malformed value"):
            parse_test_steps_page(
                _response(values=["not-an-object", {"value": "ok"}]),
                page_number=1,
                page_size=20,
            )
