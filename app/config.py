from __future__ import annotations
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Picking Control Gudang API"
    debug: bool = True

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/picking.db"

    # JWT
    secret_key: str = "change-this-to-a-long-random-secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # MinIO / S3
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "picking-files"
    s3_region: str = "us-east-1"

    # Upload
    max_upload_size_mb: int = 20

    model_config = {"env_prefix": "", "env_file": "../.env", "extra": "ignore"}


settings = Settings()
