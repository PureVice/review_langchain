import logging
import sys
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


def setup_logging():
    """Configura o sistema de logs centralizado da aplicação."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
