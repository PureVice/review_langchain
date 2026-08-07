import logging
import sys
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for
from pydantic import ValidationError

from src.config import settings, setup_logging

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.agent.agent import analyze_review
from src.database.db import get_all_reviews, get_review_by_id, init_db, save_review
from src.schemas import ReviewRequest

# Inicializa as configurações Globais de Logs
setup_logging()
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
app = Flask(__name__, template_folder=str(TEMPLATES_DIR))

# Inicialização do Banco
init_db()


@app.route("/", methods=["GET"])
def index():
    """Exibe o histórico completo de análises."""
    logger.info("Requisição GET recebida no endpoint '/'.")
    entries = get_all_reviews()
    return render_template("index.html", entries=entries, single=False)


@app.route("/review/<int:review_id>", methods=["GET"])
def show_review(review_id):
    """Exibe apenas uma análise específica."""
    logger.info("Requisição GET recebida para a avaliação ID: %d", review_id)
    entry = get_review_by_id(review_id)
    if not entry:
        logger.warning(
            "Avaliação ID %d não foi localizada. Redirecionando para '/'.", review_id
        )
        return redirect(url_for("index"))
    return render_template("index.html", entries=[entry], single=True)


@app.route("/analyze", methods=["POST"])
def analyze():
    """Recebe o texto enviado pelo formulário, valida via Pydantic e executa a análise."""
    logger.info("Requisição POST recebida no endpoint '/analyze'.")
    raw_text = request.form.get("review_text", "").strip()

    try:
        # Validação de dados com o schema Pydantic
        review_request = ReviewRequest(review_text=raw_text)
        agent_response = analyze_review(review_request)
        save_review(review_request.review_text, agent_response)
    except ValidationError as ve:
        logger.warning("Falha na validação dos dados de entrada (Pydantic): %s", ve)
    except Exception:
        logger.exception("Erro ao processar e armazenar a avaliação enviada.")

    return redirect(url_for("index"))


if __name__ == "__main__":
    logger.info(
        "Iniciando a aplicação Web no endereço 0.0.0.0:5000 (DEBUG=%s)", settings.DEBUG
    )
    app.run(host="0.0.0.0", port=5000, debug=settings.DEBUG)
