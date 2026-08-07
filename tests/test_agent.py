from unittest.mock import MagicMock, patch

from src.agent import agent
from src.schemas import ReviewRequest, ReviewResponse


@patch("src.agent.agent.ChatOpenAI")
def test_analyze_review(mock_chat_openai):
    """Testa o fluxo da função analyze_review simulando a execução da cadeia LangChain."""
    mock_llm_instance = MagicMock()
    mock_chat_openai.return_value = mock_llm_instance

    with patch(
        "langchain_core.runnables.RunnableSequence.invoke",
        return_value="Análise de teste concluída",
    ):
        request = ReviewRequest(review_text="Ótimo atendimento")
        result = agent.analyze_review(request)

        assert isinstance(result, ReviewResponse)
        assert result.analysis == "Análise de teste concluída"
