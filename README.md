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

## Accounts and roles

Everyone signs in with a username and password (`POST /auth/register`,
`POST /auth/login`). The backend returns a signed token that the frontend sends
as `Authorization: Bearer ...` on every request. Passwords are stored only as
salted hashes. Tokens expire after `ACCESS_TOKEN_MINUTES` (default 12 hours).

| Role | Can do |
|---|---|
| `student` | Learn: diagnostic, lessons, quizzes, own progress, list courses. Only their own data. |
| `instructor` | Everything a student can, plus create courses, upload study material, and view any learner's progress. |
| `admin` | Everything an instructor can, plus manage users (change roles, deactivate, reset passwords). |

Public sign-up always creates a `student`. Roles are checked on the server for
every request (and read from the database, so changes apply immediately); the
frontend only hides controls you cannot use.

**Create the first admin** (run from `backend`, once):

```bash
python create_admin.py <username> <password>
```

or set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env` and it is created at
start-up. Sign in as that admin, open "Manage users" and promote others.
Set `SECRET_KEY` in `.env` to a long random value (for example
`python -c "import secrets; print(secrets.token_urlsafe(48))"`); without it a
new key is generated on every start and everyone is signed out on restart.

Databases created before accounts existed are upgraded automatically at
start-up (new `password_hash`, `role`, `is_active` columns). Old accounts have
no password until an admin sets one.

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
| backend `.env` | `SECRET_KEY`, `ACCESS_TOKEN_MINUTES`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` | random key, 720, none |
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
