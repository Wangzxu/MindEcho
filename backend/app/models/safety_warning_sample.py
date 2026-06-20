# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database.mysql import Base

class SafetyWarningSample(Base):
    """安全预警 RAG 向量样本表（模糊匹配火种库）"""
    __tablename__ = 'safety_warning_samples'

    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(String(255), unique=True, nullable=False, index=True)
    sample_type = Column(String(20), nullable=False)  # high_risk (高危自残), violation (谩骂违规)
    is_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "sample_type": self.sample_type,
            "is_enabled": self.is_enabled,
            "created_at": self.created_at.isoformat()
        }
