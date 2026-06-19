# -*- coding: utf-8 -*-
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

class SafetyKeywordCreate(BaseModel):
    word: str = Field(..., description="要过滤拦截的敏感词正文", min_length=1, max_length=100)
    word_type: str = Field(..., description="敏感词类型: high_risk / violation")
    is_enabled: bool = Field(True, description="是否启用拦截")

class SafetyKeywordResponse(BaseModel):
    id: int
    word: str
    word_type: str
    is_enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SecurityActivityLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    session_id: str
    trigger_content: str
    log_type: str
    matched_rule: str
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardStatsResponse(BaseModel):
    student_count: int
    session_count: int
    high_risk_count: int
    violation_count: int


class PaginatedSecurityLogs(BaseModel):
    total: int
    page: int
    size: int
    items: list[SecurityActivityLogResponse]


class StudentResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    nickname: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedStudents(BaseModel):
    total: int
    page: int
    size: int
    items: list[StudentResponse]


class UpdateStudentStatus(BaseModel):
    is_active: bool


class PaginatedSafetyKeywords(BaseModel):
    total: int
    page: int
    size: int
    items: list[SafetyKeywordResponse]


class SafetyKeywordUpdate(BaseModel):
    word: Optional[str] = None
    word_type: Optional[str] = None
    is_enabled: Optional[bool] = None

