"""PE API router modules."""

from fastapi import APIRouter

from .documents import router as documents_router
from .analytics import router as analytics_router
from .reconciliation import router as reconciliation_router
from .processing import router as processing_router

# Main PE router that combines all sub-routers
router = APIRouter(prefix="/pe", tags=["PE Documents"])

# Include all sub-routers
router.include_router(documents_router)
router.include_router(analytics_router)
router.include_router(reconciliation_router)
router.include_router(processing_router)