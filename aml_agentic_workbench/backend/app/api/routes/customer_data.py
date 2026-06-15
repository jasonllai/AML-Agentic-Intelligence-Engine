"""Customer data browser routes."""

from fastapi import APIRouter, Depends, Query

from app.services.data_service import DataService, get_data_service

router = APIRouter(prefix="/customer-data", tags=["customer-data"])
DataServiceDependency = Depends(get_data_service)


@router.get("/sources")
def list_customer_data_sources(data_service: DataService = DataServiceDependency) -> dict[str, object]:
    """List available raw customer-data sources."""
    return {"sources": data_service.list_customer_data_sources()}


@router.get("/customer/{customer_id}")
def get_customer_data_profile(
    customer_id: str,
    source: str = Query(default="all"),
    limit: int = Query(default=100, ge=1, le=500),
    data_service: DataService = DataServiceDependency,
) -> dict[str, object]:
    """Return customer-scoped data across available sources."""
    return data_service.get_customer_data_profile(customer_id, source=source, limit=limit)
