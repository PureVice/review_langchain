import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from src.config import settings
from src.database.repository import ReviewRepository
from src.schemas import Review

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class SQLiteRepository(ReviewRepository):
    def __init__(self, db_path: str = settings.DATABASE_PATH):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        logger.info("Inicializando o banco de dados no caminho: %s", self.db_path)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reviews (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        review_text TEXT NOT NULL,
                        agent_response TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.commit()
        except Exception:
            logger.exception("Erro crítico ao inicializar o banco de dados.")
            raise

    def save(self, review_text: str, agent_response_str: str) -> None:
        logger.info("Salvando nova avaliação no banco de dados.")
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO reviews (review_text, agent_response) VALUES (?, ?)",
                    (review_text, agent_response_str),
                )
                conn.commit()
        except Exception:
            logger.exception("Erro ao salvar avaliação no banco de dados.")
            raise

    def get_all(self) -> list[Review]:
        logger.info("Buscando todas as avaliações salvas.")
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, review_text, agent_response, created_at FROM reviews ORDER BY id DESC"
                )
                rows = cursor.fetchall()
                return [self._format_entry(row) for row in rows]
        except Exception:
            logger.exception("Erro ao buscar a lista de avaliações no banco.")
            raise

    def get_by_id(self, review_id: int) -> Review | None:
        logger.info("Buscando avaliação com ID: %d", review_id)
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, review_text, agent_response, created_at FROM reviews WHERE id = ?",
                    (review_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return self._format_entry(row)
        except Exception:
            logger.exception("Erro ao buscar a avaliação ID %d no banco.", review_id)
            raise

    def _format_entry(self, row: sqlite3.Row) -> Review:
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

        raw_date = row["created_at"]
        try:
            created_at_dt = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError) as e:
            logger.warning(
                "Falha ao converter 'created_at' (%s) para o registro ID %s. Usando data atual. Erro: %s",
                raw_date,
                row["id"],
                e,
            )
            created_at_dt = datetime.now()

        return Review(
            id=row["id"],
            review_text=row["review_text"],
            agent_response=parsed_response,
            created_at=created_at_dt,
        )
