from fastapi import FastAPI

from app.config import settings
from app.presentation.api.routes import router as api_router
from app.presentation.error_handlers import add_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(api_router, prefix="/api/v1")
    add_exception_handlers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
