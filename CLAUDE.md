# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TherapyCompanion.AI — a full-stack AI-powered virtual therapist assistant. Backend is FastAPI (Python 3.11+), frontend is React 18 + TypeScript + Vite. The AI personalizes to each therapist's style through a 5-step onboarding flow and requires therapist approval for all patient communications.

## Common Commands

### Backend
```bash
make install          # pip install -r requirements.txt
make run              # python -m app.main (serves on :8000)
make test             # pytest -v
make test-cov         # pytest --cov=app tests/
pytest tests/test_agent.py  # run a single test file
make migrate          # alembic upgrade head
make lint             # flake8 app/ tests/ && mypy app/
make format           # black app/ tests/ && isort app/ tests/
```

### Frontend (from `frontend/` directory)
```bash
npm run dev           # Vite dev server (:3000)
npm run build         # tsc && vite build
npm run lint          # eslint . --ext ts,tsx
```

### Docker
```bash
make docker-up        # docker-compose up -d (app + PostgreSQL + Redis)
make docker-down
```

## Architecture

### Backend (`app/`)
- **`main.py`** — FastAPI application entrypoint
- **`api/routes/`** — REST endpoints: auth, agent (chat/commands/onboarding), messages (create/approve/reject/send)
- **`core/`** — App config and the core AI agent logic (Anthropic Claude / OpenAI, LangChain)
- **`models/`** — SQLAlchemy ORM models (PostgreSQL)
- **`services/`** — Business logic layer (session summaries, message drafting, onboarding)
- **`security/`** — JWT auth (python-jose), BCrypt passwords, AES-256 encryption for patient data

### Frontend (`frontend/src/`)
- **`pages/`** — Route-level page components
- **`components/`** — Reusable React components (RTL/Hebrew-first)
- **`lib/`** — Axios API client configured for the backend
- **`store/`** — Zustand state management

### Key Data Flow
1. Therapist records/types session notes → backend transcribes (Whisper) and generates summary via AI agent
2. AI drafts patient messages in therapist's learned style → stored as "pending"
3. Therapist reviews/edits/approves → only then is the message sent
4. All patient data encrypted at rest (AES-256), full audit trail logged

### Infrastructure
- **Database:** PostgreSQL 14+ with Alembic migrations (`alembic/`)
- **Cache:** Redis 6+
- **Config:** `.env` file (see `.env.example`), loaded via pydantic-settings

## Code Style
- Backend: black (line-length=100), isort (black profile), target Python 3.11
- Frontend: ESLint with TypeScript + React hooks rules, Tailwind CSS, strict `--max-warnings 0`
- Tests: pytest with `asyncio_mode = "auto"`, test files in `tests/`
- Primary UI language is Hebrew with RTL layout
