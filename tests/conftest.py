import pytest
from pathlib import Path

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Define a chave de API de teste para evitar erros de inicialização do SDK."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-deepseek-key")

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Redireciona o caminho do banco de dados SQLite para um diretório temporário."""
    test_db_path = tmp_path / "test_reviews.db"
    monkeypatch.setattr("src.database.db.DB_PATH", test_db_path)
    
    import src.database.db as db
    db.init_db()
    return test_db_path