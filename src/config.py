import logging
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GOOGLE_API_KEY: str = ""
    MODEL_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    DEBUG: bool = False
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/review_db"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def api_key(self) -> str:
        """Retorna a chave de API configurada para o modelo."""
        return self.GOOGLE_API_KEY or self.MODEL_API_KEY or self.OPENAI_API_KEY


settings = Settings()


def setup_logging():
    """Configura o formato padrão de logs para a aplicação."""
    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
