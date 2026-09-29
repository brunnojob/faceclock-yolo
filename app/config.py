from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_key: str
    master_key: str
    database_url: str = "sqlite:///./data/faceclock.db"
    yolo_model: str = "models/yolov8n-face.pt"
    arcface_model: str = "models/arcface_w600k_r50.onnx"
    match_threshold: float = 0.52
    review_threshold: float = 0.42
    rate_limit_per_minute: int = 30
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FACECLOCK_")


@lru_cache
def get_settings() -> Settings:
    return Settings()

