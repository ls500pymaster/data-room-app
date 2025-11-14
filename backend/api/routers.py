from fastapi import APIRouter
from backend.api.auth import router as auth_router
from backend.api.files import router as files_router


router = APIRouter()
router.include_router(auth_router)
router.include_router(files_router)