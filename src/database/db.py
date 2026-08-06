import json
import sqlite3
from datetime import datetime
from pathlib import Path

from src.config import settings

# Salva o banco na pasta 'data/' na raiz do projeto (fora do codigo-fonte)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = settings.DATABASE_PATH


def get_connection():
    """Retorna conexão com o banco SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Cria a tabela de reviews caso não exista."""
    with get_connection() as conn:
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


def save_review(review_text: str, agent_response: str):
    """Insere um novo registro no banco."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO reviews (review_text, agent_response) VALUES (?, ?)",
            (review_text, agent_response),
        )
        conn.commit()


def _format_entry(row):
    """Auxiliar para converter as linhas do banco no formato esperado pelo HTML."""
    raw_response = row["agent_response"]

    try:
        parsed_response = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError):
        parsed_response = raw_response

    raw_date = row["created_at"]
    try:
        created_at_dt = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        created_at_dt = datetime.now()

    return {
        "id": row["id"],
        "review_text": row["review_text"],
        "agent_response": parsed_response,
        "created_at": created_at_dt,
    }


def get_all_reviews():
    """Retorna todas as avaliações formatadas."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, review_text, agent_response, created_at FROM reviews ORDER BY id DESC"
        )
        rows = cursor.fetchall()
        return [_format_entry(row) for row in rows]


def get_review_by_id(review_id: int):
    """Retorna uma única avaliação por ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, review_text, agent_response, created_at FROM reviews WHERE id = ?",
            (review_id,),
        )
        row = cursor.fetchone()
        return _format_entry(row) if row else None
