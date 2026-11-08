from fastapi import APIRouter

from .library import router as library_router
from .routes import router as emoji_router

router = APIRouter()
router.include_router(library_router)
router.include_router(emoji_router)

__all__ = ["router"]
