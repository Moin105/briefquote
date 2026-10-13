from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ScopeExtraction(BaseModel):
    """Structured scope extracted from a client brief."""

    summary: str = Field(description="One-sentence summary of what the client wants built.")
    project_type: Literal[
        "web", "mobile", "data", "ai_automation", "design", "writing", "devops", "other"
    ] = Field(description="Best-fitting category for the project.")
    deliverables: list[str] = Field(
        description="Concrete things the freelancer must hand over, as short phrases."
    )
    tech_stack: list[str] = Field(
        description="Technologies, platforms or services explicitly mentioned in the brief."
    )
    complexity: int = Field(
        description="Overall complexity from 1 (trivial) to 5 (very complex)."
    )
    integrations_count: int = Field(
        description="Number of third-party systems/APIs to integrate with (0 or more)."
    )
    has_design_provided: bool = Field(
        description="True only if the client already has designs/mockups ready."
    )
    has_clear_requirements: bool = Field(
        description="True only if requirements and acceptance criteria are specific."
    )
    unknowns: list[str] = Field(
        description="Open questions to ask the client before quoting."
    )
    risk_flags: list[str] = Field(
        description=(
            "Scope creep signals, vague acceptance criteria, unrealistic timeline, "
            "or other risks."
        )
    )
    client_timeline_days: int | None = Field(
        default=None,
        description="Timeline in days if the client states one, otherwise null.",
    )
    budget_mentioned_usd: float | None = Field(
        default=None,
        description="Budget in USD if the client states one, otherwise null.",
    )

    @field_validator("complexity")
    @classmethod
    def _complexity_range(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("complexity must be between 1 and 5")
        return v

    @field_validator("integrations_count")
    @classmethod
    def _integrations_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("integrations_count must be >= 0")
        return v

    @classmethod
    def json_schema_for_llm(cls) -> dict:
        return cls.model_json_schema()
