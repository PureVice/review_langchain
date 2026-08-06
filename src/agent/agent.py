import os
from pathlib import Path

from langchain_core.messages import SystemMessage  # Importação adicionada
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

PROMPT_FILE = Path(__file__).resolve().parent / "perfil_agente.txt"


def _load_system_prompt() -> str:
    """Carrega as instruções do agente a partir do arquivo de perfil."""
    if not PROMPT_FILE.exists():
        return "Você é um assistente especialista em análise de avaliações e reviews."

    with open(PROMPT_FILE, encoding="utf-8") as f:
        return f.read().strip()


def analyze_review(review_text: str) -> str:
    """
    Recebe o texto do usuário, aplica o prompt do agente e faz a chamada à LLM via LangChain.
    """
    system_prompt_text = _load_system_prompt()

    prompt = ChatPromptTemplate.from_messages(
        [SystemMessage(content=system_prompt_text), ("human", "{input}")]
    )

    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )

    chain = prompt | llm | StrOutputParser()

    return chain.invoke({"input": review_text})
