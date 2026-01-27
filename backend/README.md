# Backend (FastAPI) for Robot Planner (MVP)

This tiny FastAPI app provides a local endpoint for generating demonstration plans.
It's intentionally minimal for local development and demo purposes.

## Architecture

```
Browser (port 8000)
    ↓
Node.js server.js (port 8000) [frontend + proxy]
    ↓ [proxy /api/generate_plan]
FastAPI backend (port 9000)
```

## Quickstart (Windows PowerShell)

1. Create and activate a virtual environment:

   python -m venv .venv; .\.venv\Scripts\Activate.ps1

2. Install dependencies:

   pip install -r requirements.txt

3. Run FastAPI backend on port 9000:

   uvicorn backend.app:app --host 127.0.0.1 --port 9000

4. In another terminal, run Node.js (port 8000):

   node server.js

5. Open http://localhost:8000 in browser

## Configuration

If you need to change the FastAPI port, set the environment variable:

   $env:FASTAPI_URL = "http://127.0.0.1:9000"; node server.js

Or edit the default in `server.js` line ~445:

   const FASTAPI_URL = process.env.FASTAPI_URL || "http://127.0.0.1:9000";

## Endpoint

POST /api/generate_plan

Request: { "instruction": "...", "site": "optional" }

Response: Generated plan JSON (saved to `data/demo_run.json` automatically)

CORS is enabled in app.py for development.
