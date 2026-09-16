"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Castor AI Backend configuration."""

    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.1

    # Database (mock)
    database_url: str = "sqlite+aiosqlite:///./castor.db"

    # RAG
    vector_db_path: str = "./chroma_db"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:4200"]  # Angular frontend

    # Security
    sensitive_keywords: list[str] = [
        "salario",
        "sueldo",
        "password",
        "contraseña",
        "token",
        "secret",
        "credito",
    ]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
