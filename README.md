# Adaptive AI Tutor

A personalised tutor that teaches only from study material you provide. It
assesses what a learner already knows, tracks mastery per concept, and chooses
what to do next: teach, reteach a misconception, practise, or move on.

- **Backend** – FastAPI, PostgreSQL + pgvector (retrieval), Ollama (LLM and embeddings)
- **Frontend** – React + Vite

## Prerequisites

- Python 3.11+ and Node 20+
- Docker (for PostgreSQL with pgvector)
- [Ollama](https://ollama.com) with two models:

```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

## Run it

```bash
# 1. Database
docker compose up -d

# 2. Backend (http://localhost:8000, API docs at /docs)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python create_tables.py
python seed_demo.py            # demo "Computer Networks" course + study material
uvicorn app.main:app --port 8000

# 3. Frontend (http://localhost:5173) – in a second terminal
cd frontend
npm install
npm run dev
```

`seed_demo.py` needs Ollama to embed the sample material. Use
`python seed_demo.py --skip-knowledge` to create only the course.

The status pill in the header shows whether the backend, database and AI model
are reachable.

## How the pieces connect

The frontend calls the backend under `/api`. In development the Vite dev
server proxies `/api` to `http://127.0.0.1:8000` and strips the prefix, so the
browser only talks to one origin and no CORS setup is needed.

On first visit the frontend asks for a name and calls `POST /students/bootstrap`,
which creates the profile if the name is new (ignoring case) and returns the
existing one otherwise. The browser remembers the name, and "Switch profile" in
the header returns to the name screen. There is no password: profiles are
identified by name only. All endpoint calls live in `frontend/src/api.js`.

Typical flow: choose or generate a course → upload study material → optional
diagnostic → the planner picks the next concept and the adaptive engine decides
whether to teach, reteach, practise or move on → quiz → mastery updates → repeat.

Study material uploaded for a subject (PDF, TXT or Markdown) grounds lessons,
quizzes and the diagnostic for every concept in it.

## Configuration

| Where | Variable | Default |
|---|---|---|
| backend `.env` | `DATABASE_URL` | local Postgres on port 5434 |
| backend `.env` | `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` |
| backend `.env` | `OLLAMA_BASE_URL`, `LLM_MODEL`, `EMBEDDING_MODEL` | local Ollama, `llama3.2:3b`, `nomic-embed-text` |
| `frontend/.env.local` | `VITE_API_BASE_URL` | `/api` |
| `frontend/.env.local` | `VITE_PROXY_TARGET` | `http://127.0.0.1:8000` |

See `.env.example` and `frontend/.env.example`.

For a production build, serve `frontend/dist` and either put a reverse proxy
in front that maps `/api` to the backend, or set `VITE_API_BASE_URL` to the
backend URL and add the frontend's origin to `CORS_ORIGINS`.

## Tests

```bash
# Backend – use a separate database, the tests create and remove rows
createdb adaptive_tutor_test        # or create it in the docker container
cd backend
DATABASE_URL=postgresql+psycopg://tutor:tutor_password@localhost:5434/adaptive_tutor_test \
  python create_tables.py
DATABASE_URL=postgresql+psycopg://tutor:tutor_password@localhost:5434/adaptive_tutor_test \
  pytest

# Frontend
cd frontend
npm test
```

Neither suite needs Ollama.
