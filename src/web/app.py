import sys
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.agent.agent import analyze_review
from src.database.db import get_all_reviews, get_review_by_id, init_db, save_review

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
app = Flask(__name__, template_folder=str(TEMPLATES_DIR))

init_db()


@app.route("/", methods=["GET"])
def index():
    """Exibe o histórico completo de análises."""
    entries = get_all_reviews()
    return render_template("index.html", entries=entries, single=False)


@app.route("/review/<int:review_id>", methods=["GET"])
def show_review(review_id):
    """Exibe apenas uma análise específica."""
    entry = get_review_by_id(review_id)
    if not entry:
        return redirect(url_for("index"))
    return render_template("index.html", entries=[entry], single=True)


@app.route("/analyze", methods=["POST"])
def analyze():
    """Recebe o texto enviado pelo formulário e executa a análise."""
    review_text = request.form.get("review_text", "").strip()

    if review_text:
        agent_response = analyze_review(review_text)
        save_review(review_text, agent_response)

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
