from src.database import db


def test_save_and_get_all_reviews(temp_db):
    """Verifica a inserção e a listagem de registros formatados."""
    db.save_review("Produto muito bom", '{"sentimento": "positivo"}')
    reviews = db.get_all_reviews()

    assert len(reviews) == 1
    assert reviews[0].review_text == "Produto muito bom"
    assert reviews[0].agent_response == {"sentimento": "positivo"}


def test_get_review_by_id_found(temp_db):
    """Verifica a busca de um registro específico por ID."""
    db.save_review("Atendimento excelente", "Resposta texto puro")
    reviews = db.get_all_reviews()
    review_id = reviews[0].id

    review = db.get_review_by_id(review_id)
    assert review is not None
    assert review.id == review_id
    assert review.review_text == "Atendimento excelente"


def test_get_review_by_id_not_found(temp_db):
    """Verifica o retorno para busca de ID inexistente."""
    review = db.get_review_by_id(999)
    assert review is None


def test_format_entry_json_and_date_fallback():
    """Testa o tratamento de respostas em texto plano e datas fora do padrão."""
    row = {
        "id": 1,
        "review_text": "Teste",
        "agent_response": "Texto plano não-JSON",
        "created_at": "data_invalida",
    }
    formatted = db._format_entry(row)

    assert formatted.agent_response == "Texto plano não-JSON"
    assert formatted.id == 1
