import requests
from fastapi import FastAPI, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine

from app.api.curriculum import router as curriculum_router
from app.api.student import router as student_router
from app.api.assessment import router as assessment_router
from app.api.planner import router as planner_router
from app.api.tutor import router as tutor_router
from app.api.quiz import router as quiz_router
from app.api.evaluation import router as evaluation_router
from app.api.next import router as next_router
from app.api.knowledge import router as knowledge_router
from app.api.diagnostic import router as diagnostic_router


app = FastAPI(
    title="Adaptive AI Tutor",
    version="1.0.0",
)


# Allow the React/Vite frontend to communicate with FastAPI.
# Origins are configurable through the CORS_ORIGINS setting.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(requests.exceptions.RequestException)
def handle_llm_unavailable(
    request: Request,
    exc: requests.exceptions.RequestException,
):
    """Report a clear error when Ollama cannot be reached.

    Every LLM and embedding call goes through ``requests``. Without this
    handler an offline or misconfigured Ollama surfaces as an opaque
    plain-text 500, which the frontend cannot display.
    """

    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "The AI model service (Ollama) is unavailable. "
                f"Make sure it is running at {settings.ollama_base_url} "
                f"and that the models '{settings.llm_model}' and "
                f"'{settings.embedding_model}' are installed."
            ),
        },
    )


api_router = APIRouter()


api_router.include_router(curriculum_router)
api_router.include_router(student_router)
api_router.include_router(assessment_router)
api_router.include_router(planner_router)
api_router.include_router(tutor_router)
api_router.include_router(quiz_router)
api_router.include_router(evaluation_router)
api_router.include_router(next_router)
api_router.include_router(knowledge_router)
api_router.include_router(diagnostic_router)


app.include_router(api_router)


def _llm_status() -> str:
    """Return whether Ollama answers. Never raises."""

    try:
        response = requests.get(
            f"{settings.ollama_base_url.rstrip('/')}/api/tags",
            timeout=2,
        )
        response.raise_for_status()
        return "available"

    except requests.exceptions.RequestException:
        return "unavailable"


@app.get("/health")
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected",
            "llm": _llm_status(),
            "service": "adaptive-ai-tutor",
        }

    except Exception as e:
        return {
            "status": "error",
            "database": "disconnected",
            "detail": str(e),
        }
