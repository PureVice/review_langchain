import json
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.database.models import Base, ReviewModel
from src.database.repository import ReviewRepository
from src.schemas import Review

logger = logging.getLogger(__name__)


class SQLAlchemyRepository(ReviewRepository):
    def __init__(self, db_url: str = None):
        self.db_url = db_url or settings.DATABASE_URL

        # O SQLAlchemy requer a especificação do driver na URL de conexão
        if self.db_url.startswith("postgresql://"):
            self.db_url = self.db_url.replace(
                "postgresql://", "postgresql+psycopg2://", 1
            )

        self.engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self._init_db()

    def _init_db(self) -> None:
        """Cria as tabelas no banco de dados caso não existam e garante migração de colunas."""
        logger.info("Inicializando o banco de dados via SQLAlchemy.")
        try:
            Base.metadata.create_all(bind=self.engine)
            self._ensure_columns()
            logger.info("Tabelas verificadas/criadas com sucesso no SQLAlchemy.")
        except Exception:
            logger.exception(
                "Erro crítico ao inicializar o banco de dados com SQLAlchemy."
            )
            raise

    def _ensure_columns(self) -> None:
        """Adiciona novas colunas de métricas caso a tabela já exista de versões anteriores."""
        try:
            inspector = inspect(self.engine)
            if not inspector.has_table("reviews"):
                return
            existing_cols = {col["name"] for col in inspector.get_columns("reviews")}
            new_columns = {
                "execution_time": "FLOAT DEFAULT 0.0",
                "input_tokens": "INTEGER DEFAULT 0",
                "output_tokens": "INTEGER DEFAULT 0",
                "total_tokens": "INTEGER DEFAULT 0",
            }
            with self.engine.begin() as conn:
                for col_name, col_type in new_columns.items():
                    if col_name not in existing_cols:
                        conn.execute(
                            text(
                                f"ALTER TABLE reviews ADD COLUMN {col_name} {col_type}"
                            )
                        )
        except Exception as e:
            logger.warning("Aviso ao verificar migração de colunas: %s", e)

    def save(
        self,
        review_text: str,
        agent_response_str: str,
        execution_time: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        """Insere um novo registro no banco via ORM."""
        logger.info("Salvando nova avaliação com SQLAlchemy.")
        session = self.SessionLocal()
        try:
            new_review = ReviewModel(
                review_text=review_text,
                agent_response=agent_response_str,
                execution_time=execution_time,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            )
            session.add(new_review)
            session.commit()
            logger.info("Avaliação salva com sucesso.")
        except Exception:
            session.rollback()
            logger.exception("Erro ao salvar avaliação com SQLAlchemy.")
            raise
        finally:
            session.close()

    def get_all(self) -> list[Review]:
        """Busca todas as avaliações no banco."""
        logger.info("Buscando todas as avaliações com SQLAlchemy.")
        session = self.SessionLocal()
        try:
            rows = session.query(ReviewModel).order_by(ReviewModel.id.desc()).all()
            return [self._format_entry(row) for row in rows]
        except Exception:
            logger.exception("Erro ao buscar a lista de avaliações com SQLAlchemy.")
            raise
        finally:
            session.close()

    def get_by_id(self, review_id: int) -> Review | None:
        """Busca uma avaliação específica pelo ID."""
        logger.info("Buscando avaliação com ID: %d via SQLAlchemy", review_id)
        session = self.SessionLocal()
        try:
            row = session.query(ReviewModel).filter(ReviewModel.id == review_id).first()
            if not row:
                return None
            return self._format_entry(row)
        except Exception:
            logger.exception(
                "Erro ao buscar a avaliação ID %d com SQLAlchemy.", review_id
            )
            raise
        finally:
            session.close()

    def _format_entry(self, row: ReviewModel) -> Review:
        """Converte o objeto do SQLAlchemy para o modelo Pydantic da aplicação."""
        raw_response = row.agent_response
        try:
            parsed_response = json.loads(raw_response)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(
                "Falha ao decodificar JSON da coluna 'agent_response' (ID: %s). Mantendo texto original. Erro: %s",
                row.id,
                e,
            )
            parsed_response = raw_response

        return Review(
            id=row.id,
            review_text=row.review_text,
            agent_response=parsed_response,
            execution_time=float(row.execution_time or 0.0),
            input_tokens=int(row.input_tokens or 0),
            output_tokens=int(row.output_tokens or 0),
            total_tokens=int(row.total_tokens or 0),
            created_at=row.created_at,
        )
