import sqlite3

import pytest

from src.database.sqlite_repository import SQLiteRepository


def test_save_and_get_all_reviews(temp_db):
    """Verifica a inserção e a listagem de registros formatados."""
    repo = SQLiteRepository(db_path=str(temp_db))

    repo.save("Produto muito bom", '{"sentimento": "positivo"}')
    reviews = repo.get_all()

    assert len(reviews) == 1
    assert reviews[0].review_text == "Produto muito bom"
    assert reviews[0].agent_response == {"sentimento": "positivo"}


def test_get_review_by_id_found(temp_db):
    """Verifica a busca de um registro específico por ID."""
    repo = SQLiteRepository(db_path=str(temp_db))

    repo.save("Atendimento excelente", "Resposta texto puro")
    reviews = repo.get_all()
    review_id = reviews[0].id

    review = repo.get_by_id(review_id)

    assert review is not None
    assert review.id == review_id
    assert review.review_text == "Atendimento excelente"


def test_get_review_by_id_not_found(temp_db):
    """Verifica o retorno para busca de ID inexistente."""
    repo = SQLiteRepository(db_path=str(temp_db))
    review = repo.get_by_id(999)
    assert review is None


def test_format_entry_json_and_date_fallback(temp_db):
    """Testa o tratamento de respostas em texto plano e datas fora do padrão."""
    repo = SQLiteRepository(db_path=str(temp_db))
    row = {
        "id": 1,
        "review_text": "Teste",
        "agent_response": "Texto plano não-JSON",
        "created_at": "data_invalida",
    }
    formatted = repo._format_entry(row)

    assert formatted.agent_response == "Texto plano não-JSON"
    assert formatted.id == 1


def test_repository_exceptions(tmp_path):
    """Força erros de banco de dados apontando para um diretório em vez de um arquivo."""
    invalid_db_path = str(tmp_path)

    with pytest.raises(sqlite3.OperationalError):
        SQLiteRepository(db_path=invalid_db_path)

    repo_failing = SQLiteRepository.__new__(SQLiteRepository)
    repo_failing.db_path = invalid_db_path

    with pytest.raises(sqlite3.OperationalError):
        repo_failing.save("Teste", "Resposta")

    with pytest.raises(sqlite3.OperationalError):
        repo_failing.get_all()

    with pytest.raises(sqlite3.OperationalError):
        repo_failing.get_by_id(1)
