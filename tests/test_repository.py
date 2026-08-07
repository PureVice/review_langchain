from unittest.mock import MagicMock, patch

import pytest

from src.database.sqlalchemy_repository import SQLAlchemyRepository


@pytest.fixture
def repo():
    """Cria um repositório usando banco em memória (SQLite) exclusivo para testes."""
    return SQLAlchemyRepository(db_url="sqlite:///:memory:")


def test_init_db_success(repo):
    """Verifica se as tabelas são criadas corretamente na inicialização."""
    assert repo.get_all() == []


def test_save_success(repo):
    """Verifica se o SQLAlchemy insere e commita corretamente."""
    repo.save("Produto excelente", '{"score": 10}')
    results = repo.get_all()

    assert len(results) == 1
    assert results[0].review_text == "Produto excelente"


def test_get_all_success(repo):
    """Verifica se o SELECT traz os dados formatados e ordenados de forma decrescente."""
    repo.save("Bom", '{"status": "ok"}')
    repo.save("Ruim", '{"status": "erro"}')

    results = repo.get_all()
    assert len(results) == 2
    assert results[0].review_text == "Ruim"
    assert results[1].review_text == "Bom"


def test_get_by_id_found(repo):
    """Verifica a busca de um registro específico."""
    repo.save("Neutro", "Resposta pura")
    saved = repo.get_all()[0]

    result = repo.get_by_id(saved.id)
    assert result.id == saved.id
    assert result.agent_response == "Resposta pura"


def test_get_by_id_not_found(repo):
    """Verifica o comportamento quando o ID não existe."""
    result = repo.get_by_id(99)
    assert result is None


def test_format_entry_json_fallback(repo):
    """Testa o fallback para string quando o JSON é inválido."""
    repo.save("Teste JSON falho", "Isto não é um JSON")
    result = repo.get_all()[0]
    assert result.agent_response == "Isto não é um JSON"


def test_repository_exceptions():
    """Força erros no SQLAlchemy para garantir que as exceções sejam propagadas."""
    repo = SQLAlchemyRepository(db_url="sqlite:///:memory:")

    with patch.object(repo, "SessionLocal") as mock_sessionmaker:
        mock_session = MagicMock()
        mock_session.commit.side_effect = Exception("DB Error")
        mock_session.query.side_effect = Exception("DB Error")
        mock_sessionmaker.return_value = mock_session

        with pytest.raises(Exception, match="DB Error"):
            repo.save("Teste", "Resposta")

        with pytest.raises(Exception, match="DB Error"):
            repo.get_all()

        with pytest.raises(Exception, match="DB Error"):
            repo.get_by_id(1)


@patch("src.database.sqlalchemy_repository.Base.metadata.create_all")
def test_init_db_exception(mock_create_all):
    """Força erro na inicialização do banco."""
    mock_create_all.side_effect = Exception("Init Error")
    with pytest.raises(Exception, match="Init Error"):
        SQLAlchemyRepository(db_url="sqlite:///:memory:")
