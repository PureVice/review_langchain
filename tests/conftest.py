import os
import sqlite3
from unittest.mock import patch

import pytest

from src.web.app import app


@pytest.fixture
def temp_db(tmp_path):
    """Cria um banco de dados temporário para testes e atualiza as configurações."""
    db_file = tmp_path / "test_reviews.db"
    db_path_str = str(db_file)

    # Mantemos o patch apenas no settings.
    # O ReviewRepository consumirá esta configuração ao ser instanciado.
    with patch("src.config.settings.DATABASE_PATH", db_path_str):
        conn = sqlite3.connect(db_path_str)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_text TEXT NOT NULL,
                agent_response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.commit()
        conn.close()

        yield db_file


@pytest.fixture
def mock_env_vars():
    """Garante que as variáveis de ambiente necessárias estejam presentes nos testes."""
    with patch.dict(
        os.environ,
        {
            "DEEPSEEK_API_KEY": "test_key",
            "DEBUG": "False",
        },
    ):
        yield


@pytest.fixture
def client(temp_db, mock_env_vars):
    """Cria o cliente de testes da aplicação Flask."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
