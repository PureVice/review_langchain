import sqlite3
from datetime import datetime

from src.database import db


def test_init_db_creates_table(temp_db):
    """Verifica se a tabela 'reviews' é criada corretamente."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='reviews';"
    )
    table = cursor.fetchone()
    assert table is not None
    assert table[0] == "reviews"


def test_save_and_get_all_reviews(temp_db):
    """Verifica a inserção e a listagem de registros formatados."""
    db.save_review("Produto muito bom", '{"sentimento": "positivo"}')
    reviews = db.get_all_reviews()

    assert len(reviews) == 1
    assert reviews[0]["review_text"] == "Produto muito bom"
    assert reviews[0]["agent_response"] == {"sentimento": "positivo"}


def test_get_review_by_id_found(temp_db):
    """Verifica a busca de um registro específico por ID."""
    db.save_review("Atendimento excelente", "Resposta texto puro")
    reviews = db.get_all_reviews()
    review_id = reviews[0]["id"]

    entry = db.get_review_by_id(review_id)
    assert entry is not None
    assert entry["review_text"] == "Atendimento excelente"
    assert entry["agent_response"] == "Resposta texto puro"


def test_get_review_by_id_not_found(temp_db):
    """Garante o retorno None ao buscar um ID inexistente."""
    entry = db.get_review_by_id(999)
    assert entry is None


def test_format_entry_json_and_date_fallback():
    """Testa o tratamento de respostas em texto plano e datas fora do padrão."""
    row = {
        "id": 1,
        "review_text": "Teste",
        "agent_response": "Texto plano não-JSON",
        "created_at": "data_invalida",
    }
    formatted = db._format_entry(row)
    assert formatted["agent_response"] == "Texto plano não-JSON"
    assert isinstance(formatted["created_at"], datetime)
