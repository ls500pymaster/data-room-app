from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from backend.api.routers import router
from backend.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
)

# --- CORS ---
# CORS middleware must be added before routes to handle OPTIONS preflight
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)


@app.get("/api/health", tags=["system"])
async def health_check():
    """Healthcheck endpoint for monitoring."""
    return {"status": "ok"}


# --- Routers ---
app.include_router(router, prefix="/api")

# --- Static files (frontend) ---
# Try to mount frontend build directory if it exists
# Path: /app/frontend/build (in Docker) or ../frontend/build (local)
frontend_build_path = Path("/app/frontend/build")
if not frontend_build_path.exists():
    # Try relative path for local development
    frontend_build_path = Path(__file__).parent.parent.parent / "frontend" / "build"

if frontend_build_path.exists():
    # Mount static files (JS, CSS, images, etc.) - must be before catch-all route
    static_dir = frontend_build_path / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Serve index.html for all non-API routes (React Router)
    # This must be the LAST route to not interfere with API routes
    # IMPORTANT: Only handle GET - OPTIONS requests are handled by CORS middleware first
    @app.get("/{full_path:path}", name="frontend")
    async def serve_frontend(full_path: str):
        """
        Serve React app. This should be the last route.
        For API routes, they are handled above with /api prefix.
        Only handles GET requests - OPTIONS are handled by CORS middleware.
        """
        # Don't serve index.html for API routes, static files, or docs
        if full_path.startswith("api") or full_path.startswith("static") or full_path.startswith("docs"):
            return {"detail": "Not Found"}
        
        index_path = frontend_build_path / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"detail": "Frontend not found"}

# --- Entry point for local run ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)