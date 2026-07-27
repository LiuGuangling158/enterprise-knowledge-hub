from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from core.config import settings
from database.session import init_db


app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.on_event("startup")
async def startup() -> None:
    if settings.jwt_secret == "change-me" and settings.app_env not in {"development", "local", "test"}:
        raise RuntimeError("JWT_SECRET must be changed outside development")
    init_db()


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ready"}
