"""Typed schemas for safe internal MCP-style tool execution."""

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.roles import SupportedRole


class ToolInput(BaseModel):
    """Base class for all tool input schemas."""


class ToolResult(BaseModel):
    """Base class for all tool result payload schemas."""


class ToolContext(BaseModel):
    """Execution context supplied by the registry, not by the tool caller."""

    actor: str = Field(..., min_length=1)
    role: SupportedRole
    request_id: str | None = None


class ToolOutput(BaseModel):
    """Standard registry response envelope for every tool invocation."""

    tool_name: str
    status: str
    data: dict[str, Any] | None = None
    error: str | None = None
    audit_metadata: dict[str, Any] = Field(default_factory=dict)
    elapsed_ms: float


class ToolDescriptor(BaseModel):
    """Safe tool metadata exposed for discovery."""

    name: str
    description: str
    allowed_roles: list[SupportedRole]
    input_schema_name: str
    output_schema_name: str

