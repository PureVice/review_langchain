from unittest.mock import MagicMock, patch

import pytest

from src.database.postgres_repository import PostgresRepository
from src.schemas import Review


@pytest.fixture
def mock_db():
    """Cria mocks para a conexão e o cursor do psycopg2."""
    with patch("src.database.postgres_repository.psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_connect.return_value = mock_conn
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        yield mock_connect, mock_conn, mock_cursor


def test_init_db_success(mock_db):
    """Verifica se a tabela é criada na inicialização."""
    _, mock_conn, mock_cursor = mock_db

    PostgresRepository(db_url="fake_url")

    executed_query = mock_cursor.execute.call_args[0][0]

    assert "CREATE TABLE IF NOT EXISTS reviews" in executed_query
    assert "id SERIAL PRIMARY KEY" in executed_query
    mock_conn.commit.assert_called()


@patch("src.database.postgres_repository.PostgresRepository._init_db")
def test_save_success(mock_init_db, mock_db):
    """Verifica se o comando INSERT é executado corretamente."""
    _, mock_conn, mock_cursor = mock_db
    repo = PostgresRepository(db_url="fake_url")

    repo.save("Produto excelente", '{"score": 10}')

    mock_cursor.execute.assert_called_with(
        "INSERT INTO reviews (review_text, agent_response) VALUES (%s, %s)",
        ("Produto excelente", '{"score": 10}'),
    )
    mock_conn.commit.assert_called_once()


@patch("src.database.postgres_repository.PostgresRepository._init_db")
def test_get_all_success(mock_init_db, mock_db):
    """Verifica se o SELECT traz os dados e os formata como Pydantic."""
    _, _, mock_cursor = mock_db

    mock_cursor.fetchall.return_value = [
        {
            "id": 1,
            "review_text": "Bom",
            "agent_response": '{"status": "ok"}',
            "created_at": "2026-08-07 12:00:00",
        }
    ]

    repo = PostgresRepository(db_url="fake_url")
    results = repo.get_all()

    assert len(results) == 1
    assert isinstance(results[0], Review)
    assert results[0].id == 1
    assert results[0].agent_response == {"status": "ok"}


@patch("src.database.postgres_repository.PostgresRepository._init_db")
def test_get_by_id_found(mock_init_db, mock_db):
    """Verifica a busca de um registro específico."""
    _, _, mock_cursor = mock_db

    mock_cursor.fetchone.return_value = {
        "id": 5,
        "review_text": "Ruim",
        "agent_response": "Resposta pura",
        "created_at": "2026-08-07 12:00:00",
    }

    repo = PostgresRepository(db_url="fake_url")
    result = repo.get_by_id(5)

    assert result.id == 5
    assert result.agent_response == "Resposta pura"
    mock_cursor.execute.assert_called_with(
        "SELECT id, review_text, agent_response, created_at FROM reviews WHERE id = %s",
        (5,),
    )


@patch("src.database.postgres_repository.PostgresRepository._init_db")
def test_get_by_id_not_found(mock_init_db, mock_db):
    """Verifica o comportamento quando o ID não existe."""
    _, _, mock_cursor = mock_db
    mock_cursor.fetchone.return_value = None

    repo = PostgresRepository(db_url="fake_url")
    result = repo.get_by_id(99)

    assert result is None


def test_repository_exceptions(mock_db):
    """Garante que as exceções do banco sejam propagadas no repositório."""
    mock_connect, _, _ = mock_db
    mock_connect.side_effect = Exception("Falha de conexão Postgres")

    repo = PostgresRepository.__new__(PostgresRepository)
    repo.db_url = "fake_url"

    with pytest.raises(Exception, match="Falha de conexão Postgres"):
        repo._init_db()

    with pytest.raises(Exception, match="Falha de conexão Postgres"):
        repo.save("Teste", "Resposta")

    with pytest.raises(Exception, match="Falha de conexão Postgres"):
        repo.get_all()

    with pytest.raises(Exception, match="Falha de conexão Postgres"):
        repo.get_by_id(1)
