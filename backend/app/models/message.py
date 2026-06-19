# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database.mysql import Base

class ChatMessage(Base):
    """聊天消息明细表"""
    __tablename__ = 'chat_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey('chat_sessions.id'), nullable=False)
    sender = Column(String(10), nullable=False)  # 'user' 或 'ai'
    content = Column(Text, nullable=False)  # 消息正文
    intent = Column(String(50), nullable=True)  # 意图分类（CRISIS, KNOWLEDGE, EMOTION, CHITCHAT）
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系映射
    session = relationship('ChatSession', back_populates='messages')

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "sender": self.sender,
            "content": self.content,
            "intent": self.intent,
            "created_at": self.created_at.isoformat()
        }
