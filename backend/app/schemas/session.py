# -*- coding: utf-8 -*-
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

class SessionCreate(BaseModel):
    user_id: Optional[int] = Field(None, description="关联的用户ID，匿名聊天时不传")
    title: str = Field("新的对话", description="会话标题")
    is_anonymous: bool = Field(False, description="是否为匿名树洞会话")


class SessionResponse(BaseModel):
    id: str
    user_id: Optional[int]
    title: str
    created_at: datetime
    summary: Optional[str]
    is_anonymous: bool

    class Config:
        from_attributes = True
