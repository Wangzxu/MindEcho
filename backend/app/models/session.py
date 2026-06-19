# -*- coding: utf-8 -*-
from datetime import datetime
import uuid
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database.mysql import Base

class ChatSession(Base):
    """聊天会话表"""
    __tablename__ = 'chat_sessions'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # 支持匿名会话（user_id 为空）
    title = Column(String(255), default="新对话")
    created_at = Column(DateTime, default=datetime.utcnow)
    summary = Column(Text, nullable=True)  # 该会话的摘要
    is_anonymous = Column(Boolean, default=False)  # 是否为无痕树洞会话

    # 关系映射
    user = relationship('User', back_populates='sessions')
    messages = relationship('ChatMessage', back_populates='session', lazy=True, cascade="all, delete-orphan")
    security_logs = relationship('SecurityActivityLog', back_populates='session', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "summary": self.summary,
            "is_anonymous": self.is_anonymous
        }
