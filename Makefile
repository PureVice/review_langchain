.PHONY: help install run test format lint prepare-precommit clean docker-build docker-up docker-down

# Variáveis
PYTHON = python3
PIP = pip
FLASK_APP = src/web/app.py

help: ## Exibe a lista de comandos disponíveis
	@echo "Comandos disponíveis:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Instala as dependências do projeto
	$(PIP) install -r requirements.txt

run: ## Executa a aplicação localmente
	PYTHONPATH=. $(PYTHON) $(FLASK_APP)

test: ## Executa os testes automatizados com pytest
	PYTHONPATH=. pytest tests/ -v

format: ## Aplica a formatação automática (Black) e correções de lint (Ruff)
	black src/ tests/
	ruff check --fix src/ tests/

lint: ## Checa a formatação e qualidade do código sem alterar os arquivos
	black --check src/ tests/
	ruff check src/ tests/

prepare-precommit: ## Instala os hooks do pre-commit no Git local
	pre-commit install

clean: ## Remove arquivos temporários, caches do Python e do Pytest
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .coverage

docker-build: ## Constrói a imagem Docker via docker-compose
	docker-compose build

docker-up: ## Sobe a aplicação em contêineres Docker em segundo plano
	docker-compose up -d

docker-down: ## Para e remove os contêineres Docker
	docker-compose down --remove-orphans
