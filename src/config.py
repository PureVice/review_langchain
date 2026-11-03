import logging
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GOOGLE_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    MODEL_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    LLM_PROVIDER: str = "gemini"
    DEBUG: bool = False
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/review_db"
    BATCH_API_THRESHOLD: int = 500
    MAX_CONCURRENCY: int = 5
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 1.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def google_key(self) -> str:
        """Retorna a chave de API configurada para o Google Gemini."""
        return self.GOOGLE_API_KEY or self.MODEL_API_KEY or self.OPENAI_API_KEY

    @property
    def deepseek_key(self) -> str:
        """Retorna a chave de API configurada para o DeepSeek."""
        return self.DEEPSEEK_API_KEY or self.MODEL_API_KEY or self.OPENAI_API_KEY

    @property
    def deepseek_base_url(self) -> str:
        """Retorna a URL base formatada para a API OpenAI-compatible do DeepSeek."""
        url = (self.DEEPSEEK_BASE_URL or "https://api.deepseek.com").strip().rstrip("/")
        if url.endswith("/anthropic"):
            url = url[: -len("/anthropic")]
        return url or "https://api.deepseek.com"

    @property
    def api_key(self) -> str:
        """Retorna a chave de API configurada para o modelo ativo."""
        if self.LLM_PROVIDER.strip().lower() == "deepseek":
            return self.deepseek_key
        return self.google_key


settings = Settings()


def setup_logging():
    """Configura o formato padrão de logs para a aplicação."""
    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
