from fastapi import APIRouter
from api.routers.member import assess

member_router = APIRouter()
member_router.include_router(assess.router)
