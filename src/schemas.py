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
    execution_time: float = Field(
        default=0.0, description="Tempo de execução da chamada LLM em segundos"
    )
    input_tokens: int = Field(
        default=0, description="Quantidade de tokens de entrada (prompt)"
    )
    output_tokens: int = Field(
        default=0, description="Quantidade de tokens de saída (completion)"
    )
    total_tokens: int = Field(
        default=0, description="Total de tokens consumidos na chamada"
    )


class Review(BaseModel):
    id: int
    review_text: str
    agent_response: dict[str, Any] | list[Any] | str
    execution_time: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    created_at: datetime
