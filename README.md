# AI Employee OS

**Status:** Functional multi-tenant AI platform (development build)

AI Employee OS is a multi-tenant SaaS platform that acts as an all-in-one operating system for businesses, augmented with specialized AI agents. The backend AI engine, frontend dashboards, external integrations, and background workers are implemented and tested.

## Current Architecture State

- **Frontend:** Next.js — real dashboards (CRM, Sales, Finance, HR, …) connected to the backend API via React Query; auth via Supabase.
- **Backend:** FastAPI — AI engine with **14 AI agents / 59 tools**, Gemini + OpenRouter model routing (with image/screenshot understanding), RAG knowledge base, **13 external integrations**, and Celery workers.
- **Database:** PostgreSQL (Supabase) — 71 tables with Row Level Security (RLS) enforcing multi-tenancy.

## Running Locally

See the maintained snapshot in **SYSTEM_SETUP.md** for the full current setup (LLM config, agents, tools, integrations, workers, workflows) and `INTEGRATION_SETUP.md` for provider console URLs.

### Database Setup
```bash
cd supabase
supabase start
supabase db push
```

## Documentation

- **[SYSTEM_SETUP.md](SYSTEM_SETUP.md)** — *maintained*: current agents, tools, integrations, workers, workflows, and configuration.
- **[DASHBOARD_MATRIX.md](DASHBOARD_MATRIX.md)** — *maintained*: which AI agent works with which dashboard, and which human role can access which dashboards.
- **INTEGRATION_SETUP.md** — callback/webhook URLs for every provider console.
- `ARCHITECTURE.md`, `API_SPEC.md`, `PRD.md`, `DESIGN.md`, `MEMORY.md`.
- `CURRENT_STATE.md` / `BACKEND_GAP_ANALYSIS.md` — historical scaffold-era snapshots, superseded by `SYSTEM_SETUP.md`.
