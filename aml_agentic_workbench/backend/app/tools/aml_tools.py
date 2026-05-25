"""Registered AML prototype tools backed by local services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.schemas.roles import SupportedRole
from app.services.data_service import DataService, get_data_service
from app.services.knowledge_retriever import KnowledgeRetriever, get_knowledge_retriever
from app.tools.base import BaseTool
from app.tools.schemas import ToolContext

if TYPE_CHECKING:
    from app.tools.registry import ToolRegistry

ALL_ROLES = frozenset(SupportedRole)
ANALYTIC_ROLES = frozenset(
    {
        SupportedRole.DATA_SCIENTIST,
        SupportedRole.INVESTIGATOR,
        SupportedRole.MODEL_VALIDATOR,
    }
)
REPORTING_ROLES = frozenset({SupportedRole.INVESTIGATOR, SupportedRole.COMPLIANCE_STRATEGY})


class CustomerIdInput(BaseModel):
    """Input schema for customer-scoped tools."""

    customer_id: str = Field(..., min_length=1)


class CustomerTransactionsInput(CustomerIdInput):
    """Input for transaction retrieval."""

    limit: int = Field(default=100, ge=1, le=500)


class CustomerTransactionsOutput(BaseModel):
    """Transactions returned for a customer."""

    customer_id: str
    transactions: list[dict[str, object]]
    count: int


class FeatureSummaryOutput(BaseModel):
    """Feature summary returned for a customer."""

    customer_id: str
    feature_summary: dict[str, object]
    top_features: list[str]


class ModelOutputsOutput(BaseModel):
    """Model outputs returned for a customer."""

    customer_id: str
    model_outputs: dict[str, object]


class KnowledgeSearchInput(BaseModel):
    """Input for local AML knowledge retrieval."""

    query: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(default=3, ge=1, le=10)


class KnowledgeSearchOutput(BaseModel):
    """Retrieved knowledge documents."""

    query: str
    documents: list[dict[str, object]]


class NetworkSummaryOutput(BaseModel):
    """Counterparty network summary returned for a customer."""

    customer_id: str
    summary: dict[str, object]


class SaveReportInput(BaseModel):
    """Input for saving a governed report artifact."""

    run_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)


class SaveReportOutput(BaseModel):
    """Saved report metadata."""

    report_id: str
    run_id: str
    status: str
    title: str


class DataServiceTool(BaseTool):
    """Base class for tools that use the local data service."""

    def __init__(self, data_service: DataService | None = None) -> None:
        self.data_service = data_service or get_data_service()


class GetCustomerTransactionsTool(DataServiceTool):
    """Return synthetic customer transactions."""

    name = "get_customer_transactions"
    description = "Retrieve synthetic transactions for a customer."
    allowed_roles = ANALYTIC_ROLES
    input_schema = CustomerTransactionsInput
    output_schema = CustomerTransactionsOutput

    def execute(self, tool_input: BaseModel, context: ToolContext) -> BaseModel:
        request = CustomerTransactionsInput.model_validate(tool_input)
        transactions = self.data_service.get_transactions(request.customer_id, limit=request.limit)
        return CustomerTransactionsOutput(
            customer_id=request.customer_id,
            transactions=transactions,
            count=len(transactions),
        )


class GetCustomerFeatureSummaryTool(DataServiceTool):
    """Return synthetic customer feature summary."""

    name = "get_customer_feature_summary"
    description = "Retrieve engineered AML feature summary for a customer."
    allowed_roles = ANALYTIC_ROLES
    input_schema = CustomerIdInput
    output_schema = FeatureSummaryOutput

    def execute(self, tool_input: BaseModel, context: ToolContext) -> BaseModel:
        request = CustomerIdInput.model_validate(tool_input)
        summary = self.data_service.get_feature_summary(request.customer_id)
        return FeatureSummaryOutput(
            customer_id=request.customer_id,
            feature_summary=summary,
            top_features=list(summary.get("top_features", [])),
        )


class GetModelOutputsTool(DataServiceTool):
    """Return synthetic model outputs."""

    name = "get_model_outputs"
    description = "Retrieve AML model output scores and leading features."
    allowed_roles = frozenset({SupportedRole.DATA_SCIENTIST, SupportedRole.MODEL_VALIDATOR})
    input_schema = CustomerIdInput
    output_schema = ModelOutputsOutput

    def execute(self, tool_input: BaseModel, context: ToolContext) -> BaseModel:
        request = CustomerIdInput.model_validate(tool_input)
        return ModelOutputsOutput(
            customer_id=request.customer_id,
            model_outputs=self.data_service.get_model_outputs(request.customer_id),
        )


class SearchAmlKnowledgeBaseTool(BaseTool):
    """Search local AML knowledge documents."""

    name = "search_aml_knowledge_base"
    description = "Search curated AML typology and governance knowledge."
    allowed_roles = ALL_ROLES
    input_schema = KnowledgeSearchInput
    output_schema = KnowledgeSearchOutput

    def __init__(self, retriever: KnowledgeRetriever | None = None) -> None:
        self.retriever = retriever or get_knowledge_retriever()

    def execute(self, tool_input: BaseModel, context: ToolContext) -> BaseModel:
        request = KnowledgeSearchInput.model_validate(tool_input)
        documents = self.retriever.search(request.query, limit=request.limit)
        return KnowledgeSearchOutput(
            query=request.query,
            documents=[document.model_dump(mode="json") for document in documents],
        )


class GetCounterpartyNetworkSummaryTool(DataServiceTool):
    """Return synthetic counterparty network summary."""

    name = "get_counterparty_network_summary"
    description = "Summarize customer counterparty concentration and cross-border exposure."
    allowed_roles = ANALYTIC_ROLES
    input_schema = CustomerIdInput
    output_schema = NetworkSummaryOutput

    def execute(self, tool_input: BaseModel, context: ToolContext) -> BaseModel:
        request = CustomerIdInput.model_validate(tool_input)
        return NetworkSummaryOutput(
            customer_id=request.customer_id,
            summary=self.data_service.get_network_summary(request.customer_id),
        )


class SaveReportTool(BaseTool):
    """Mock save-report tool for governed report generation."""

    name = "save_report"
    description = "Persist a governed AML intelligence report artifact."
    allowed_roles = REPORTING_ROLES
    input_schema = SaveReportInput
    output_schema = SaveReportOutput

    def __init__(self) -> None:
        self._saved_reports: dict[str, SaveReportInput] = {}

    def execute(self, tool_input: BaseModel, context: ToolContext) -> BaseModel:
        request = SaveReportInput.model_validate(tool_input)
        report_id = f"report-{len(self._saved_reports) + 1:04d}"
        self._saved_reports[report_id] = request
        return SaveReportOutput(report_id=report_id, run_id=request.run_id, status="saved", title=request.title)


def build_default_tool_registry() -> ToolRegistry:
    """Build the default allowlisted internal tool registry."""
    from app.tools.registry import ToolRegistry

    registry = ToolRegistry()
    registry.register(GetCustomerTransactionsTool())
    registry.register(GetCustomerFeatureSummaryTool())
    registry.register(GetModelOutputsTool())
    registry.register(SearchAmlKnowledgeBaseTool())
    registry.register(GetCounterpartyNetworkSummaryTool())
    registry.register(SaveReportTool())
    return registry
