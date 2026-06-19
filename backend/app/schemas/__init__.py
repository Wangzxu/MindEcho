# -*- coding: utf-8 -*-
from app.schemas.base import Result
from app.schemas.health import HealthStatus
from app.schemas.session import SessionCreate, SessionResponse
from app.schemas.message import MessageCreate, MessageResponse
from app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserResponse, UserProfileResponse
from app.schemas.knowledge import KnowledgeImportCreate, KnowledgeImportResponse
from app.schemas.safety import (
    SafetyKeywordCreate, 
    SafetyKeywordResponse, 
    SecurityActivityLogResponse,
    DashboardStatsResponse,
    PaginatedSecurityLogs,
    StudentResponse,
    PaginatedStudents,
    UpdateStudentStatus,
    PaginatedSafetyKeywords,
    SafetyKeywordUpdate
)

# 统一导出所有数据契约 Schema
__all__ = [
    "Result",
    "HealthStatus",
    "SessionCreate",
    "SessionResponse",
    "MessageCreate",
    "MessageResponse",
    "UserRegister",
    "UserLogin",
    "TokenResponse",
    "UserResponse",
    "UserProfileResponse",
    "KnowledgeImportCreate",
    "KnowledgeImportResponse",
    "SafetyKeywordCreate",
    "SafetyKeywordResponse",
    "SecurityActivityLogResponse",
    "DashboardStatsResponse",
    "PaginatedSecurityLogs",
    "StudentResponse",
    "PaginatedStudents",
    "UpdateStudentStatus",
    "PaginatedSafetyKeywords",
    "SafetyKeywordUpdate"
]

