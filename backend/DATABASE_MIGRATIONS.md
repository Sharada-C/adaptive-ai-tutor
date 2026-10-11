# Database Migrations


## Database setup

The application uses PostgreSQL with the pgvector extension.

For a new database, run `python create_tables.py` from the `backend` directory with the backend virtual environment activated. This enables the `vector` extension and creates missing tables; it does not migrate existing tables.


## Alembic

Alembic configuration is in the repository root (alembic.ini). Migration revisions are in backend/alembic/versions.

From the repository root, check for schema differences using: .\backend\.venv\Scripts\python.exe -m alembic -c .\alembic.ini check

Generate a migration after reviewing model changes using: .\backend\.venv\Scripts\python.exe -m alembic -c .\alembic.ini revision --autogenerate -m 'describe schema change'

Inspect every generated migration before applying it. Apply migrations using: .\backend\.venv\Scripts\python.exe -m alembic -c .\alembic.ini upgrade head


## Existing databases

The initial Alembic revision records creation of the knowledge_chunks.subject_id index only. It is not a complete baseline migration for creating every application table from scratch. Assess an existing database schema before adopting Alembic migration history.

Back up important data before applying schema changes. Do not use create_tables.py as a substitute for migrations on an existing database.
