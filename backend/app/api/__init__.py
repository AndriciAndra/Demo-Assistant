from fastapi import APIRouter
from app.api.routes import jira, demo, review, settings, auth, files

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(jira.router)
api_router.include_router(demo.router)
api_router.include_router(review.router)
api_router.include_router(settings.router)
api_router.include_router(files.router)

__all__ = ["api_router"]