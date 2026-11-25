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
    # Optional separate (usually larger) model used only for grading answers.
    # Empty = use llm_model.
    grader_model: str = ""
    embedding_model: str = "nomic-embed-text"

    # A concept is 'mastered', and unlocks what depends on it, at this score.
    prerequisite_mastery_threshold: float = 0.80

    # Ollama calls: per-request timeout and how many times to retry a
    # transient failure (connection error, timeout, 5xx).
    ollama_timeout_seconds: float = 120.0
    ollama_retries: int = 1
    ollama_retry_backoff_seconds: float = 0.5

    # Study material fetched automatically for student-created courses.
    web_material_enabled: bool = True
    wikipedia_api_url: str = "https://en.wikipedia.org/w/api.php"
    web_material_max_articles: int = 6
    web_material_max_words: int = 3000
    web_material_timeout_seconds: float = 10.0

    # How many private courses one student may create.
    max_courses_per_user: int = 25

    # Largest accepted knowledge-base upload.
    max_upload_bytes: int = 10 * 1024 * 1024

    # Authentication. SECRET_KEY signs login tokens. When it is not set a
    # random key is generated at start-up, which is safe but logs everyone
    # out whenever the server restarts. Set a long random value in .env.
    secret_key: str = ""
    access_token_minutes: int = 720

    # Optional: create (or promote) this admin account at start-up.
    admin_username: str = ""
    admin_password: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
