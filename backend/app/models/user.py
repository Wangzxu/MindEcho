# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.database.mysql import Base

class User(Base):
    """用户账号鉴权表"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="student")  # role: admin / student
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 1对1 关联心理画像表
    profile = relationship('UserProfile', back_populates='user', uselist=False, cascade="all, delete-orphan")
    
    # 关联会话列表
    sessions = relationship('ChatSession', back_populates='user', lazy=True)

    # 关联安全事件日志
    security_logs = relationship('SecurityActivityLog', back_populates='user', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat()
        }
