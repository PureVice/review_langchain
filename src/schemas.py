from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    review_text: str = Field(
        ..., min_length=1, description="Texto da avaliação a ser analisada pelo agente"
    )


class ReviewResponse(BaseModel):
    analysis: dict[str, Any] | list[Any] | str = Field(
        ..., description="Resultado do processamento e análise do agente LLM"
    )


class Review(BaseModel):
    id: int
    review_text: str
    agent_response: dict[str, Any] | list[Any] | str
    created_at: datetime
