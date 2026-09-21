"""
CarbonPilot Backend Main Application Entrypoint

FastAPI server providing REST APIs for Workflow Management, Optimization, Execution Simulation,
Quality Gate Evaluation, and Dashboard Comparison.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import dashboard, execute, optimize, quality, workflows
from backend.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite DB schema on startup
    init_db()
    yield


app = FastAPI(
    title="CarbonPilot API",
    description="AI-powered carbon-, cost-, latency-, quality-, and deadline-aware scheduler for agentic AI workflows.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(workflows.router)
app.include_router(optimize.router)
app.include_router(execute.router)
app.include_router(quality.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["Health"])
def health_check():
    """Service health check endpoint."""
    return {"status": "ok"}
