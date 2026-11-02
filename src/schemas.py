from datetime import datetime
from typing import Any, Literal

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


class DominioDetectado(BaseModel):
    dominio: str = Field(
        ...,
        description="Domínio permitido: produto, logistica, atendimento, suporte, pagamento, plataforma ou outro",
    )
    confianca: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Nível de confiança na identificação do domínio",
    )


class EvidenciaEstruturada(BaseModel):
    trecho: str = Field(
        ..., description="Trecho exato extraído do texto sem aspas duplas internas"
    )
    dimensoes: list[str] = Field(
        default_factory=list,
        description="Dimensões associadas à evidência (RD, OB, CL, UT)",
    )
    polaridade_relato: Literal["positivo", "neutro", "negativo"] = Field(
        ..., description="Polaridade observada no trecho"
    )


class DimensaoAvaliacao(BaseModel):
    justificativa: str = Field(
        ...,
        description="Justificativa concisa (máximo 2 frases) formulada antes do score",
    )
    avaliabilidade: float = Field(
        ..., ge=0.0, le=1.0, description="Grau de suficiência de dados para avaliação"
    )
    confianca: float = Field(
        ..., ge=0.0, le=1.0, description="Grau de certeza na nota atribuída"
    )
    score: int = Field(
        ...,
        ge=1,
        le=5,
        description="Score inteiro estrito de 1 a 5 conforme a rubrica dimensional",
    )


class AnaliseDimensional(BaseModel):
    RD: DimensaoAvaliacao
    OB: DimensaoAvaliacao
    CL: DimensaoAvaliacao
    UT: DimensaoAvaliacao


class MetadadosAgente(BaseModel):
    dominios_detectados: list[DominioDetectado] = Field(default_factory=list)


class ValidacoesAgente(BaseModel):
    anti_length_bias_applied: bool = True
    absence_not_penalized_as_contradiction: bool = True
    independence_of_sentiment_maintained: bool = True
    halo_effect_mitigated: bool = True


class AgenteAnalysisOutput(BaseModel):
    metadados: MetadadosAgente
    evidencias_estruturadas: list[EvidenciaEstruturada] = Field(default_factory=list)
    analise_dimensional: AnaliseDimensional
    validacoes: ValidacoesAgente = Field(default_factory=ValidacoesAgente)


class Review(BaseModel):
    id: int
    review_text: str
    agent_response: dict[str, Any] | list[Any] | str
    execution_time: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    created_at: datetime
