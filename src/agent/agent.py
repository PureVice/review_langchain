import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import settings
from src.schemas import ReviewRequest, ReviewResponse

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent / "perfil_agente.txt"

TERMINAL_BATCH_STATES = {
    "JOB_STATE_SUCCEEDED",
    "JOB_STATE_PARTIALLY_SUCCEEDED",
    "JOB_STATE_FAILED",
    "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED",
}


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


def _parse_raw_output(raw_output: str) -> dict[str, Any] | list[Any] | str:
    """Converte a saída textual da LLM para estrutura JSON quando possível."""
    if not isinstance(raw_output, str):
        return raw_output

    cleaned = raw_output.strip()
    fenced_match = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$", cleaned, flags=re.DOTALL | re.IGNORECASE
    )
    if fenced_match:
        cleaned = fenced_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return raw_output


def analyze_review(request: ReviewRequest) -> ReviewResponse:
    """
    Recebe a requisição validada pelo Pydantic, executa o fluxo do agente e retorna um ReviewResponse
    contendo a análise, o tempo de execução e a contagem de tokens.
    """
    logger.info("Iniciando a chamada do agente LLM para processar a avaliação.")
    system_prompt_text = _load_system_prompt()

    prompt = ChatPromptTemplate.from_messages(
        [SystemMessage(content=system_prompt_text), ("human", "{input}")]
    )

    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.api_key or None,
        temperature=0.2,
    )

    chain = prompt | llm

    try:
        start_time = time.perf_counter()
        result = chain.invoke({"input": request.review_text})
        execution_time = round(time.perf_counter() - start_time, 4)
        logger.info(
            "Processamento da LLM concluído com sucesso em %.4fs.", execution_time
        )

        if hasattr(result, "content"):
            content = result.content
            if isinstance(content, list):
                raw_output = "".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
            else:
                raw_output = str(content)
            usage = getattr(result, "usage_metadata", None) or {}
        else:
            raw_output = str(result)
            usage = {}

        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        total_tokens = int(
            usage.get("total_tokens", 0) or (input_tokens + output_tokens)
        )

        parsed_analysis = _parse_raw_output(raw_output)

        return ReviewResponse(
            analysis=parsed_analysis,
            execution_time=execution_time,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
    except Exception:
        logger.exception("Falha na chamada da API LLM / LangChain.")
        raise


def analyze_reviews_batch_api(
    requests: list[ReviewRequest], poll_interval: float = 2.0
) -> list[ReviewResponse]:
    """
    Executa um lote grande de avaliações utilizando a Gemini Batch API (google.genai.Client.batches).
    Ideal para lotes acima de 500 avaliações.
    """
    if not requests:
        return []

    logger.info(
        "Iniciando processamento via Gemini Batch API para %d avaliações.",
        len(requests),
    )
    system_prompt_text = _load_system_prompt()
    client = genai.Client(api_key=settings.api_key or None)

    inlined_requests = [
        types.InlinedRequest(
            model=settings.GEMINI_MODEL,
            contents=req.review_text,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt_text,
                temperature=0.2,
            ),
        )
        for req in requests
    ]

    start_time = time.perf_counter()
    batch_job = client.batches.create(
        model=settings.GEMINI_MODEL,
        src=inlined_requests,
    )

    while True:
        state_str = (
            batch_job.state.value
            if hasattr(batch_job.state, "value")
            else str(batch_job.state)
        )
        if state_str in TERMINAL_BATCH_STATES:
            break
        time.sleep(poll_interval)
        batch_job = client.batches.get(name=batch_job.name)

    total_elapsed = round(time.perf_counter() - start_time, 4)
    avg_exec_time = round(total_elapsed / max(len(requests), 1), 4)

    state_str = (
        batch_job.state.value
        if hasattr(batch_job.state, "value")
        else str(batch_job.state)
    )
    if state_str not in {"JOB_STATE_SUCCEEDED", "JOB_STATE_PARTIALLY_SUCCEEDED"}:
        raise RuntimeError(
            f"Gemini Batch Job '{batch_job.name}' falhou com estado: {state_str}"
        )

    responses: list[ReviewResponse] = []
    inlined_responses = (
        batch_job.dest.inlined_responses if batch_job.dest else None
    ) or []

    for item in inlined_responses:
        if getattr(item, "error", None) or not getattr(item, "response", None):
            err_msg = str(getattr(item, "error", "Erro no item do Batch API"))
            responses.append(
                ReviewResponse(
                    analysis={"erro": err_msg},
                    execution_time=avg_exec_time,
                )
            )
            continue

        resp = item.response
        raw_text = getattr(resp, "text", "") or ""
        usage = getattr(resp, "usage_metadata", None)
        in_tok = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
        out_tok = int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
        tot_tok = (
            int(getattr(usage, "total_token_count", 0) or (in_tok + out_tok))
            if usage
            else 0
        )

        responses.append(
            ReviewResponse(
                analysis=_parse_raw_output(raw_text),
                execution_time=avg_exec_time,
                input_tokens=in_tok,
                output_tokens=out_tok,
                total_tokens=tot_tok,
            )
        )

    logger.info(
        "Gemini Batch API finalizada em %.4fs (%d respostas obtidas).",
        total_elapsed,
        len(responses),
    )
    return responses
