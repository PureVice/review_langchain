from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.schemas import Review, ReviewRequest, ReviewResponse
from src.service.review_service import ReviewService


def test_process_and_save_review():
    """Testa se o Service executa o Agent e formata os dados e métricas para salvar no Repository."""
    mock_repository = MagicMock()
    mock_agent_function = MagicMock()

    mock_agent_function.return_value = ReviewResponse(
        analysis={"sentimento": "positivo", "score": 10},
        execution_time=1.25,
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
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
        execution_time=1.25,
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
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
        execution_time=0.0,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
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
    assert "execution_time,input_tokens,output_tokens,total_tokens" in csv_output
    assert "Ótimo fone de ouvido" in csv_output
    assert "produto" in csv_output
    assert "Boa descrição" in csv_output


def test_retry_with_exponential_backoff_and_jitter():
    """Testa se o pipeline aplica retry com backoff exponencial + jitter quando ocorrem falhas transitórias."""
    mock_repository = MagicMock()
    mock_agent = MagicMock(
        side_effect=[
            RuntimeError("Rate limit 429"),
            ReviewResponse(analysis={"ok": True}, execution_time=0.5, total_tokens=42),
        ]
    )

    service = ReviewService(
        repository=mock_repository,
        agent_function=mock_agent,
        max_retries=2,
        retry_base_delay=0.001,
    )

    count = service.process_reviews_batch(["Avaliação com falha transitória"])
    assert count == 1
    assert mock_agent.call_count == 2
    mock_repository.save.assert_called_once()


def test_batch_api_strategy_selected_above_threshold():
    """Testa se a estratégia Gemini Batch API é selecionada para lotes acima do threshold (ex: > 500)."""
    mock_repository = MagicMock()
    mock_single_agent = MagicMock()
    mock_batch_agent = MagicMock(
        side_effect=lambda reqs: [
            ReviewResponse(
                analysis={"batch": True}, execution_time=0.1, total_tokens=10
            )
            for _ in reqs
        ]
    )

    service = ReviewService(
        repository=mock_repository,
        agent_function=mock_single_agent,
        batch_agent_function=mock_batch_agent,
        batch_api_threshold=500,
    )

    reviews_list = [f"Review número {i}" for i in range(501)]
    count = service.process_reviews_batch(reviews_list)

    assert count == 501
    mock_batch_agent.assert_called_once()
    mock_single_agent.assert_not_called()
    assert mock_repository.save.call_count == 501


def test_checkpoint_resume_in_concurrent_pipeline(tmp_path):
    """Testa se o checkpointing pula avaliações já persistidas e limpa o checkpoint ao concluir."""
    checkpoint_file = tmp_path / "checkpoint.json"
    mock_repository = MagicMock()
    mock_agent = MagicMock(return_value=ReviewResponse(analysis={"ok": True}))

    service = ReviewService(
        repository=mock_repository,
        agent_function=mock_agent,
        checkpoint_path=checkpoint_file,
    )

    # Simula que o item 0 já foi concluído em uma execução anterior interrompida
    first_hash = service._review_hash(0, "Review 1")
    service._update_checkpoint({first_hash})

    count = service.process_reviews_batch(["Review 1", "Review 2"])
    assert count == 1
    assert mock_agent.call_count == 1
    assert not checkpoint_file.exists()
