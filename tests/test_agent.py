from pathlib import Path
from unittest.mock import patch, MagicMock
from src.agent import agent

def test_load_system_prompt_default_when_file_missing(monkeypatch):
    """Testa o prompt padrão caso o arquivo perfil_agente.txt não exista."""
    monkeypatch.setattr(agent, "PROMPT_FILE", Path("/caminho/inexistente/perfil.txt"))
    prompt = agent._load_system_prompt()
    assert prompt == "Você é um assistente especialista em análise de avaliações e reviews."

def test_load_system_prompt_from_file(tmp_path, monkeypatch):
    """Testa a leitura do prompt a partir de um arquivo existente."""
    fake_prompt_file = tmp_path / "perfil_agente.txt"
    fake_prompt_file.write_text("Prompt customizado de teste", encoding="utf-8")
    monkeypatch.setattr(agent, "PROMPT_FILE", fake_prompt_file)
    
    prompt = agent._load_system_prompt()
    assert prompt == "Prompt customizado de teste"

@patch("src.agent.agent.ChatOpenAI")
def test_analyze_review(mock_chat_openai):
    """Testa o fluxo da função analyze_review simulando a execução da cadeia LangChain."""
    mock_llm_instance = MagicMock()
    mock_chat_openai.return_value = mock_llm_instance
    
    with patch("langchain_core.runnables.RunnableSequence.invoke", return_value="Análise de teste concluída"):
        result = agent.analyze_review("Ótimo atendimento")
        assert result == "Análise de teste concluída"