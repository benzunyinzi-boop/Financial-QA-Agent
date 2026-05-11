"""
SQLAlchemy 数据库模型
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, BigInteger
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Document(Base):
    """文档元数据表"""
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # txt, pdf, md, docx
    size_bytes = Column(BigInteger, nullable=False)
    md5 = Column(String, unique=True, nullable=False)
    chunk_count = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending, indexing, indexed, failed
    storage_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
