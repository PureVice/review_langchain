import json
import logging
from pathlib import Path

from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config import settings
from src.schemas import ReviewRequest, ReviewResponse

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


def analyze_review(request: ReviewRequest) -> ReviewResponse:
    """
    Recebe a requisição validada pelo Pydantic, executa o fluxo do agente e retorna um ReviewResponse.
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
        raw_output = chain.invoke({"input": request.review_text})
        logger.info("Processamento da LLM concluído com sucesso.")

        # Tenta converter a saída para dicionário/estrutura de dados se for um JSON válido
        try:
            parsed_analysis = json.loads(raw_output)
        except (json.JSONDecodeError, TypeError):
            parsed_analysis = raw_output

        return ReviewResponse(analysis=parsed_analysis)
    except Exception:
        logger.exception("Falha na chamada da API LLM / LangChain.")
        raise
