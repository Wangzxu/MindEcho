# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database.mysql import init_mysql
from app.database.vector import vector_db
from app.services.llm import llm_service
from app.routes.health import health_bp
from app.routes.chat import chat_bp
from app.routes.auth import auth_bp
from app.routes.admin import admin_bp
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 统一生命周期生命周期管理器 (Lifespan)
    取代旧的在应用运行时单独初始化的逻辑，保证在服务启动前完成数据库建表及客户端链接校验。
    """
    logging.basicConfig(level=logging.INFO)
    logger.info("正在启动 MindEcho 后端服务...")
    
    # 1. 初始化 MySQL 数据库结构
    init_mysql()
    
    # 2. 初始化向量数据库 (ChromaDB)
    vector_db.init_db()
    
    # 3. 校验并载入硅基流动大模型客户端
    llm_service.init_service()

    # 3.5 同步 MySQL 安全预警 RAG 向量样本到 ChromaDB (用于在更换嵌入模型时自动重建向量索引)
    try:
        from app.database.mysql import sync_warning_samples_to_vector_db
        sync_warning_samples_to_vector_db()
    except Exception as e:
        logger.error(f"服务启动时同步预警向量样本失败: {str(e)}")
    
    # 4. 初始化对象存储服务 (MinIO)
    from app.services.storage import storage_service
    storage_service.init_service()
    
    logger.info("MindEcho 后端服务启动初始化校验完成。")
    yield
    logger.info("MindEcho 后端服务正在安全退出...")


def create_app() -> FastAPI:
    """
    FastAPI 应用工程工厂函数
    """
    app = FastAPI(
        title="MindEcho API Backend",
        description="校园 AI 心理委员系统 (MVP) 后端接口规范说明书",
        version="0.1.0",
        lifespan=lifespan
    )

    # 启用 CORS 中间件，支持跨域
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注入业务子路由 APIRouter
    app.include_router(health_bp)
    app.include_router(chat_bp)
    app.include_router(auth_bp)
    app.include_router(admin_bp)

    return app

