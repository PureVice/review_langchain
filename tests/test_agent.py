from unittest.mock import MagicMock, mock_open, patch

import pytest

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


# Correção: Fazendo o patch no método da classe Path em vez da instância PROMPT_FILE
@patch("src.agent.agent.Path.exists", return_value=False)
def test_load_system_prompt_file_not_found(mock_exists):
    """Testa o uso do prompt padrão caso o arquivo não seja encontrado."""
    from src.agent.agent import _load_system_prompt

    prompt = _load_system_prompt()
    assert "Você é um assistente especialista" in prompt


@patch("src.agent.agent.Path.exists", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data="Instruções personalizadas.")
def test_load_system_prompt_success(mock_file, mock_exists):
    """Testa a leitura bem-sucedida do arquivo de perfil do agente."""
    from src.agent.agent import _load_system_prompt

    prompt = _load_system_prompt()
    assert prompt == "Instruções personalizadas."


@patch("src.agent.agent.Path.exists", return_value=True)
@patch("builtins.open", side_effect=Exception("Erro simulado de leitura"))
def test_load_system_prompt_exception(mock_file, mock_exists):
    """Testa o fallback para o prompt padrão caso ocorra uma falha ao abrir o arquivo."""
    from src.agent.agent import _load_system_prompt

    prompt = _load_system_prompt()
    assert "Você é um assistente especialista" in prompt


@patch("src.agent.agent.ChatOpenAI")
def test_analyze_review_api_exception(mock_chat_openai):
    """Testa a propagação do erro quando a LangChain/OpenAI falha."""
    with patch(
        "langchain_core.runnables.RunnableSequence.invoke",
        side_effect=Exception("API limit exceeded"),
    ):
        request = ReviewRequest(review_text="Texto")
        with pytest.raises(Exception, match="API limit exceeded"):
            agent.analyze_review(request)
