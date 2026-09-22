# CarbonPilot Backend API

CarbonPilot is an AI-powered carbon-, cost-, latency-, quality-, and deadline-aware scheduler for agentic AI workflows.

## Features

- **Whole-Workflow Optimizer**: Optimizes execution DAGs as a whole rather than making isolated per-model decisions.
- **Quality Gate & Smart Escalation**: Starts with efficient models and escalates to higher-capacity models only when quality checks fail.
- **Carbon Budget Constraint**: Strictly rejects execution plans that exceed specified carbon limits.
- **Deadline Slack Scheduling**: Delays execution into cleaner carbon windows when sufficient deadline slack exists.
- **What-If Engine**: Re-evaluates candidate plans dynamically based on frontend priority slider weights.
- **Zero-Dependency Persistence**: Automatically runs with local SQLite / in-memory storage fallback if external database configuration is omitted.

---

## Quickstart & Local Setup

### 1. Requirements

- Python 3.11+

### 2. Installation

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Setup

Copy example configuration:

```bash
cp .env.example .env
```

### 4. Running the Server

Start FastAPI server with auto-reload:

```bash
uvicorn main:app --reload --port 8000
```

The server will run at `http://localhost:8000`. Interactive API documentation (Swagger UI) is available at `http://localhost:8000/docs`.

---

## API Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check endpoint returning `{"status": "ok"}` |
| `POST` | `/api/workflows` | Save a new DAG workflow |
| `GET` | `/api/workflows/{workflow_id}` | Retrieve stored workflow by ID |
| `POST` | `/api/optimize` | Run Whole-Workflow Optimizer (Supports What-If sliders & constraints) |
| `POST` | `/api/execute/{plan_id}` | Execute simulated plan with quality gates & model escalations |
| `POST` | `/api/quality-check` | Direct quality gate evaluation |
| `GET` | `/api/dashboard/{workflow_id}` | Retrieve baseline vs CarbonPilot comparison metrics & history |
