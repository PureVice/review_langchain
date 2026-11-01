import io
from unittest.mock import patch

from src.schemas import ReviewRequest


@patch("src.web.app.review_service.get_all_reviews")
def test_index_route(mock_get_all, client):
    """Testa o acesso à rota principal /."""
    mock_get_all.return_value = []
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


@patch("src.web.app.review_service.get_review_by_id")
def test_show_review_not_found(mock_get_by_id, client):
    """Testa o acesso a uma avaliação inexistente, que deve redirecionar para a raiz."""
    mock_get_by_id.return_value = None
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


def test_swagger_docs(client):
    """Testa se a página de documentação do Swagger UI está acessível."""
    response = client.get("/apidocs/")
    assert response.status_code == 200


@patch("src.web.app.review_service.process_file_upload")
def test_upload_file_success(mock_upload, client):
    """Testa o envio de arquivo via POST /upload."""
    data = {"file": (io.BytesIO(b"content\nReview via CSV"), "test.csv")}
    response = client.post(
        "/upload",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 302
    mock_upload.assert_called_once_with("test.csv", b"content\nReview via CSV")


@patch("src.web.app.review_service.process_file_upload")
def test_upload_file_empty(mock_upload, client):
    """Testa POST /upload sem enviar arquivo."""
    response = client.post("/upload", data={}, follow_redirects=False)
    assert response.status_code == 302
    mock_upload.assert_not_called()


@patch("src.web.app.review_service.export_reviews_to_csv")
def test_export_csv_route(mock_export, client):
    """Testa o download do dataset no endpoint GET /export/csv."""
    mock_export.return_value = "id,content\n1,Excelente produto\n"
    response = client.get("/export/csv")
    assert response.status_code == 200
    assert "text/csv" in response.content_type
    assert (
        "attachment; filename=reviews_dataset.csv"
        in response.headers["Content-Disposition"]
    )
    assert "Excelente produto" in response.get_data(as_text=True)
