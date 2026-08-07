import json
import logging

from sqlalchemy import create_engine
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
        """Cria as tabelas no banco de dados caso não existam."""
        logger.info("Inicializando o banco de dados via SQLAlchemy.")
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Tabelas verificadas/criadas com sucesso no SQLAlchemy.")
        except Exception:
            logger.exception(
                "Erro crítico ao inicializar o banco de dados com SQLAlchemy."
            )
            raise

    def save(self, review_text: str, agent_response_str: str) -> None:
        """Insere um novo registro no banco via ORM."""
        logger.info("Salvando nova avaliação com SQLAlchemy.")
        session = self.SessionLocal()
        try:
            new_review = ReviewModel(
                review_text=review_text, agent_response=agent_response_str
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
            created_at=row.created_at,
        )
