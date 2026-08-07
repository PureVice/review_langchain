import json
from unittest.mock import patch

from src.schemas import ReviewRequest


def test_index_route(client):
    """Testa o acesso à rota principal /."""
    response = client.get("/")
    assert response.status_code == 200


@patch("src.web.app.analyze_review")
@patch("src.web.app.save_review")
def test_analyze_post_success(mock_save, mock_analyze, client):
    """Testa o envio de dados via POST /analyze com redirecionamento para /."""
    mock_json_response = json.dumps(
        {
            "analise_dimensional": {"Atendimento": {"score": 10}},
            "metadados": {
                "dominios_detectados": [{"dominio": "geral", "confianca": 0.99}]
            },
            "resumo": "Produto excelente",
        }
    )
    mock_analyze.return_value = mock_json_response

    response = client.post(
        "/analyze", data={"review_text": "Produto excelente"}, follow_redirects=False
    )

    assert response.status_code == 302
    mock_analyze.assert_called_once_with(ReviewRequest(review_text="Produto excelente"))
    mock_save.assert_called_once()
