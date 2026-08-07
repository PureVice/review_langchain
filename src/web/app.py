import logging
import sys
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for
from pydantic import ValidationError

from src.config import settings, setup_logging

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# Importando o Repository, o Service e o Agente
from src.agent.agent import analyze_review
from src.database.repository import ReviewRepository
from src.schemas import ReviewRequest
from src.service.review_service import ReviewService

setup_logging()
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
app = Flask(__name__, template_folder=str(TEMPLATES_DIR))

# Injeção de dependências: Instanciamos o Repositório e passamos para o Serviço
review_repository = ReviewRepository()
review_service = ReviewService(
    repository=review_repository, agent_function=analyze_review
)


@app.route("/", methods=["GET"])
def index():
    """Exibe o histórico completo de análises."""
    logger.info("Requisição GET recebida no endpoint '/'.")
    entries = review_service.get_all_reviews()
    return render_template("index.html", entries=entries, single=False)


@app.route("/review/<int:review_id>", methods=["GET"])
def show_review(review_id):
    """Exibe apenas uma análise específica."""
    logger.info("Requisição GET recebida para a avaliação ID: %d", review_id)
    entry = review_service.get_review_by_id(review_id)

    if not entry:
        logger.warning(
            "Avaliação ID %d não foi localizada. Redirecionando para '/'.", review_id
        )
        return redirect(url_for("index"))

    return render_template("index.html", entries=[entry], single=True)


@app.route("/analyze", methods=["POST"])
def analyze():
    """Recebe o texto enviado pelo formulário, valida via Pydantic e aciona o Service."""
    logger.info("Requisição POST recebida no endpoint '/analyze'.")
    raw_text = request.form.get("review_text", "").strip()

    try:
        # Controller se encarrega estritamente da validação do input HTTP
        review_request = ReviewRequest(review_text=raw_text)

        # O Service orquestra a chamada de LLM e o Banco
        review_service.process_and_save_review(review_request)

    except ValidationError as ve:
        logger.warning("Falha na validação dos dados de entrada (Pydantic): %s", ve)
    except Exception:
        logger.exception("Erro ao processar e armazenar a avaliação enviada.")

    return redirect(url_for("index"))


if __name__ == "__main__":  # pragma: no cover
    logger.info(
        "Iniciando a aplicação Web no endereço 0.0.0.0:5000 (DEBUG=%s)", settings.DEBUG
    )
    app.run(host="0.0.0.0", port=5000, debug=settings.DEBUG)
