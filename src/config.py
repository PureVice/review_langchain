from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Variáveis de ambiente com validação de tipo
    DEEPSEEK_API_KEY: str
    DATABASE_PATH: str = str(BASE_DIR / "reviews.db")
    DEBUG: bool = False

    # Configuração do carregamento do arquivo .env
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Instância única utilizada por toda a aplicação
settings = Settings()
