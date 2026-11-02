from sqlalchemy import Column, DateTime, Float, Integer, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class ReviewModel(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_text = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=False)
    execution_time = Column(Float, nullable=True, default=0.0)
    input_tokens = Column(Integer, nullable=True, default=0)
    output_tokens = Column(Integer, nullable=True, default=0)
    total_tokens = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime, server_default=func.now())
