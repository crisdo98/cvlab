"""
FastAPI application entry point for CV Web Application.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from .routers import cv_router, export_router, llm_router, typography_router, job_suitability_router, application_tracker_router, backup_router

app = FastAPI(
    title="CV Web Application",
    description="A local web application for creating, editing, and exporting CVs",
    version="1.0.0"
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Vue dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cv_router.router)
app.include_router(export_router.router)
app.include_router(llm_router.router)
app.include_router(typography_router.router)
app.include_router(job_suitability_router.router)
app.include_router(application_tracker_router.router)
app.include_router(backup_router.router)

# Configure static file serving for export downloads
exports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "exports")
if os.path.exists(exports_dir):
    app.mount("/exports", StaticFiles(directory=exports_dir), name="exports")

# Health check endpoint with comprehensive validation
@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint that validates all critical components.
    """
    import subprocess
    import os
    from pathlib import Path
    
    health_status = {
        "status": "healthy",
        "service": "cv-web-app",
        "checks": {}
    }
    
    try:
        # Check data directories
        data_dir = Path("/app/data")
        health_status["checks"]["data_directory"] = {
            "status": "ok" if data_dir.exists() and data_dir.is_dir() else "error",
            "writable": os.access(data_dir, os.W_OK) if data_dir.exists() else False
        }
        
        # Check Pandoc availability
        try:
            result = subprocess.run(["pandoc", "--version"], capture_output=True, text=True, timeout=5)
            health_status["checks"]["pandoc"] = {
                "status": "ok" if result.returncode == 0 else "error",
                "version": result.stdout.split('\n')[0] if result.returncode == 0 else None
            }
        except Exception as e:
            health_status["checks"]["pandoc"] = {"status": "error", "error": str(e)}
        
        # Check LaTeX availability
        try:
            result = subprocess.run(["xelatex", "--version"], capture_output=True, text=True, timeout=5)
            health_status["checks"]["xelatex"] = {
                "status": "ok" if result.returncode == 0 else "error"
            }
        except Exception as e:
            health_status["checks"]["xelatex"] = {"status": "error", "error": str(e)}
        
        # Check required files
        required_files = [
            "/app/scripts/export.sh",
            "/app/templates/cv.latex",
            "/app/pandoc/defaults.yaml"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        health_status["checks"]["required_files"] = {
            "status": "ok" if not missing_files else "error",
            "missing_files": missing_files
        }
        
        # Overall status
        all_checks_ok = all(
            check.get("status") == "ok" 
            for check in health_status["checks"].values()
        )
        
        if not all_checks_ok:
            health_status["status"] = "unhealthy"
            
    except Exception as e:
        health_status["status"] = "error"
        health_status["error"] = str(e)
    
    return health_status

# API root endpoint
@app.get("/api")
async def api_root():
    return {"message": "CV Web Application API"}

# Serve frontend static files
static_dir = Path("/app/static")
if static_dir.exists():
    # Asset directory depends on which frontend built the bundle: Vite emits
    # assets/, Next.js emits _next/. Mount whichever is present rather than
    # assuming — StaticFiles raises at startup on a missing directory, which
    # would take the whole backend down.
    for asset_dir in ("assets", "_next"):
        asset_path = static_dir / asset_dir
        if asset_path.is_dir():
            app.mount(f"/{asset_dir}", StaticFiles(directory=str(asset_path)), name=asset_dir)
    
    # Serve favicon/logo
    @app.get("/cvlab.png")
    async def serve_logo():
        """Serve the CVLab logo/favicon"""
        logo_path = static_dir / "cvlab.png"
        if logo_path.exists():
            return FileResponse(str(logo_path))
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Logo not found")
    
    # index.html references content-hashed bundles, so it must never be
    # cached: a stale copy points at an asset filename that no longer exists
    # and the app silently keeps running the previous build
    index_headers = {"Cache-Control": "no-cache, no-store, must-revalidate"}

    # Serve index.html for root and all non-API routes (SPA routing)
    @app.get("/")
    async def serve_spa():
        """Serve the SPA index.html"""
        return FileResponse(str(static_dir / "index.html"), headers=index_headers)
    
    @app.get("/{full_path:path}")
    async def serve_spa_routes(full_path: str):
        """
        Catch-all route to serve index.html for SPA client-side routing.
        Excludes API routes which are handled by routers.
        """
        # Don't intercept API routes, health check, or static files. `_next`
        # matters as much as `assets`: without it every JavaScript chunk request
        # is answered with index.html and the app never boots.
        reserved = ("api", "exports", "assets", "_next")
        if full_path == "health" or full_path.startswith(reserved):
            # Let FastAPI return 404 for these
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")

        # A static export writes one HTML file per route (cv/index.html). Serve
        # that when it exists so the right page is delivered on first paint,
        # and fall back to the root document for client-side routes.
        candidate = static_dir / full_path.strip("/") / "index.html"
        if candidate.is_file():
            return FileResponse(str(candidate), headers=index_headers)

        return FileResponse(str(static_dir / "index.html"), headers=index_headers)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)