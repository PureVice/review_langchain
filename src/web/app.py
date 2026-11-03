import logging
import sys
from pathlib import Path

from flasgger import Swagger
from flask import Flask, Response, redirect, render_template, request, url_for
from pydantic import ValidationError

from src.config import settings, setup_logging

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.agent.agent import analyze_review
from src.database.sqlalchemy_repository import SQLAlchemyRepository
from src.schemas import ReviewRequest
from src.service.review_service import ReviewService, describe_processing_error

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
    repository=review_repository,
    agent_function=analyze_review,
    checkpoint_path=ROOT_DIR / "data" / "checkpoint_batch.json",
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
    error = request.args.get("error")
    success = request.args.get("success")
    active_tab = request.args.get("tab", "reviews")
    return render_template(
        "index.html",
        entries=entries,
        single=False,
        error=error,
        success=success,
        active_tab=active_tab,
        llm_provider=(settings.LLM_PROVIDER or "gemini").strip().lower(),
        gemini_model=settings.GEMINI_MODEL,
        deepseek_model=settings.DEEPSEEK_MODEL,
    )


@app.route("/settings", methods=["POST"])
def update_settings():
    """
    Atualiza as configurações da aplicação (ex: provedor LLM entre Gemini e DeepSeek).
    ---
    tags:
      - Settings
    consumes:
      - application/x-www-form-urlencoded
    parameters:
      - name: llm_provider
        in: formData
        type: string
        required: true
        enum: [gemini, deepseek]
        description: Provedor de LLM selecionado ('gemini' ou 'deepseek').
    responses:
      302:
        description: Redireciona para a aba de configurações.
    """
    provider = request.form.get("llm_provider", "").strip().lower()
    if provider not in ("gemini", "deepseek"):
        return redirect(
            url_for(
                "index",
                tab="settings",
                error="Provedor de IA inválido. Escolha 'gemini' ou 'deepseek'.",
            )
        )

    settings.LLM_PROVIDER = provider
    provider_label = "Google Gemini" if provider == "gemini" else "DeepSeek"
    logger.info("Provedor LLM alterado via interface para: %s", provider)
    return redirect(
        url_for(
            "index",
            tab="settings",
            success=f"Modelo de IA alterado para {provider_label} com sucesso!",
        )
    )


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

    return render_template(
        "index.html",
        entries=[entry],
        single=True,
        llm_provider=(settings.LLM_PROVIDER or "gemini").strip().lower(),
        gemini_model=settings.GEMINI_MODEL,
        deepseek_model=settings.DEEPSEEK_MODEL,
    )


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
        return redirect(
            url_for("index", error="O texto da avaliação não pode estar vazio.")
        )
    except Exception as exc:
        logger.exception("Erro ao processar e armazenar a avaliação enviada.")
        error_msg = describe_processing_error(exc, is_batch=False)
        return redirect(url_for("index", error=error_msg))

    return redirect(url_for("index"))


@app.route("/upload", methods=["POST"])
def upload_file():
    """
    Recebe o upload de um arquivo JSON ou CSV com o campo 'content' e processa as avaliações.
    ---
    tags:
      - Reviews
    consumes:
      - multipart/form-data
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: Arquivo .json ou .csv contendo o campo 'content' com as avaliações.
    responses:
      302:
        description: Redireciona para a página inicial após processar o arquivo.
    """
    logger.info("Requisição POST recebida no endpoint '/upload'.")
    uploaded = request.files.get("file")

    if not uploaded or not uploaded.filename:
        logger.warning("Nenhum arquivo enviado no endpoint '/upload'.")
        return redirect(
            url_for("index", error="Nenhum arquivo selecionado para upload.")
        )

    try:
        raw_bytes = uploaded.read()
        review_service.process_file_upload(uploaded.filename, raw_bytes)
    except ValueError as ve:
        logger.warning("Erro de validação no arquivo enviado: %s", ve)
        return redirect(url_for("index", error=str(ve)))
    except Exception as exc:
        logger.exception("Erro ao processar o arquivo enviado no upload.")
        error_msg = describe_processing_error(exc, is_batch=True)
        return redirect(url_for("index", error=error_msg))

    return redirect(url_for("index"))


@app.route("/export/csv", methods=["GET"])
def export_csv():
    """
    Exporta o dataset completo de avaliações analisadas em formato CSV.
    ---
    tags:
      - Reviews
    produces:
      - text/csv
    responses:
      200:
        description: Arquivo CSV contendo as avaliações e análises.
    """
    logger.info("Requisição GET recebida no endpoint '/export/csv'.")
    csv_content = review_service.export_reviews_to_csv()
    return Response(
        csv_content,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=reviews_dataset.csv"},
    )


if __name__ == "__main__":  # pragma: no cover
    logger.info(
        "Iniciando a aplicação Web no endereço 0.0.0.0:5000 (DEBUG=%s)", settings.DEBUG
    )
    app.run(host="0.0.0.0", port=5000, debug=settings.DEBUG)
