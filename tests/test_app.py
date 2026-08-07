from unittest.mock import patch

from src.schemas import ReviewRequest


def test_index_route(client):
    """Testa o acesso à rota principal /."""
    response = client.get("/")
    assert response.status_code == 200


@patch("src.web.app.review_service.process_and_save_review")
def test_analyze_post_success(mock_process, client):
    """Testa o envio de dados via POST /analyze com redirecionamento para /."""
    response = client.post(
        "/analyze", data={"review_text": "Produto excelente"}, follow_redirects=False
    )

    assert response.status_code == 302
    mock_process.assert_called_once_with(ReviewRequest(review_text="Produto excelente"))


def test_show_review_not_found(client, temp_db):
    """Testa o acesso a uma avaliação inexistente, que deve redirecionar para a raiz."""
    response = client.get("/review/9999", follow_redirects=False)
    assert response.status_code == 302
    assert "/" in response.location


@patch("src.web.app.review_service.process_and_save_review")
def test_analyze_post_validation_error(mock_process, client):
    """Testa o envio de dados inválidos (texto vazio) para acionar o ValidationError."""
    response = client.post("/analyze", data={"review_text": ""}, follow_redirects=False)
    assert response.status_code == 302
    mock_process.assert_not_called()


@patch(
    "src.web.app.review_service.process_and_save_review",
    side_effect=Exception("Erro genérico"),
)
def test_analyze_post_exception(mock_process, client):
    """Testa o comportamento do controller quando o Service levanta uma exceção genérica."""
    response = client.post(
        "/analyze", data={"review_text": "Texto válido"}, follow_redirects=False
    )
    assert response.status_code == 302
    mock_process.assert_called_once()
