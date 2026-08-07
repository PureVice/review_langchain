from abc import ABC, abstractmethod

from src.schemas import Review


class ReviewRepository(ABC):
    @abstractmethod
    def save(self, review_text: str, agent_response_str: str) -> None:
        pass

    @abstractmethod
    def get_all(self) -> list[Review]:
        pass

    @abstractmethod
    def get_by_id(self, review_id: int) -> Review | None:
        pass
