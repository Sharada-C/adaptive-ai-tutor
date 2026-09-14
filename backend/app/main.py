from fastapi import FastAPI, APIRouter
from sqlalchemy import text

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


@app.get("/health")
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected",
            "service": "adaptive-ai-tutor",
        }

    except Exception as e:
        return {
            "status": "error",
            "database": "disconnected",
            "detail": str(e),
        }