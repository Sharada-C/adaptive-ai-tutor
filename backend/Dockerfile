# Build from the repository root:  docker build -f backend/Dockerfile -t adaptive-tutor-api .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so code changes do not reinstall them.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY alembic.ini alembic.ini
COPY backend backend

# Run as an unprivileged user.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

WORKDIR /app/backend
EXPOSE 8000

# Apply migrations, then serve.
CMD ["sh", "-c", "python -m alembic -c /app/alembic.ini upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
