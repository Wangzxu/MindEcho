# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.mysql import get_db, SessionLocal
from app.database.vector import vector_db
from app.services.llm import llm_service
from app.schemas.health import HealthStatus
from app.schemas.base import Result

# 使用 APIRouter 代替 Flask Blueprint
health_bp = APIRouter(prefix="/api", tags=["系统健康检查"])

@health_bp.get("/health", response_model=Result[HealthStatus])
def health_check(db: Session = Depends(get_db)):
    """系统各项服务健康状况检查"""
    status_report = {
        "status": "healthy",
        "mysql": "ok",
        "chromadb": "ok",
        "siliconflow": "ok",
        "warnings": []
    }

    # 1. 检查 MySQL 连通性
    try:
        db.execute(SessionLocal().bind.execute(db.text("SELECT 1")))
    except Exception as e:
        status_report["status"] = "degraded"
        status_report["mysql"] = f"failed: {str(e)}"
        status_report["warnings"].append("MySQL 数据库连接异常")

    # 2. 检查 ChromaDB
    if not vector_db.client:
        status_report["status"] = "degraded"
        status_report["chromadb"] = "uninitialized"
        status_report["warnings"].append("向量数据库未完成初始化")
    else:
        try:
            vector_db.get_collection("psychology_kb")
        except Exception as e:
            status_report["status"] = "degraded"
            status_report["chromadb"] = f"error: {str(e)}"
            status_report["warnings"].append("向量数据库集合访问失败")

    # 3. 检查 SiliconFlow
    if not llm_service.client:
        status_report["siliconflow"] = "mock_mode"
        status_report["warnings"].append("SiliconFlow 未配置 API 密钥，当前运行在 Mock 模式")

    if status_report["status"] == "healthy":
        return Result.success(data=status_report, message="系统服务运行正常")
    else:
        return Result.error(code=500, message="系统服务处于降级运行状态", data=status_report)
