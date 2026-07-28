from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "knowledge-platform"
    app_env: str = "development"
    database_url: str = "sqlite:///./knowledge_v1.db"
    jwt_secret: str = "change-me"
    access_token_expire_minutes: int = 60 * 8
    upload_dir: str = "uploads"
    max_upload_bytes: int = 5 * 1024 * 1024
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    demo_tenant_id: str = "tenant-demo"
    demo_department_id: str = "dept-product"

    class Config:
        env_file = ".env"
        env_prefix = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
