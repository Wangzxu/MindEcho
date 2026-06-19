# -*- coding: utf-8 -*-
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

class UserRegister(BaseModel):
    username: str = Field(..., description="用户名/学号/工号，做唯一标识", min_length=3, max_length=50)
    password: str = Field(..., description="注册明文密码", min_length=6, max_length=100)
    nickname: Optional[str] = Field(None, description="可选的用户自拟昵称")


class UserLogin(BaseModel):
    username: str = Field(..., description="用户名/学号/工号")
    password: str = Field(..., description="登录密码")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT 访问 Token 字符串")
    token_type: str = Field("bearer", description="Token 类型，固定为 bearer")


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):
    id: int
    user_id: int
    nickname: str
    core_stressors: List[str]
    effective_coping_methods: List[str]
    entity_relation_map: Dict[str, str]
    semantic_history_recall: Optional[str]

    class Config:
        from_attributes = True
