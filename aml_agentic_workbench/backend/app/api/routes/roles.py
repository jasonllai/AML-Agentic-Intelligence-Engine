"""Role discovery endpoints."""

from fastapi import APIRouter

from app.schemas.roles import RoleCatalogResponse, SupportedRole

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=RoleCatalogResponse)
async def list_roles() -> RoleCatalogResponse:
    """Return supported workbench user roles."""
    return RoleCatalogResponse(roles=list(SupportedRole))

