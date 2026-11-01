from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.schemas import Review, ReviewRequest, ReviewResponse
from src.service.review_service import ReviewService


def test_process_and_save_review():
    """Testa se o Service executa o Agent e formata os dados para salvar no Repository."""
    mock_repository = MagicMock()
    mock_agent_function = MagicMock()

    mock_agent_function.return_value = ReviewResponse(
        analysis={"sentimento": "positivo", "score": 10}
    )

    service = ReviewService(
        repository=mock_repository, agent_function=mock_agent_function
    )

    request = ReviewRequest(review_text="Serviço rápido e eficiente")
    service.process_and_save_review(request)

    mock_agent_function.assert_called_once_with(request)
    mock_repository.save.assert_called_once_with(
        review_text="Serviço rápido e eficiente",
        agent_response_str='{"sentimento": "positivo", "score": 10}',
    )


def test_process_and_save_review_string_output():
    """Testa a formatação e salvamento quando o Agente retorna uma string em vez de um dicionário."""
    mock_repository = MagicMock()
    mock_agent_function = MagicMock()

    mock_agent_function.return_value = ReviewResponse(
        analysis="O texto é apenas uma resposta descritiva."
    )

    service = ReviewService(
        repository=mock_repository, agent_function=mock_agent_function
    )

    request = ReviewRequest(review_text="Avaliação descritiva")
    service.process_and_save_review(request)

    mock_repository.save.assert_called_once_with(
        review_text="Avaliação descritiva",
        agent_response_str="O texto é apenas uma resposta descritiva.",
    )


def test_process_file_upload_csv():
    """Testa o processamento de upload de arquivo CSV com a coluna content."""
    mock_repository = MagicMock()
    mock_agent_function = MagicMock(
        return_value=ReviewResponse(analysis={"status": "ok"})
    )
    service = ReviewService(
        repository=mock_repository, agent_function=mock_agent_function
    )

    csv_bytes = b"id,content\n1,Produto excelente\n2,Entrega atrasou\n"
    count = service.process_file_upload("reviews.csv", csv_bytes)

    assert count == 2
    assert mock_repository.save.call_count == 2


def test_process_file_upload_json_list():
    """Testa o processamento de upload de arquivo JSON contendo lista de objetos com campo content."""
    mock_repository = MagicMock()
    mock_agent_function = MagicMock(
        return_value=ReviewResponse(analysis={"status": "ok"})
    )
    service = ReviewService(
        repository=mock_repository, agent_function=mock_agent_function
    )

    json_bytes = b'[{"content": "Review 1"}, {"content": "Review 2"}]'
    count = service.process_file_upload("reviews.json", json_bytes)

    assert count == 2
    assert mock_repository.save.call_count == 2


def test_process_file_upload_json_object_with_list():
    """Testa o processamento de upload de arquivo JSON com objeto raiz contendo a chave content."""
    mock_repository = MagicMock()
    mock_agent_function = MagicMock(
        return_value=ReviewResponse(analysis={"status": "ok"})
    )
    service = ReviewService(
        repository=mock_repository, agent_function=mock_agent_function
    )

    json_bytes = b'{"content": ["Review A", "Review B"]}'
    count = service.process_file_upload("reviews.json", json_bytes)

    assert count == 2
    assert mock_repository.save.call_count == 2


def test_process_file_upload_invalid_extension():
    """Testa erro ao enviar arquivo com extensão não suportada."""
    service = ReviewService(repository=MagicMock(), agent_function=MagicMock())
    with pytest.raises(ValueError, match="Formato de arquivo não suportado"):
        service.process_file_upload("reviews.txt", b"content")


def test_extract_reviews_csv_missing_content_column():
    """Testa erro quando o CSV não possui a coluna content."""
    service = ReviewService(repository=MagicMock(), agent_function=MagicMock())
    with pytest.raises(ValueError, match="coluna chamada 'content'"):
        service.extract_reviews_from_csv("id,texto\n1,Oi")


def test_export_reviews_to_csv():
    """Testa a geração do CSV a partir das avaliações salvas."""
    mock_repository = MagicMock()
    mock_repository.get_all.return_value = [
        Review(
            id=1,
            review_text="Ótimo fone de ouvido",
            agent_response={
                "metadados": {
                    "dominios_detectados": [{"dominio": "produto", "confianca": 0.9}]
                },
                "analise_dimensional": {
                    "RD": {"score": 8, "justificativa": "Boa descrição"},
                    "OB": {"score": 7, "justificativa": "Objetivo"},
                    "CL": {"score": 9, "justificativa": "Coerente"},
                    "UT": {"score": 8, "justificativa": "Útil"},
                },
            },
            created_at=datetime(2026, 11, 1, 15, 30, 0),
        )
    ]
    service = ReviewService(repository=mock_repository, agent_function=MagicMock())

    csv_output = service.export_reviews_to_csv()
    assert "id,content,dominios,rd_score" in csv_output
    assert "Ótimo fone de ouvido" in csv_output
    assert "produto" in csv_output
    assert "Boa descrição" in csv_output
