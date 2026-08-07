import json
import logging
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

from src.config import settings
from src.database.repository import ReviewRepository
from src.schemas import Review

logger = logging.getLogger(__name__)


class PostgresRepository(ReviewRepository):
    def __init__(self, db_url: str = None):
        self.db_url = db_url or settings.DATABASE_URL
        self._init_db()

    def get_connection(self):
        """Retorna uma conexão com o PostgreSQL utilizando RealDictCursor para facilitar o mapeamento."""
        return psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)

    def _init_db(self) -> None:
        """Cria a tabela de reviews no PostgreSQL caso não exista."""
        logger.info("Inicializando o banco de dados PostgreSQL.")
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS reviews (
                            id SERIAL PRIMARY KEY,
                            review_text TEXT NOT NULL,
                            agent_response TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                    conn.commit()
            logger.info("Tabela 'reviews' verificada/criada com sucesso no Postgres.")
        except Exception:
            logger.exception("Erro crítico ao inicializar o banco de dados PostgreSQL.")
            raise

    def save(self, review_text: str, agent_response_str: str) -> None:
        """Insere um novo registro no PostgreSQL."""
        logger.info("Salvando nova avaliação no PostgreSQL.")
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO reviews (review_text, agent_response) VALUES (%s, %s)",
                        (review_text, agent_response_str),
                    )
                    conn.commit()
            logger.info("Avaliação salva no Postgres com sucesso.")
        except Exception:
            logger.exception("Erro ao salvar avaliação no PostgreSQL.")
            raise

    def get_all(self) -> list[Review]:
        """Busca todas as avaliações ordenadas por ID decrescente."""
        logger.info("Buscando todas as avaliações no PostgreSQL.")
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT id, review_text, agent_response, created_at FROM reviews ORDER BY id DESC"
                    )
                    rows = cursor.fetchall()
                    return [self._format_entry(row) for row in rows]
        except Exception:
            logger.exception("Erro ao buscar a lista de avaliações no PostgreSQL.")
            raise

    def get_by_id(self, review_id: int) -> Review | None:
        """Busca uma avaliação específica pelo ID no PostgreSQL."""
        logger.info("Buscando avaliação com ID: %d no PostgreSQL", review_id)
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT id, review_text, agent_response, created_at FROM reviews WHERE id = %s",
                        (review_id,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        return None
                    return self._format_entry(row)
        except Exception:
            logger.exception(
                "Erro ao buscar a avaliação ID %d no PostgreSQL.", review_id
            )
            raise

    def _format_entry(self, row: dict) -> Review:
        """Auxiliar para converter o dicionário do Postgres no modelo Pydantic."""
        raw_response = row["agent_response"]
        try:
            parsed_response = json.loads(raw_response)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "Falha ao decodificar JSON da coluna 'agent_response' (ID: %s). Mantendo texto original. Erro: %s",
                row["id"],
                e,
            )
            parsed_response = raw_response

        created_at_dt = row["created_at"]
        if isinstance(created_at_dt, str):
            try:
                created_at_dt = datetime.strptime(created_at_dt, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                created_at_dt = datetime.now()

        return Review(
            id=row["id"],
            review_text=row["review_text"],
            agent_response=parsed_response,
            created_at=created_at_dt,
        )
