"""Test-step read model tests."""

from __future__ import annotations

from mcp_server_polarion.models import TestStep, TestStepCell


class TestTestStepCell:
    def test_keeps_configured_key_and_markdown_value(self) -> None:
        cell = TestStepCell(key="expectedResult", value="**accepted**")
        assert cell.key == "expectedResult"
        assert cell.value == "**accepted**"


class TestTestStep:
    def test_keeps_opaque_resource_id_and_ordered_cells(self) -> None:
        step = TestStep(
            id="P/MCPT-1/2",
            index="2",
            cells=[
                TestStepCell(key="step", value="Do the thing"),
                TestStepCell(key="expectedResult", value="It works"),
            ],
        )
        assert step.id == "P/MCPT-1/2"
        assert [cell.key for cell in step.cells] == ["step", "expectedResult"]
