# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database.mysql import Base

class SecurityActivityLog(Base):
    """安全事件拦截与预警活动日志表"""
    __tablename__ = 'security_activity_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    session_id = Column(String(36), ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False)
    trigger_content = Column(Text, nullable=False)
    log_type = Column(String(20), nullable=False)  # high_risk (高危), violation (违规)
    matched_rule = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联关系
    user = relationship('User', back_populates='security_logs', lazy=True)
    session = relationship('ChatSession', back_populates='security_logs', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "trigger_content": self.trigger_content,
            "log_type": self.log_type,
            "matched_rule": self.matched_rule,
            "created_at": self.created_at.isoformat()
        }
