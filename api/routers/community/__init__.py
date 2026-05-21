from fastapi import APIRouter
from api.routers.community import posts, reactions, follows

community_router = APIRouter()
community_router.include_router(posts.router)
community_router.include_router(reactions.router)
community_router.include_router(follows.router)
