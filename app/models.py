from datetime import datetime

from sqlalchemy import ARRAY, Column, DateTime, Integer, String

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    text = Column(String, nullable=False)
    rubrics = Column(ARRAY(String), nullable=True)
    created_date = Column(DateTime, nullable=False, default=datetime.utcnow)
