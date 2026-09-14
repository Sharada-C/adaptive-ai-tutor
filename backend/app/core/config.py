from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://tutor:tutor_password@localhost:5434/adaptive_tutor"
    )


settings = Settings()