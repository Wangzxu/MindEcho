# -*- coding: utf-8 -*-
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

class MessageCreate(BaseModel):
    session_id: str = Field(..., description="会话 UUID")
    content: str = Field(..., description="发送消息的文本内容", max_length=800)


class MessageResponse(BaseModel):
    id: int
    session_id: str
    sender: str
    content: str
    intent: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
