# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from app.database.mysql import Base

class KnowledgeImport(Base):
    """知识文档导入任务与云存储记录表"""
    __tablename__ = 'knowledge_imports'

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(255), nullable=False, index=True)
    file_hash = Column(String(64), unique=True, nullable=False)
    minio_bucket = Column(String(64), nullable=False)
    minio_object_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending, processing, success, failed
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "file_name": self.file_name,
            "file_hash": self.file_hash,
            "minio_bucket": self.minio_bucket,
            "minio_object_name": self.minio_object_name,
            "file_size": self.file_size,
            "status": self.status,
            "chunk_count": self.chunk_count,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat()
        }
