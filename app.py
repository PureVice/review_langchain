import os
import json
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from sqlalchemy import create_engine, Column, Integer, Text, DateTime
from sqlalchemy.types import JSON as SAJSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

contexto = open('perfil_agente.txt','r',encoding='utf-8').read()

llm = ChatOpenAI(
    model='deepseek-chat',
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url='https://api.deepseek.com'
)

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///reviews.db')
engine = create_engine(DATABASE_URL, echo=False, future=True)
Base = declarative_base()

class Review(Base):
    __tablename__ = 'reviews'
    id = Column(Integer, primary_key=True)
    review_text = Column(Text, nullable=False)
    agent_response = Column(SAJSON, nullable=True)
    created_at = Column(DateTime, nullable=False)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine, future=True)

agent = create_agent(
    model=llm,
    tools=[],
    system_prompt=contexto,
)

app = Flask(__name__)

def extract_json_from_agent(result_obj):
    """Tenta extrair um JSON válido da resposta bruta do agente."""
    try:
        content = ""
        if isinstance(result_obj, dict):
            if 'output' in result_obj:
                content = result_obj['output']
            elif 'messages' in result_obj and len(result_obj['messages']) > 0:
                content = result_obj['messages'][-1].content
        else:
            content = str(result_obj)
        
        # Busca por chaves na string indicando um bloco JSON
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass
    return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        review = request.form.get('review', '').strip()
        if not review:
            return redirect(url_for('index'))
        
        result = agent.invoke({"messages": [{"role": "user", "content": review}]})
        
        # Tenta extrair o JSON estruturado para visualização amigável
        parsed_json = extract_json_from_agent(result)
        payload = parsed_json if parsed_json else {"raw": str(result)}
        
        session = Session()
        try:
            row = Review(review_text=review, agent_response=payload, created_at=datetime.utcnow())
            session.add(row)
            session.commit()
            saved_id = row.id
        finally:
            session.close()
        return redirect(url_for('view_review', review_id=saved_id))

    session = Session()
    try:
        entries = session.query(Review).order_by(Review.id.desc()).limit(20).all()
    finally:
        session.close()
    return render_template('index.html', entries=entries, single=False)

@app.route('/review/<int:review_id>')
def view_review(review_id):
    session = Session()
    try:
        entry = session.get(Review, review_id)
    finally:
        session.close()
    if not entry:
        return "Not found", 404
    return render_template('index.html', entries=[entry], single=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)