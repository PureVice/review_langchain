from unittest.mock import MagicMock

from src.schemas import ReviewRequest, ReviewResponse
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
