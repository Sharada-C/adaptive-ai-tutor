# Adaptive AI Tutor

A personalised tutor that teaches from study material: your own uploads and
cited Wikipedia articles, never from the model's memory alone. It
assesses what a learner already knows, tracks mastery per concept, and chooses
what to do next: teach, reteach a misconception, practise, or move on.

- **Backend** – FastAPI, PostgreSQL + pgvector (retrieval), Ollama (LLM and embeddings)
- **Frontend** – React + Vite

## Prerequisites

- Python 3.11+ and Node 20+
- Docker (for PostgreSQL with pgvector)
- [Ollama](https://ollama.com) with two models:

```bash
ollama pull llama3.2:3b        # tutor model (default)
ollama pull nomic-embed-text   # embeddings
ollama pull qwen2.5:7b         # recommended for grading, see "Grading quality"
```

## Run it

```bash
# 1. Database
docker compose up -d

# 2. Backend (http://localhost:8000, API docs at /docs)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env        # then set SECRET_KEY, or logins reset on every restart
python -m alembic -c ../alembic.ini upgrade head   # builds the schema
python seed_demo.py            # demo "Computer Networks" course + study material
uvicorn app.main:app --port 8000

# 3. Frontend (http://localhost:5173) – in a second terminal
cd frontend
npm install
npm run dev
```

`seed_demo.py` needs Ollama to embed the sample material. Use
`python seed_demo.py --skip-knowledge` to create only the course.

### Everything in containers

```bash
cp .env.example .env     # set SECRET_KEY
docker compose up --build
```

This starts Postgres, the API (it applies migrations on start) and the
frontend at http://localhost:8080. Ollama still runs on your machine; the API
reaches it through `host.docker.internal`.

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
| `student` | Learn: diagnostic, lessons, quizzes, own progress. Can study any topic by creating a **private course** (see below). Only their own data. |
| `instructor` | Everything a student can, plus create **shared** courses (visible to everyone), upload material to them, and view any learner's progress. |
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

Mastery per concept is the recency-weighted average of the last five answers,
pulled toward zero by a small prior (`PRIOR_WEIGHT` in `mastery_service.py`):
one correct answer gives 0.67, two give 0.86, so a concept needs repeated
success to reach the 0.80 advance threshold.

Study material uploaded for a subject (PDF, TXT or Markdown) grounds lessons,
quizzes and the diagnostic for every concept in it.

## Learning any topic

A student types any topic (`POST /subjects/from-topic`). The backend asks the
LLM for a concept path with prerequisites, saves it as a course that only that
student can see, and attaches study material automatically from the Wikipedia
API (top articles for the topic and each concept, disambiguation and stub pages
skipped). The student can add their own notes or PDFs to their course. Material
keeps its article title and URL as the chunk source, so the tutor's evidence
stays traceable; Wikipedia text is CC BY-SA 4.0. If Wikipedia or the embedding
model is unreachable the course is still created and the student is asked to
upload material. A student can keep up to `MAX_COURSES_PER_USER` courses;
asking for the same topic twice returns the existing course. Private courses
return 404 to everyone else, including instructors.

Each concept also gets its own Wikipedia article (cited per concept), so a
lesson or quiz on a concept is grounded in text about that concept rather than
only in the topic's overview. Evidence text that does not mention the concept is
not shown as a lesson.

## My learning

The **My learning** page (header button, also offered at the end of a path)
lists every course the learner created or started, with mastery and concepts
mastered, and lets them continue one or start a new topic. "What I've learned"
opens a journal per concept: status (mastered / in progress / not started),
takeaways from questions they answered well, misconceptions still open and
their recent answers (`GET /students/{id}/library`,
`GET /students/{id}/subjects/{subject_id}/journal`).

## Configuration

| Where | Variable | Default |
|---|---|---|
| backend `.env` | `DATABASE_URL` | local Postgres on port 5434 |
| backend `.env` | `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` |
| backend `.env` | `SECRET_KEY`, `ACCESS_TOKEN_MINUTES`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` | random key, 720, none |
| backend `.env` | `OLLAMA_BASE_URL`, `LLM_MODEL`, `EMBEDDING_MODEL` | local Ollama, `llama3.2:3b`, `nomic-embed-text` |
| backend `.env` | `GRADER_MODEL` | empty (grade with `LLM_MODEL`); a 7-8B model grades far more reliably |
| backend `.env` | `COVERAGE_CHECK` | `true`: an answer with no contradictions is also checked for covering the reference's essential ideas (else partial credit); one extra model call |
| backend `.env` | `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_RETRIES`, `OLLAMA_RETRY_BACKOFF_SECONDS` | 120, 1, 0.5 |
| backend `.env` | `PREREQUISITE_MASTERY_THRESHOLD` | 0.80 |
| backend `.env` | `MAX_UPLOAD_BYTES` | 10485760 (10 MB) |
| backend `.env` | `WEB_MATERIAL_ENABLED`, `WEB_MATERIAL_MAX_ARTICLES`, `WEB_MATERIAL_MAX_WORDS`, `MAX_COURSES_PER_USER` | true, 6, 3000, 25 |
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
pip install -r backend/requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://tutor:tutor_password@localhost:5434/adaptive_tutor_test
python -m alembic -c alembic.ini upgrade head
cd backend
pytest --cov=app                   # the database user needs CREATEDB (migration tests)
ruff check .

# Frontend
cd frontend
npm test
```

Neither suite needs Ollama.


## Grading quality

Answers are graded by a local model, which is the weakest link of the tutor.
A flagged contradiction only counts when a second, simpler check explicitly
agrees; otherwise the answer gets partial credit and no misconception is
stored. To measure how well a model agrees with human judgement, edit
`backend/eval/grader_examples.json` (add your own labelled answers) and run,
from `backend`, `python -m app.tutor.grader_agreement`. Run it again with a
different `GRADER_MODEL` to compare models; report the numbers you measured,
not estimates.

To build an independent labelled set, run `python -m app.tutor.label_answers`
from `backend`: it shows 33 student answers (`eval/grader_to_label.json`, no
suggested grades) and saves your verdicts to `eval/grader_labels.json`. Then
`python -m app.tutor.grader_agreement eval/grader_labels.json`.

## License and attribution

Code: MIT, see [LICENSE](LICENSE). Course material fetched from Wikipedia is
CC BY-SA 4.0; each chunk keeps its article title and URL as its source.
