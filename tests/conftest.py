import os
from unittest.mock import patch

import pytest

# 1. Configura as variáveis de ambiente base
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DEEPSEEK_API_KEY"] = "test_key"
os.environ["DEBUG"] = "False"

# 2. Força a sobrescrita das configurações na memória caso o Pydantic já tenha lido o .env.
# 3. Bloqueia a execução do _init_db para que nenhuma tabela tente ser criada
#    durante a fase de coleta de testes do Pytest.
with patch("src.config.settings.DATABASE_URL", "sqlite:///:memory:"):
    with patch("src.database.sqlalchemy_repository.SQLAlchemyRepository._init_db"):
        from src.web.app import app


@pytest.fixture
def client():
    """Cria o cliente de testes da aplicação Flask."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
