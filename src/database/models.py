from sqlalchemy import Column, DateTime, Integer, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class ReviewModel(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_text = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
