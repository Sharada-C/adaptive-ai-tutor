from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Values are read from environment variables, then from a ``.env`` file.
    The repository-root ``.env`` is loaded first and ``backend/.env`` (if it
    exists) overrides it, so the backend works whether it is started from the
    repository root or from the ``backend`` directory.
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://tutor:tutor_password@localhost:5434/adaptive_tutor"
    )

    # Comma-separated list of browser origins allowed to call the API.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Ollama serves both the LLM and the embedding model.
    ollama_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "llama3.2:3b"
    embedding_model: str = "nomic-embed-text"

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
