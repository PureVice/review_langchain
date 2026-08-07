import logging
import sys
from pathlib import Path

from flasgger import Swagger
from flask import Flask, redirect, render_template, request, url_for
from pydantic import ValidationError

from src.config import settings, setup_logging

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.agent.agent import analyze_review
from src.database.sqlalchemy_repository import SQLAlchemyRepository
from src.schemas import ReviewRequest
from src.service.review_service import ReviewService

setup_logging()
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
app = Flask(__name__, template_folder=str(TEMPLATES_DIR))

# Configuração do Swagger
swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "Review Analyzer API",
        "description": "Documentação dos endpoints da aplicação de análise de avaliações usando LLM.",
        "version": "1.0.0",
    },
}
swagger = Swagger(app, template=swagger_template)

review_repository = SQLAlchemyRepository()
review_service = ReviewService(
    repository=review_repository, agent_function=analyze_review
)


@app.route("/", methods=["GET"])
def index():
    """
    Lista o histórico completo de análises.
    ---
    tags:
      - Reviews
    responses:
      200:
        description: Retorna a página inicial em HTML com a lista de avaliações.
    """
    logger.info("Requisição GET recebida no endpoint '/'.")
    entries = review_service.get_all_reviews()
    return render_template("index.html", entries=entries, single=False)


@app.route("/review/<int:review_id>", methods=["GET"])
def show_review(review_id):
    """
    Exibe uma análise específica.
    ---
    tags:
      - Reviews
    parameters:
      - name: review_id
        in: path
        type: integer
        required: true
        description: ID da avaliação no banco de dados.
    responses:
      200:
        description: Retorna a página em HTML contendo a avaliação solicitada.
      302:
        description: Redireciona para a raiz caso a avaliação não seja encontrada.
    """
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
    """
    Envia um novo texto para análise do Agente LLM.
    ---
    tags:
      - Reviews
    consumes:
      - application/x-www-form-urlencoded
    parameters:
      - name: review_text
        in: formData
        type: string
        required: true
        description: Texto da avaliação escrita pelo usuário.
    responses:
      302:
        description: Redireciona para a página inicial após salvar a análise.
    """
    logger.info("Requisição POST recebida no endpoint '/analyze'.")
    raw_text = request.form.get("review_text", "").strip()

    try:
        review_request = ReviewRequest(review_text=raw_text)
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
