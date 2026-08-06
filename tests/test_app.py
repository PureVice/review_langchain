import json
import pytest
from unittest.mock import patch
from src.web.app import app

@pytest.fixture
def client(temp_db):
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_index_route(client):
    """Testa se a rota principal GET / responde com status 200."""
    response = client.get("/")
    assert response.status_code == 200

def test_show_review_existing(client, temp_db):
    """Testa se a rota GET /review/<id> retorna 200 para um registro existente."""
    from src.database.db import save_review
    
    mock_response = json.dumps({
        "analise_dimensional": {
            "Atendimento": {"score": 8},
            "Qualidade": {"score": 9}
        },
        "metadados": {
            "dominios_detectados": [
                {"dominio": "atendimento", "confianca": 0.95}
            ]
        },
        "resumo": "Produto atendeu às expectativas"
    })
    
    save_review("Review de teste", mock_response)
    
    response = client.get("/review/1")
    assert response.status_code == 200

def test_show_review_not_found(client, temp_db):
    """Testa o redirecionamento (302) para a raiz quando o ID não é encontrado."""
    response = client.get("/review/999", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

@patch("src.web.app.analyze_review")
@patch("src.web.app.save_review")
def test_analyze_post_success(mock_save, mock_analyze, client):
    """Testa o envio de dados via POST /analyze com redirecionamento para /."""
    mock_json_response = json.dumps({
        "analise_dimensional": {
            "Atendimento": {"score": 10}
        },
        "metadados": {
            "dominios_detectados": [
                {"dominio": "geral", "confianca": 0.99}
            ]
        },
        "resumo": "Produto excelente"
    })
    mock_analyze.return_value = mock_json_response
    
    response = client.post("/analyze", data={"review_text": "Produto excelente"}, follow_redirects=False)
    
    mock_analyze.assert_called_once_with("Produto excelente")
    mock_save.assert_called_once_with("Produto excelente", mock_json_response)
    assert response.status_code == 302
    assert response.headers["Location"] == "/"

@patch("src.web.app.analyze_review")
@patch("src.web.app.save_review")
def test_analyze_post_empty_text(mock_save, mock_analyze, client):
    """Garante que texto em branco no formulário não aciona o agente nem salva no banco."""
    response = client.post("/analyze", data={"review_text": "   "}, follow_redirects=False)
    
    mock_analyze.assert_not_called()
    mock_save.assert_not_called()
    assert response.status_code == 302
    