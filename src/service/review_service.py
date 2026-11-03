import csv
import hashlib
import io
import json
import logging
import random
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src.agent.agent import analyze_reviews_batch_api
from src.config import settings
from src.database.repository import ReviewRepository
from src.schemas import Review, ReviewRequest, ReviewResponse

logger = logging.getLogger(__name__)


def _collect_error_signals(exc: Exception) -> str:
    """Coleta nomes de classes e mensagens de toda a cadeia de exceções em letras minúsculas."""
    parts: list[str] = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        parts.append(type(current).__name__)
        parts.append(str(current))
        current = current.__cause__ or current.__context__
    return " | ".join(parts).lower()


def describe_processing_error(exc: Exception, is_batch: bool = True) -> str:
    """
    Traduz exceções ocorridas durante o envio/processamento de avaliações ou lotes
    em mensagens claras e detalhadas para o usuário.
    """
    signals = _collect_error_signals(exc)
    raw_detail = str(exc).strip() or type(exc).__name__

    if any(
        token in signals
        for token in (
            "402",
            "insufficient_balance",
            "insufficient balance",
            "insufficient_quota",
            "payment required",
            "billing",
        )
    ):
        base_msg = (
            "Saldo ou créditos insuficientes na conta da API de IA (Erro 402): "
            "verifique seu saldo ou faturamento no painel do provedor."
        )
    elif any(
        token in signals
        for token in (
            "429",
            "rate limit",
            "ratelimit",
            "rate_limit",
            "resource_exhausted",
            "resourceexhausted",
            "quota",
            "too many requests",
            "requests per minute",
            "tokens per minute",
        )
    ):
        base_msg = (
            "Limite da API excedido (Erro 429 / Rate Limit ou cota esgotada): "
            "o provedor de IA recusou novas requisições. Aguarde alguns instantes "
            "ou verifique o limite do seu plano."
        )
    elif any(
        token in signals
        for token in (
            "401",
            "403",
            "api_key",
            "api key",
            "apikey",
            "invalid_api_key",
            "authentication",
            "unauthorized",
            "unauthenticated",
            "permission_denied",
            "permissiondenied",
            "forbidden",
            "credentials",
        )
    ):
        base_msg = (
            "Falha de autenticação na API de IA (Erro 401/403): chave de API inválida, "
            "ausente ou sem permissão. Verifique suas chaves GOOGLE_API_KEY / DEEPSEEK_API_KEY."
        )
    elif any(
        token in signals
        for token in (
            "context_length",
            "maximum context",
            "token limit",
            "max_tokens",
            "too many tokens",
            "payload too large",
            "request too large",
            "413",
            "string too long",
        )
    ):
        base_msg = (
            "Limite de tokens/contexto da API excedido: o texto enviado ultrapassa "
            "o tamanho máximo suportado pelo modelo de IA."
        )
    elif isinstance(exc, TimeoutError) or any(
        token in signals
        for token in (
            "timeout",
            "timed out",
            "deadline_exceeded",
            "deadlineexceeded",
            "504",
            "gateway timeout",
        )
    ):
        base_msg = (
            "Tempo limite de resposta da API excedido (Timeout): o servidor de IA "
            "demorou muito para responder. Tente novamente."
        )
    elif isinstance(exc, ConnectionError) or any(
        token in signals
        for token in (
            "connection",
            "connecterror",
            "network",
            "dns",
            "unreachable",
            "502",
            "503",
            "500",
            "service unavailable",
            "bad gateway",
            "overloaded",
            "server error",
            "internal server error",
        )
    ):
        base_msg = (
            "Falha de conexão ou indisponibilidade no servidor da API de IA (Erro de rede / 5xx). "
            "Verifique sua conexão ou tente novamente em instantes."
        )
    elif any(
        token in signals
        for token in (
            "404",
            "model_not_found",
            "not_found",
            "not found",
            "does not exist",
        )
    ):
        base_msg = (
            "Modelo de IA não encontrado ou indisponível no provedor (Erro 404). "
            "Verifique a configuração do modelo."
        )
    elif any(
        token in signals
        for token in (
            "safety",
            "content_filter",
            "content filter",
            "blocked",
            "harm_category",
            "recitation",
        )
    ):
        base_msg = "O processamento foi bloqueado pelo filtro de segurança/conteúdo da API de IA."
    elif any(
        token in signals
        for token in (
            "sqlalchemy",
            "sqlite",
            "postgres",
            "psycopg",
            "operationalerror",
            "integrityerror",
            "database",
            "db error",
        )
    ):
        base_msg = "Erro no banco de dados ao salvar as avaliações processadas."
    else:
        context_label = "o lote de avaliações" if is_batch else "a avaliação"
        base_msg = f"Erro ao processar {context_label}: {raw_detail}"

    if is_batch:
        processed = getattr(exc, "processed_count", 0)
        total = getattr(exc, "total_count", 0)
        if processed and total:
            base_msg = (
                f"{base_msg} ({processed} de {total} avaliações do lote já haviam "
                f"sido salvas antes da interrupção.)"
            )

    return base_msg


