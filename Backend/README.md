# CarbonPilot Combined Backend

CarbonPilot is an AI-powered carbon-, cost-, latency-, quality-, and deadline-aware scheduler for agentic AI workflows.

This repository combines Whole-Workflow Optimization (DAG analysis, step fusion, redundant node pruning), Multi-Objective Deadline Slack Scheduling, Quality Gate & Smart Model Escalation, Execution Simulation, and a FastAPI integration server.

---

## Core Features

- **Whole-Workflow Optimizer**: Analyzes dependency graphs as a whole, fusing linear prompt steps and pruning redundant operations.
- **Quality Gate & Smart Escalation**: Starts with efficient models and escalates to higher-capacity models only when quality checks fail.
- **Carbon Budget Constraint**: Strictly rejects execution plans that exceed specified carbon limits.
- **Deadline Slack Scheduling**: Delays execution into cleaner carbon windows when sufficient deadline slack exists.
- **What-If Engine**: Re-evaluates candidate plans dynamically based on priority sliders.
- **Zero-Dependency Persistence**: Runs with local SQLite / in-memory storage fallback.

---

## Quickstart & Local Setup

### 1. Requirements

- Python 3.11+

### 2. Installation

```bash
cd Backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Running the FastAPI Server

```bash
uvicorn main:app --reload --port 8000
```

The server runs at `http://localhost:8000`. Interactive API documentation (Swagger UI) is available at `http://localhost:8000/docs`.

### 4. Running Demonstrations & Tests

```bash
# Run Whole-Workflow Optimizer CLI Demo
python3 examples/demo_optimizer.py

# Run Execution Scheduler CLI Demo
python3 examples/demo_scheduler.py

# Run Full Test Suite
python3 -m unittest discover -s tests -p "test_*.py"
```

---

## API Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check endpoint returning `{"status": "ok"}` |
| `POST` | `/api/workflows` | Save a new DAG workflow |
| `GET` | `/api/workflows/{workflow_id}` | Retrieve stored workflow by ID |
| `POST` | `/api/optimize` | Run Whole-Workflow Optimizer & What-If Engine |
| `POST` | `/api/execute/{plan_id}` | Execute simulated plan with Quality Gate escalations |
| `POST` | `/api/quality-check` | Quality gate evaluation endpoint |
| `GET` | `/api/dashboard/{workflow_id}` | Baseline vs CarbonPilot dashboard comparison |
