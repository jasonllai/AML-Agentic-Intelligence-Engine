"""Agent metadata schemas."""

from pydantic import BaseModel, Field


class AgentDescriptor(BaseModel):
    """Description of a routable AML agent."""

    name: str = Field(..., min_length=1)
    description: str
    supported_task_types: list[str]


class AgentExecutionResult(BaseModel):
    """Standard envelope for future agent outputs."""

    agent_name: str
    status: str
    output: dict[str, object]