class ReviewService:
    def __init__(
        self,
        repository: ReviewRepository,
        agent_function: Callable[[ReviewRequest], ReviewResponse],
        batch_agent_function: (
            Callable[[list[ReviewRequest]], list[ReviewResponse]] | None
        ) = None,
        batch_api_threshold: int | None = None,
        max_concurrency: int | None = None,
        max_retries: int | None = None,
        retry_base_delay: float | None = None,
        checkpoint_path: Path | None = None,
    ):
        """
        Recebe o repositório, funções do agente e configurações de pipeline/lote via injeção de dependência.
        """
        self.repository = repository
        self.agent_function = agent_function
        self.batch_agent_function = batch_agent_function or analyze_reviews_batch_api
        self.batch_api_threshold = (
            batch_api_threshold
            if batch_api_threshold is not None
            else settings.BATCH_API_THRESHOLD
        )
        self.max_concurrency = (
            max_concurrency if max_concurrency is not None else settings.MAX_CONCURRENCY
        )
        self.max_retries = (
            max_retries if max_retries is not None else settings.MAX_RETRIES
        )
        self.retry_base_delay = (
            retry_base_delay
            if retry_base_delay is not None
            else settings.RETRY_BASE_DELAY
        )
        self.checkpoint_path = checkpoint_path
        self._persistence_lock = threading.Lock()

    def _persist_review(self, review_text: str, agent_response: ReviewResponse) -> None:
        """Formata e persiste imediatamente o resultado da avaliação e suas métricas no repositório."""
        content = agent_response.analysis
        if isinstance(content, (dict | list)):
            response_str = json.dumps(content, ensure_ascii=False)
        else:
            response_str = str(content)

        with self._persistence_lock:
            self.repository.save(
                review_text=review_text,
                agent_response_str=response_str,
                execution_time=agent_response.execution_time,
                input_tokens=agent_response.input_tokens,
                output_tokens=agent_response.output_tokens,
                total_tokens=agent_response.total_tokens,
            )

    def _invoke_agent_with_retry(self, request: ReviewRequest) -> ReviewResponse:
        """Executa a chamada ao agente com retry, backoff exponencial e jitter."""
        last_exception: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return self.agent_function(request)
            except Exception as exc:
                last_exception = exc
                if attempt >= self.max_retries:
                    break
                backoff = self.retry_base_delay * (2**attempt)
                jitter = random.uniform(0, max(self.retry_base_delay, 0.001))
                sleep_seconds = backoff + jitter
                logger.warning(
                    "Tentativa %d/%d falhou ao analisar review. Novo retry em %.3fs. Erro: %s",
                    attempt + 1,
                    self.max_retries + 1,
                    sleep_seconds,
                    exc,
                )
                time.sleep(sleep_seconds)
        assert last_exception is not None
        raise last_exception

    def process_and_save_review(self, request: ReviewRequest) -> None:
        """
        Coordena a execução da análise via agente LLM e persiste o resultado no banco.
        """
        logger.info("Service: Iniciando processamento da avaliação.")
        agent_response = self.agent_function(request)
        self._persist_review(request.review_text, agent_response)
        logger.info("Service: Avaliação processada e salva com sucesso.")

    def extract_reviews_from_csv(self, file_content: str) -> list[str]:
        """Extrai os textos do campo 'content' a partir de um conteúdo CSV."""
        stream = io.StringIO(file_content.strip())
        sample = stream.read(2048)
        stream.seek(0)

        delimiter = ","
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;")
            delimiter = dialect.delimiter
        except csv.Error:
            pass

        try:
            reader = csv.DictReader(stream, delimiter=delimiter)
            if not reader.fieldnames:
                raise ValueError("O arquivo CSV está vazio ou sem cabeçalho.")

            content_col = next(
                (
                    col
                    for col in reader.fieldnames
                    if col and col.strip().lower() == "content"
                ),
                None,
            )
            if not content_col:
                raise ValueError(
                    "O arquivo CSV deve conter uma coluna chamada 'content'."
                )

            reviews: list[str] = []
            for row in reader:
                val = row.get(content_col)
                if val and str(val).strip():
                    reviews.append(str(val).strip())
        except csv.Error as e:
            raise ValueError(f"Arquivo CSV malformado ou inválido: {e}") from e

        return reviews

    def extract_reviews_from_json(self, file_content: str) -> list[str]:
        """Extrai os textos do campo 'content' a partir de um conteúdo JSON."""
        try:
            data = json.loads(file_content)
        except json.JSONDecodeError as e:
            raise ValueError("Arquivo JSON inválido.") from e

        reviews: list[str] = []

        if isinstance(data, dict):
            if "content" not in data:
                raise ValueError("O arquivo JSON deve conter o campo 'content'.")
            content_val = data["content"]
            if isinstance(content_val, str):
                if content_val.strip():
                    reviews.append(content_val.strip())
            elif isinstance(content_val, list):
                for item in content_val:
                    if isinstance(item, str) and item.strip():
                        reviews.append(item.strip())
                    elif (
                        isinstance(item, dict) and str(item.get("content", "")).strip()
                    ):
                        reviews.append(str(item["content"]).strip())
            else:
                raise ValueError(
                    "O campo 'content' no JSON deve ser um texto ou uma lista de avaliações."
                )
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if "content" not in item:
                        raise ValueError(
                            "Cada objeto na lista JSON deve conter o campo 'content'."
                        )
                    val = item.get("content")
                    if val and str(val).strip():
                        reviews.append(str(val).strip())
                elif isinstance(item, str) and item.strip():
                    reviews.append(item.strip())
        else:
            raise ValueError("Estrutura JSON não suportada.")

        return reviews

    def _review_hash(self, index: int, text: str) -> str:
        return hashlib.sha256(f"{index}:{text}".encode()).hexdigest()

    def _load_checkpoint(self) -> set[str]:
        if not self.checkpoint_path or not self.checkpoint_path.exists():
            return set()
        try:
            data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            return set(data.get("completed_hashes", []))
        except Exception:
            return set()

    def _update_checkpoint(self, completed_hashes: set[str]) -> None:
        if not self.checkpoint_path:
            return
        try:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            self.checkpoint_path.write_text(
                json.dumps({"completed_hashes": sorted(completed_hashes)}),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Não foi possível atualizar arquivo de checkpoint: %s", e)

    def _clear_checkpoint(self) -> None:
        if self.checkpoint_path and self.checkpoint_path.exists():
            try:
                self.checkpoint_path.unlink()
            except Exception as e:
                logger.warning("Não foi possível remover arquivo de checkpoint: %s", e)

    def _process_concurrent_pipeline(self, requests: list[ReviewRequest]) -> int:
        """
        Pipeline com concorrência fixa, retry com backoff exponencial + jitter,
        e checkpointing com persistência imediata no banco de dados.
        """
        logger.info(
            "Service: Executando pipeline concorrente (max_concurrency=%d) para %d avaliações.",
            self.max_concurrency,
            len(requests),
        )
        completed_hashes = self._load_checkpoint()
        processed_count = 0

        pending: list[tuple[str, ReviewRequest]] = []
        for idx, req in enumerate(requests):
            item_hash = self._review_hash(idx, req.review_text)
            if item_hash in completed_hashes:
                continue
            pending.append((item_hash, req))

        if not pending:
            self._clear_checkpoint()
            return 0

        workers = max(1, min(self.max_concurrency, len(pending)))
        executor = ThreadPoolExecutor(max_workers=workers)
        try:
            future_to_item = {
                executor.submit(self._invoke_agent_with_retry, req): (item_hash, req)
                for item_hash, req in pending
            }
            for future in as_completed(future_to_item):
                item_hash, req = future_to_item[future]
                try:
                    agent_response = future.result()
                    if workers > 1 and agent_response.execution_time:
                        effective_time = round(
                            agent_response.execution_time / workers, 4
                        )
                        agent_response = agent_response.model_copy(
                            update={"execution_time": effective_time}
                        )
                    # Checkpointing de persistência imediata assim que cada worker conclui
                    self._persist_review(req.review_text, agent_response)
                    with self._persistence_lock:
                        completed_hashes.add(item_hash)
                        self._update_checkpoint(completed_hashes)
                    processed_count += 1
                except Exception as exc:
                    logger.exception(
                        "Falha definitiva ao processar avaliação no pipeline após retries."
                    )
                    exc.processed_count = len(completed_hashes)  # type: ignore[attr-defined]
                    exc.total_count = len(requests)  # type: ignore[attr-defined]
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        self._clear_checkpoint()
        return processed_count

    def _process_batch_api(self, requests: list[ReviewRequest]) -> int:
        """
        Estratégia para > 500 avaliações:
        Processamento em lote via Gemini Batch API com persistência imediata dos resultados.
        """
        logger.info(
            "Service: Acionando estratégia Gemini Batch API para %d avaliações (> %d).",
            len(requests),
            self.batch_api_threshold,
        )
        responses = self.batch_agent_function(requests)
        processed_count = 0
        for req, resp in zip(requests, responses, strict=False):
            self._persist_review(req.review_text, resp)
            processed_count += 1
        return processed_count

    def process_reviews_batch(self, review_texts: list[str]) -> int:
        """
        Executa o lote de avaliações utilizando o pipeline concorrente com
        concorrência fixa, retry exponencial com jitter e persistência imediata.
        """
        requests = [
            ReviewRequest(review_text=t.strip()) for t in review_texts if t.strip()
        ]
        if not requests:
            return 0

        return self._process_concurrent_pipeline(requests)

    def process_file_upload(self, filename: str, raw_bytes: bytes) -> int:
        """
        Lê um arquivo CSV ou JSON, extrai as avaliações do campo 'content' e processa o lote
        sem limite de tamanho de dataset.
        Retorna a quantidade de avaliações processadas.
        """
        lower_name = (filename or "").lower()
        if not lower_name.endswith((".csv", ".json")):
            raise ValueError(
                "Formato de arquivo não suportado. Envie um arquivo .csv ou .json."
            )

        if not raw_bytes or not raw_bytes.strip():
            raise ValueError("O arquivo enviado está vazio.")

        try:
            text_content = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise ValueError(
                "Não foi possível ler o arquivo: codificação de texto inválida. "
                "Salve o arquivo em formato UTF-8."
            ) from e

        if lower_name.endswith(".csv"):
            reviews = self.extract_reviews_from_csv(text_content)
        else:
            reviews = self.extract_reviews_from_json(text_content)

        if not reviews:
            raise ValueError(
                "Nenhuma avaliação válida foi encontrada no campo 'content' do arquivo enviado."
            )

        processed_count = self.process_reviews_batch(reviews)
        logger.info(
            "Service: Upload processado com sucesso (%d avaliações salvas).",
            processed_count,
        )
        return processed_count

    def export_reviews_to_csv(self) -> str:
        """Exporta todas as avaliações, análises e métricas (tempo e tokens) em formato CSV."""
        reviews = self.get_all_reviews()
        output = io.StringIO()
        fieldnames = [
            "id",
            "content",
            "dominios",
            "rd_score",
            "rd_justificativa",
            "ob_score",
            "ob_justificativa",
            "cl_score",
            "cl_justificativa",
            "ut_score",
            "ut_justificativa",
            "execution_time",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "agent_response",
            "created_at",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for entry in reviews:
            resp = entry.agent_response
            dominios_str = ""
            rd_score = rd_just = ob_score = ob_just = ""
            cl_score = cl_just = ut_score = ut_just = ""

            if isinstance(resp, dict):
                raw_json = json.dumps(resp, ensure_ascii=False)
                dominios = resp.get("metadados", {}).get("dominios_detectados", [])
                if isinstance(dominios, list):
                    dominios_str = ", ".join(
                        str(d.get("dominio", ""))
                        for d in dominios
                        if isinstance(d, dict) and d.get("dominio")
                    )

                dim = resp.get("analise_dimensional", {})
                if isinstance(dim, dict):
                    rd = dim.get("RD", {})
                    ob = dim.get("OB", {})
                    cl = dim.get("CL", {})
                    ut = dim.get("UT", {})
                    rd_score = rd.get("score", "")
                    rd_just = rd.get("justificativa", "")
                    ob_score = ob.get("score", "")
                    ob_just = ob.get("justificativa", "")
                    cl_score = cl.get("score", "")
                    cl_just = cl.get("justificativa", "")
                    ut_score = ut.get("score", "")
                    ut_just = ut.get("justificativa", "")
            elif isinstance(resp, list):
                raw_json = json.dumps(resp, ensure_ascii=False)
            else:
                raw_json = str(resp)

            created_str = (
                entry.created_at.strftime("%Y-%m-%d %H:%M:%S")
                if entry.created_at
                else ""
            )

            writer.writerow(
                {
                    "id": entry.id,
                    "content": entry.review_text,
                    "dominios": dominios_str,
                    "rd_score": rd_score,
                    "rd_justificativa": rd_just,
                    "ob_score": ob_score,
                    "ob_justificativa": ob_just,
                    "cl_score": cl_score,
                    "cl_justificativa": cl_just,
                    "ut_score": ut_score,
                    "ut_justificativa": ut_just,
                    "execution_time": entry.execution_time,
                    "input_tokens": entry.input_tokens,
                    "output_tokens": entry.output_tokens,
                    "total_tokens": entry.total_tokens,
                    "agent_response": raw_json,
                    "created_at": created_str,
                }
            )

        return output.getvalue()

    def get_all_reviews(self) -> list[Review]:
        """Recupera todas as análises de avaliações salvas."""
        return self.repository.get_all()

    def get_review_by_id(self, review_id: int) -> Review | None:
        """Recupera uma análise específica pelo ID."""
        return self.repository.get_by_id(review_id)
