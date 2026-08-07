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

    def get_all_reviews(self) -> list[Review]:
        """Recupera todas as análises de avaliações salvas."""
        return self.repository.get_all()

    def get_review_by_id(self, review_id: int) -> Review | None:
        """Recupera uma análise específica pelo ID."""
        return self.repository.get_by_id(review_id)
