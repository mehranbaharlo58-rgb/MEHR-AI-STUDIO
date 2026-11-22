"""Validated data contracts for MEHR AI STUDIO workflows."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ContentBriefContract(StrictContract):
    goal: str = Field(min_length=1, max_length=4000)
    audience: str = Field(min_length=1, max_length=1000)
    channel: str = Field(min_length=1, max_length=200)
    language: str = Field(default="Persian", min_length=1, max_length=100)
    tone: str = Field(default="clear and professional", min_length=1, max_length=500)
    key_points: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("key_points")
    @classmethod
    def validate_key_points(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("key_points cannot contain empty strings")
        return values


class GeneratedAssetContract(StrictContract):
    content: str = Field(min_length=1)
    format: str = Field(default="text", min_length=1, max_length=100)
    model: str = Field(default="unknown", min_length=1, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QualityReportContract(StrictContract):
    score: int = Field(ge=0, le=100)
    checks: dict[str, bool | int | float | str]
    limitations: list[str] = Field(default_factory=list)


class ProviderResultContract(StrictContract):
    text: str = Field(min_length=1)
    model: str = Field(min_length=1, max_length=200)


class WorkflowRunContract(StrictContract):
    run_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=128)
    status: Literal["queued", "running", "waiting_approval", "failed", "succeeded", "cancelled"]
    current_stage: str | None = Field(default=None, max_length=100)
    attempt: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime
    prompt_version: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=200)
    error_code: str | None = Field(default=None, max_length=100)
