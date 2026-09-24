"""Test-step read models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TestStepCell(BaseModel):
    """One configured Test Steps table cell rendered as Markdown."""

    __test__ = False

    key: str
    value: str


class TestStep(BaseModel):
    """One Test Steps table row from ``list_work_item_test_steps``."""

    __test__ = False

    id: str
    index: str
    cells: list[TestStepCell] = Field(default_factory=list)
