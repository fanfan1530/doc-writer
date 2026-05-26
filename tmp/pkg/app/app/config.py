from pydantic import SecretStr
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "智慧警务智能工作台"
    app_version: str = "2.0.0"
    debug: bool = False

    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model_large: str = "qwen2.5:72b"
    llm_model_small: str = "qwen2.5:7b"

    knowledge_dir: str = "./app/knowledge"
    llm_max_input_chars: int = 16000

    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60

    allowed_origins: list[str] = ["http://localhost:5174", "http://127.0.0.1:5174"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
