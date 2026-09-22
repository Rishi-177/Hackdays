"""
CarbonPilot FastAPI Application Entry Point.
"""

import os
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.api import workflows, optimize, execute, quality, dashboard, queue
from backend.db.async_database import init_async_db

app = FastAPI(
    title="CarbonPilot API",
    description="AI-powered carbon-, cost-, latency-, quality-, and deadline-aware scheduler for agentic AI workflows with offline sync support.",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    """Initialize database schemas on server startup."""
    await init_async_db()

# Mount static files (dashboard frontend)
_static_dir = os.path.join(os.path.dirname(__file__), "backend", "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Include API Routers
app.include_router(queue.router)
app.include_router(workflows.router)
app.include_router(optimize.router)
app.include_router(execute.router)
app.include_router(quality.router)
app.include_router(dashboard.router)


@app.get("/", include_in_schema=False)
def serve_dashboard():
    """Serve the CarbonPilot dashboard frontend."""
    index_path = os.path.join(_static_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"message": "CarbonPilot API is running. Visit /docs for API documentation."}


@app.get("/sw.js", include_in_schema=False)
def serve_service_worker():
    """Serve the root-scoped service worker for offline background sync."""
    sw_path = os.path.join(_static_dir, "sw.js")
    if os.path.isfile(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    return {"error": "sw.js not found"}


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)

