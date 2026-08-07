import os
from unittest.mock import patch

import pytest

# Injeta variáveis de ambiente simuladas ANTES de importar a aplicação.
# Isso impede que o sistema tente ler seu .env local.
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_db"
os.environ["DEEPSEEK_API_KEY"] = "test_key"
os.environ["DEBUG"] = "False"

# Isolamento de Importação:
# Mockamos o _init_db apenas durante a importação do app.
# Isso impede chamadas ao banco real na fase de coleta do Pytest.
with patch("src.database.postgres_repository.PostgresRepository._init_db"):
    from src.web.app import app


@pytest.fixture
def client():
    """Cria o cliente de testes da aplicação Flask."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
