"""
CarbonPilot FastAPI Application Entry Point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import workflows, optimize, execute, quality, dashboard

app = FastAPI(
    title="CarbonPilot API",
    description="AI-powered carbon-, cost-, latency-, quality-, and deadline-aware scheduler for agentic AI workflows.",
    version="1.0.0"
)

# Enable CORS for Next.js frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(workflows.router)
app.include_router(optimize.router)
app.include_router(execute.router)
app.include_router(quality.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    import os
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
