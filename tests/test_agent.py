from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.agent import agent
from src.schemas import ReviewRequest, ReviewResponse


@patch("src.agent.agent.ChatGoogleGenerativeAI")
def test_analyze_review(mock_chat_gemini):
    """Testa o fluxo da função analyze_review simulando a execução da cadeia LangChain."""
    mock_llm_instance = MagicMock()
    mock_chat_gemini.return_value = mock_llm_instance

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


@patch("src.agent.agent.ChatGoogleGenerativeAI")
def test_analyze_review_api_exception(mock_chat_gemini):
    """Testa a propagação do erro quando o Gemini/LangChain falha."""
    with patch(
        "langchain_core.runnables.RunnableSequence.invoke",
        side_effect=Exception("API limit exceeded"),
    ):
        request = ReviewRequest(review_text="Texto")
        with pytest.raises(Exception, match="API limit exceeded"):
            agent.analyze_review(request)


@patch("src.agent.agent.ChatGoogleGenerativeAI")
def test_analyze_review_with_usage_metadata(mock_chat_gemini):
    """Testa a extração de contagem de tokens e tempo de execução de uma AIMessage."""
    mock_ai_msg = MagicMock()
    mock_ai_msg.content = '```json\n{"score": 9}\n```'
    mock_ai_msg.usage_metadata = {
        "input_tokens": 120,
        "output_tokens": 80,
        "total_tokens": 200,
    }

    with patch(
        "langchain_core.runnables.RunnableSequence.invoke",
        return_value=mock_ai_msg,
    ):
        request = ReviewRequest(review_text="Produto incrível")
        result = agent.analyze_review(request)

        assert result.analysis == {"score": 9}
        assert result.input_tokens == 120
        assert result.output_tokens == 80
        assert result.total_tokens == 200
        assert result.execution_time >= 0.0


@patch("src.agent.agent.genai.Client")
def test_analyze_reviews_batch_api_success(mock_client_cls):
    """Testa o fluxo de lote usando a Gemini Batch API."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_resp_item = MagicMock()
    mock_resp_item.error = None
    mock_resp_item.response.text = '{"status": "batch_ok"}'
    mock_resp_item.response.usage_metadata.prompt_token_count = 50
    mock_resp_item.response.usage_metadata.candidates_token_count = 30
    mock_resp_item.response.usage_metadata.total_token_count = 80

    mock_batch_job = MagicMock()
    mock_batch_job.name = "batches/test-123"
    mock_batch_job.state.value = "JOB_STATE_SUCCEEDED"
    mock_batch_job.dest.inlined_responses = [mock_resp_item]

    mock_client.batches.create.return_value = mock_batch_job

    reqs = [ReviewRequest(review_text="Review em lote")]
    results = agent.analyze_reviews_batch_api(reqs, poll_interval=0.01)

    assert len(results) == 1
    assert results[0].analysis == {"status": "batch_ok"}
    assert results[0].input_tokens == 50
    assert results[0].output_tokens == 30
    assert results[0].total_tokens == 80


def test_agente_analysis_output_schema_validation():
    """Testa se a saída estruturada do perfil_agente (escala 1 a 5 e validações) valida no Pydantic."""
    from src.schemas import AgenteAnalysisOutput

    payload = {
        "metadados": {
            "dominios_detectados": [{"dominio": "produto", "confianca": 0.95}]
        },
        "evidencias_estruturadas": [
            {
                "trecho": "o produto é ótimo e funcionou bem",
                "dimensoes": ["RD", "OB", "UT"],
                "polaridade_relato": "positivo",
            }
        ],
        "analise_dimensional": {
            "RD": {
                "justificativa": "Menciona atributos e contexto.",
                "avaliabilidade": 1.0,
                "confianca": 0.95,
                "score": 4,
            },
            "OB": {
                "justificativa": "Fatos claros.",
                "avaliabilidade": 1.0,
                "confianca": 0.95,
                "score": 5,
            },
            "CL": {
                "justificativa": "Sem contradição.",
                "avaliabilidade": 0.0,
                "confianca": 0.90,
                "score": 3,
            },
            "UT": {
                "justificativa": "Reduz incerteza de compra.",
                "avaliabilidade": 1.0,
                "confianca": 0.95,
                "score": 4,
            },
        },
        "validacoes": {
            "anti_length_bias_applied": True,
            "absence_not_penalized_as_contradiction": True,
            "independence_of_sentiment_maintained": True,
            "halo_effect_mitigated": True,
        },
    }

    validated = AgenteAnalysisOutput.model_validate(payload)
    assert validated.analise_dimensional.RD.score == 4
    assert validated.analise_dimensional.CL.score == 3
    assert validated.validacoes.halo_effect_mitigated is True
