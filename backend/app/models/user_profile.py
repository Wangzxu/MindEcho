# -*- coding: utf-8 -*-
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database.mysql import Base

class UserProfile(Base):
    """用户心理特征画像与长期记忆表"""
    __tablename__ = 'user_profiles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    nickname = Column(String(80), nullable=True)
    
    # 心理特征与长期记忆
    core_stressors = Column(JSON, nullable=True, default=list)  # 核心压力源 JSON
    effective_coping_methods = Column(JSON, nullable=True, default=list)  # 历史有效方法 JSON
    entity_relation_map = Column(JSON, nullable=True, default=dict)  # 重要人物关系网络 JSON
    semantic_history_recall = Column(Text, nullable=True)  # 历史会话合并提炼的摘要线索
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 1对1 关联账号表
    user = relationship('User', back_populates='profile')

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "nickname": self.nickname or "匿名同学",
            "core_stressors": self.core_stressors or [],
            "effective_coping_methods": self.effective_coping_methods or [],
            "entity_relation_map": self.entity_relation_map or {},
            "semantic_history_recall": self.semantic_history_recall or ""
        }
