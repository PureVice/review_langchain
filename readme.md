este projeto se trata de um avaliador de opiniões utilizando LLMs

Persistência de dados

- As reviews e as respostas do modelo são salvas em um banco de dados para uso posterior em treino de outros modelos.
- Por padrão utiliza SQLite (arquivo reviews.db). Para usar PostgreSQL ou outro banco eficiente, defina a variável de ambiente DATABASE_URL.
  - Exemplo Postgres: export DATABASE_URL='postgresql+psycopg://user:password@host:5432/dbname'

Dependências úteis

- SQLAlchemy (recomendado): pip install sqlalchemy
- Psycopg (Postgres driver): pip install psycopg[binary]
- LangChain / deepseek client: siga as instruções originais do projeto (DEEPSEEK_API_KEY deve estar setada)

Execução

1. Exporte variáveis de ambiente necessárias:
   - DEEPSEEK_API_KEY (obrigatório)
   - DATABASE_URL (opcional — usa SQLite se ausente)
2. Execute: python main.py
3. Cole a review e pressione Enter; o agente avaliará e o resultado será salvo no banco.

Uso com PostgreSQL via Docker

1. Copie .env.example para .env e ajuste se necessário: cp .env.example .env
2. Inicie o banco: docker-compose up -d
3. Exporte a variável DATABASE_URL (exemplo):
   export DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/reviews'
4. Instale dependências (se usar Postgres):
   pip install sqlalchemy psycopg[binary]
5. Execute o programa: python main.py

Observações:
- Adminer está disponível em http://localhost:8080 para gerenciar o banco (user/postgres por padrão).
- Se preferir não usar Docker, configure um PostgreSQL externo e ajuste DATABASE_URL.

