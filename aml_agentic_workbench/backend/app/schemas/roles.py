"""Role schemas for AML workbench users."""

from enum import StrEnum

from pydantic import BaseModel, Field


class SupportedRole(StrEnum):
    """Supported role-aware experiences."""

    DATA_SCIENTIST = "data_scientist"
    INVESTIGATOR = "investigator"
    MODEL_VALIDATOR = "model_validator"
    COMPLIANCE_STRATEGY = "compliance_strategy"


class RoleCatalogResponse(BaseModel):
    """Supported role catalog response."""

    roles: list[SupportedRole] = Field(..., description="Roles supported by the workbench.")

