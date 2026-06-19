# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database.mysql import Base

class SafetyKeyword(Base):
    """安全敏感词过滤配置表"""
    __tablename__ = 'safety_keywords'

    id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String(100), unique=True, nullable=False, index=True)
    word_type = Column(String(20), nullable=False)  # high_risk (高危自残), violation (谩骂违规)
    is_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "word": self.word,
            "word_type": self.word_type,
            "is_enabled": self.is_enabled,
            "created_at": self.created_at.isoformat()
        }
