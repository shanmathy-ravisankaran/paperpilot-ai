from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.evaluation import router as evaluation_router
from app.api.health import router as health_router
from app.api.papers import router as papers_router
from app.api.qa import router as qa_router
from app.api.research import router as research_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Evidence-grounded research intelligence API.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(health_router)
    app.include_router(papers_router)
    app.include_router(qa_router)
    app.include_router(research_router)
    app.include_router(evaluation_router)
    return app


app = create_app()
