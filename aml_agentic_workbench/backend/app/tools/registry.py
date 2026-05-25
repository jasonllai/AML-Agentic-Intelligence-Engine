"""Safe registry and executor for internal MCP-style tools."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from time import perf_counter

from app.guardrails.tool_guardrails import ToolGuardrails
from app.schemas.roles import SupportedRole
from app.services.audit_logger import AuditEvent, AuditLogger
from app.tools.base import BaseTool
from app.tools.schemas import ToolContext, ToolDescriptor, ToolOutput


class ToolRegistryError(Exception):
    """Base exception for tool registry failures."""


class ToolAlreadyRegisteredError(ToolRegistryError):
    """Raised when a duplicate tool name is registered."""


class ToolNotFoundError(ToolRegistryError):
    """Raised when a requested tool is not registered."""


class ToolPermissionError(ToolRegistryError):
    """Raised when a role is not allowed to execute a tool."""


class ToolExecutionError(ToolRegistryError):
    """Raised when a tool fails during execution."""


class ToolRegistry:
    """Allowlisted registry that validates, authorizes, executes, and audits tools."""

    def __init__(self, audit_logger: AuditLogger | None = None, tool_guardrails: ToolGuardrails | None = None) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._audit_logger = audit_logger or AuditLogger()
        self._tool_guardrails = tool_guardrails or ToolGuardrails()

    def register(self, tool: BaseTool) -> None:
        """Register a tool by unique name."""
        if tool.name in self._tools:
            raise ToolAlreadyRegisteredError(f"Tool '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """Return a registered tool by name."""
        return self._tools.get(name)

    def list_tools(self, role: SupportedRole | None = None) -> list[ToolDescriptor]:
        """Return safe descriptors for tools visible to an optional role."""
        tools = self._tools.values()
        if role is not None:
            tools = [tool for tool in tools if role in tool.allowed_roles]
        return [
            ToolDescriptor(
                name=tool.name,
                description=tool.description,
                allowed_roles=sorted(tool.allowed_roles, key=lambda item: item.value),
                input_schema_name=tool.input_schema.__name__,
                output_schema_name=tool.output_schema.__name__,
            )
            for tool in tools
        ]

    def invoke(
        self,
        tool_name: str,
        role: SupportedRole,
        arguments: dict[str, object],
        *,
        actor: str = "system",
        request_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> ToolOutput:
        """Invoke a registered tool with typed validation, authorization, and audit logging."""
        started = perf_counter()
        context = ToolContext(actor=actor, role=role, request_id=request_id)
        tool = self._tools.get(tool_name)

        if tool is None:
            self._audit("tool_not_found", actor, tool_name, {"role": role.value, "request_id": request_id})
            raise ToolNotFoundError(f"Tool '{tool_name}' is not registered.")

        policy_decision = self._tool_guardrails.evaluate_tool_call(
            tool_name=tool.name,
            role=role,
            allowed_roles=set(tool.allowed_roles),
            read_only=tool.name != "save_report",
        )
        if not policy_decision.allowed:
            metadata = {
                "role": role.value,
                "flags": policy_decision.flags,
                "allowed_roles": [allowed.value for allowed in tool.allowed_roles],
            }
            self._audit("tool_policy_denied", actor, tool.name, metadata)
            raise ToolPermissionError(f"Tool policy denied '{tool.name}': {', '.join(policy_decision.flags)}.")

        if role not in tool.allowed_roles:
            metadata = {"role": role.value, "allowed_roles": [allowed.value for allowed in tool.allowed_roles]}
            self._audit("tool_denied", actor, tool.name, metadata)
            raise ToolPermissionError(f"Role '{role.value}' is not allowed to execute tool '{tool.name}'.")

        validated_input = tool.input_schema.model_validate(arguments)
        audit_metadata = tool.audit_metadata(validated_input, context)
        self._audit("tool_started", actor, tool.name, audit_metadata)

        executor = ThreadPoolExecutor(max_workers=1)
        executor_closed = False
        try:
            future = executor.submit(tool.execute, validated_input, context)
            raw_output = future.result(timeout=timeout_seconds or tool.default_timeout_seconds)
            validated_output = tool.output_schema.model_validate(raw_output)
        except FutureTimeoutError:
            executor.shutdown(wait=False, cancel_futures=True)
            executor_closed = True
            elapsed_ms = self._elapsed_ms(started)
            metadata = {**audit_metadata, "elapsed_ms": elapsed_ms}
            self._audit("tool_timeout", actor, tool.name, metadata)
            return ToolOutput(
                tool_name=tool.name,
                status="timeout",
                error=f"Tool '{tool.name}' exceeded timeout.",
                audit_metadata=metadata,
                elapsed_ms=elapsed_ms,
            )
        except Exception as exc:
            executor.shutdown(wait=False, cancel_futures=True)
            executor_closed = True
            elapsed_ms = self._elapsed_ms(started)
            metadata = {**audit_metadata, "elapsed_ms": elapsed_ms, "error_type": exc.__class__.__name__}
            self._audit("tool_failed", actor, tool.name, metadata)
            return ToolOutput(
                tool_name=tool.name,
                status="error",
                error=str(exc),
                audit_metadata=metadata,
                elapsed_ms=elapsed_ms,
            )
        finally:
            if not executor_closed:
                executor.shutdown(wait=True)

        elapsed_ms = self._elapsed_ms(started)
        metadata = {**audit_metadata, "elapsed_ms": elapsed_ms}
        self._audit("tool_succeeded", actor, tool.name, metadata)
        return ToolOutput(
            tool_name=tool.name,
            status="success",
            data=validated_output.model_dump(mode="json"),
            audit_metadata=metadata,
            elapsed_ms=elapsed_ms,
        )

    def _audit(self, action: str, actor: str, target: str, metadata: dict[str, object]) -> None:
        self._audit_logger.log(AuditEvent(actor=actor, action=action, target=target, metadata=metadata))

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((perf_counter() - started) * 1000, 3)
