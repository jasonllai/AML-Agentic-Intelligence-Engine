"""Base interfaces for registered internal tools."""

from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.schemas.roles import SupportedRole
from app.tools.schemas import ToolContext


class BaseTool(ABC):
    """Safe, typed interface for internal MCP-style tools.

    Tools are intentionally constrained: they expose schemas, role scope, and a
    single execute method. They do not receive shell access or arbitrary runtime
    execution privileges.
    """

    name: str
    description: str
    allowed_roles: frozenset[SupportedRole]
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    default_timeout_seconds: float = 5.0

    @abstractmethod
    def execute(self, tool_input: BaseModel, context: ToolContext) -> BaseModel:
        """Execute the tool with validated input and registry-owned context."""

    def audit_metadata(self, tool_input: BaseModel, context: ToolContext) -> dict[str, object]:
        """Return non-sensitive metadata to attach to audit events."""
        return {
            "tool_name": self.name,
            "role": context.role.value,
            "request_id": context.request_id,
            "input_fields": sorted(tool_input.model_fields_set),
        }

