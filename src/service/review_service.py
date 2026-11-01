import csv
import io
import json
import logging
from collections.abc import Callable

from src.database.repository import ReviewRepository
from src.schemas import Review, ReviewRequest, ReviewResponse

logger = logging.getLogger(__name__)


class ReviewService:
    def __init__(
        self,
        repository: ReviewRepository,
        agent_function: Callable[[ReviewRequest], ReviewResponse],
    ):
        """
        Recebe o repositório e a função do agente via injeção de dependência.
        """
        self.repository = repository
        self.agent_function = agent_function

    def process_and_save_review(self, request: ReviewRequest) -> None:
        """
        Coordena a execução da análise via agente LLM e persiste o resultado no banco.
        """
        logger.info("Service: Iniciando processamento da avaliação.")

        # 1. Chama o agente LLM para processar a avaliação
        agent_response = self.agent_function(request)

        # 2. Prepara e formata os dados para o banco
        content = agent_response.analysis
        if isinstance(content, (dict | list)):
            response_str = json.dumps(content, ensure_ascii=False)
        else:
            response_str = str(content)

        # 3. Salva a avaliação formatada no repositório
        self.repository.save(
            review_text=request.review_text, agent_response_str=response_str
        )
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
            raise ValueError("O arquivo CSV deve conter uma coluna chamada 'content'.")

        reviews: list[str] = []
        for row in reader:
            val = row.get(content_col)
            if val and str(val).strip():
                reviews.append(str(val).strip())

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

    def process_file_upload(self, filename: str, raw_bytes: bytes) -> int:
        """
        Lê um arquivo CSV ou JSON, extrai as avaliações do campo 'content' e processa cada uma.
        Retorna a quantidade de avaliações processadas.
        """
        lower_name = (filename or "").lower()
        text_content = raw_bytes.decode("utf-8-sig")

        if lower_name.endswith(".csv"):
            reviews = self.extract_reviews_from_csv(text_content)
        elif lower_name.endswith(".json"):
            reviews = self.extract_reviews_from_json(text_content)
        else:
            raise ValueError(
                "Formato de arquivo não suportado. Envie um arquivo .csv ou .json."
            )

        processed_count = 0
        for review_text in reviews:
            req = ReviewRequest(review_text=review_text)
            self.process_and_save_review(req)
            processed_count += 1

        logger.info(
            "Service: Upload processado com sucesso (%d avaliações salvas).",
            processed_count,
        )
        return processed_count

    def export_reviews_to_csv(self) -> str:
        """Exporta todas as avaliações e suas respectivas análises em formato CSV."""
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
