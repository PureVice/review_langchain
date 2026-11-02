from abc import ABC, abstractmethod

from src.schemas import Review


class ReviewRepository(ABC):
    @abstractmethod
    def save(
        self,
        review_text: str,
        agent_response_str: str,
        execution_time: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        pass

    @abstractmethod
    def get_all(self) -> list[Review]:
        pass

    @abstractmethod
    def get_by_id(self, review_id: int) -> Review | None:
        pass
