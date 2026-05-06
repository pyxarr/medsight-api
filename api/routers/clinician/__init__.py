from fastapi import APIRouter
from api.routers.clinician import assess, history

clinician_router = APIRouter()
clinician_router.include_router(assess.router)
clinician_router.include_router(history.router)
