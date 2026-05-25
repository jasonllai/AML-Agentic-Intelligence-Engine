"""Tool registry and permission tests."""


import pytest

from app.schemas.roles import SupportedRole
from app.services.audit_logger import AuditEvent
from app.tools.aml_tools import GetCustomerTransactionsTool, SaveReportTool, SearchAmlKnowledgeBaseTool
from app.tools.registry import ToolAlreadyRegisteredError, ToolPermissionError, ToolRegistry


class InMemoryAuditLogger:
    """Audit logger test double."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def log(self, event: AuditEvent) -> None:
        """Capture audit events in memory."""
        self.events.append(event)


def test_tool_registration_lists_descriptors_for_role() -> None:
    """Registered tools should be discoverable through safe descriptors."""
    audit_logger = InMemoryAuditLogger()
    registry = ToolRegistry(audit_logger=audit_logger)  # type: ignore[arg-type]
    registry.register(GetCustomerTransactionsTool())

    descriptors = registry.list_tools(role=SupportedRole.INVESTIGATOR)

    assert len(descriptors) == 1
    assert descriptors[0].name == "get_customer_transactions"
    assert SupportedRole.INVESTIGATOR in descriptors[0].allowed_roles


def test_duplicate_tool_registration_is_rejected() -> None:
    """Duplicate tool names should fail closed."""
    registry = ToolRegistry()
    registry.register(GetCustomerTransactionsTool())

    with pytest.raises(ToolAlreadyRegisteredError):
        registry.register(GetCustomerTransactionsTool())


def test_tool_invocation_audits_success() -> None:
    """Successful invocations should produce start and success audit events."""
    audit_logger = InMemoryAuditLogger()
    registry = ToolRegistry(audit_logger=audit_logger)  # type: ignore[arg-type]
    registry.register(GetCustomerTransactionsTool())

    output = registry.invoke(
        "get_customer_transactions",
        SupportedRole.INVESTIGATOR,
        {"customer_id": "CUST003", "limit": 2},
        actor="analyst-1",
        request_id="req-1",
    )

    assert output.status == "success"
    assert output.data is not None
    assert output.data["count"] == 2
    assert [event.action for event in audit_logger.events] == ["tool_started", "tool_succeeded"]


def test_unauthorized_role_cannot_call_restricted_tool() -> None:
    """Restricted tools should deny roles outside their allowlist."""
    audit_logger = InMemoryAuditLogger()
    registry = ToolRegistry(audit_logger=audit_logger)  # type: ignore[arg-type]
    registry.register(SaveReportTool())

    with pytest.raises(ToolPermissionError):
        registry.invoke(
            "save_report",
            SupportedRole.DATA_SCIENTIST,
            {"run_id": "run-1", "title": "Draft", "content": "Restricted save."},
            actor="ds-1",
        )

    assert audit_logger.events[-1].action == "tool_policy_denied"


def test_knowledge_search_tool_is_role_scoped_to_all_roles() -> None:
    """Knowledge search should be available to every supported role."""
    registry = ToolRegistry()
    registry.register(SearchAmlKnowledgeBaseTool())

    output = registry.invoke(
        "search_aml_knowledge_base",
        SupportedRole.COMPLIANCE_STRATEGY,
        {"query": "cross-border concentration wires", "limit": 2},
    )

    assert output.status == "success"
    assert output.data is not None
    documents = output.data["documents"]
    assert isinstance(documents, list)
    assert any("Cross-border" in str(document["title"]) for document in documents)
