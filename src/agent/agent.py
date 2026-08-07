import logging
from pathlib import Path

from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config import settings

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent / "perfil_agente.txt"


def _load_system_prompt() -> str:
    """Carrega as instruções do agente a partir do arquivo de perfil."""
    if not PROMPT_FILE.exists():
        logger.warning(
            "Arquivo de perfil '%s' não encontrado. Usando prompt genérico padrão.",
            PROMPT_FILE,
        )
        return "Você é um assistente especialista em análise de avaliações e reviews."

    logger.info("Carregando prompt do sistema a partir de: %s", PROMPT_FILE)
    try:
        with open(PROMPT_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        logger.exception(
            "Erro ao ler o arquivo de perfil '%s'. Usando prompt padrão.", PROMPT_FILE
        )
        return "Você é um assistente especialista em análise de avaliações e reviews."


def analyze_review(review_text: str) -> str:
    """
    Recebe o texto do usuário, aplica o prompt do agente e faz a chamada à LLM via LangChain.
    """
    logger.info("Iniciando a chamada do agente LLM para processar a avaliação.")
    system_prompt_text = _load_system_prompt()

    prompt = ChatPromptTemplate.from_messages(
        [SystemMessage(content=system_prompt_text), ("human", "{input}")]
    )

    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )

    chain = prompt | llm | StrOutputParser()

    try:
        response = chain.invoke({"input": review_text})
        logger.info("Processamento da LLM concluído com sucesso.")
        return response
    except Exception:
        logger.exception("Falha na chamada da API LLM / LangChain.")
        raise
