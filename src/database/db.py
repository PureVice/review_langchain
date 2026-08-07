import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)

# Salva o banco na pasta 'data/' na raiz do projeto (fora do codigo-fonte)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = settings.DATABASE_PATH


def get_connection():
    """Retorna conexão com o banco SQLite."""
    return sqlite3.connect(DB_PATH)


def init_db():
    """Cria a tabela de reviews caso não exista."""
    logger.info("Inicializando o banco de dados no caminho: %s", DB_PATH)
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
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
        logger.info("Tabela 'reviews' verificada/criada com sucesso.")
    except Exception:
        logger.exception("Erro crítico ao inicializar o banco de dados.")
        raise


def save_review(review_text: str, agent_response: str):
    """Insere um novo registro no banco."""
    logger.info("Salvando nova avaliação no banco de dados.")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO reviews (review_text, agent_response) VALUES (?, ?)",
                (review_text, agent_response),
            )
            conn.commit()
        logger.info("Avaliação salva no banco com sucesso.")
    except Exception:
        logger.exception("Erro ao salvar avaliação no banco de dados.")
        raise


def _format_entry(row):
    """Auxiliar para converter as linhas do banco no formato esperado pelo HTML."""
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

    return {
        "id": row["id"],
        "review_text": row["review_text"],
        "agent_response": parsed_response,
        "created_at": created_at_dt,
    }


def get_all_reviews():
    """Retorna todas as avaliações formatadas."""
    logger.info("Buscando todas as avaliações salvas.")
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, review_text, agent_response, created_at FROM reviews ORDER BY id DESC"
            )
            rows = cursor.fetchall()
            logger.info("Registros recuperados do banco: %d", len(rows))
            return [_format_entry(row) for row in rows]
    except Exception:
        logger.exception("Erro ao buscar a lista de avaliações no banco.")
        raise


def get_review_by_id(review_id: int):
    """Retorna uma única avaliação por ID."""
    logger.info("Buscando avaliação com ID: %d", review_id)
    try:
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, review_text, agent_response, created_at FROM reviews WHERE id = ?",
                (review_id,),
            )
            row = cursor.fetchone()
            if not row:
                logger.warning("Nenhuma avaliação encontrada para o ID %d.", review_id)
                return None
            return _format_entry(row)
    except Exception:
        logger.exception("Erro ao buscar a avaliação ID %d no banco.", review_id)
        raise
