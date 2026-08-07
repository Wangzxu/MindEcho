# -*- coding: utf-8 -*-
from app.services.llm import llm_service
from app.database.vector import vector_db
from app.services.storage import storage_service
import logging
import os
import uuid
import hashlib
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from app.models.knowledge import KnowledgeImport
from sqlalchemy.orm import Session
from typing import Optional

from app.database.mysql import get_db
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.session import ChatSession
from app.models.safety_keyword import SafetyKeyword
from app.models.security_activity_log import SecurityActivityLog
from app.schemas.base import Result
from app.schemas.safety import (
    DashboardStatsResponse,
    PaginatedSecurityLogs,
    SecurityActivityLogResponse,
    StudentResponse,
    PaginatedStudents,
    UpdateStudentStatus,
    PaginatedSafetyKeywords,
    SafetyKeywordResponse,
    SafetyKeywordCreate,
    SafetyKeywordUpdate
)
from app.schemas.auth import UserResponse, UserProfileResponse
from app.routes.auth import get_current_admin
from app.services.intent import intent_service
from app.services.rag import (
    extract_text_from_file, split_text_into_chunks,
    split_markdown_into_chunks, ingest_document,
    retrieve_with_context, trace_retrieval
)
from app.services.converter import convert_to_markdown
from config import Config

logger = logging.getLogger(__name__)

admin_bp = APIRouter(
    prefix="/api/admin",
    tags=["教师端后台管理"],
    dependencies=[Depends(get_current_admin)]
)


# 物理 YAML 写入机制已被完全废弃，此部分无用方法已被清理。


@admin_bp.get("/dashboard/stats", response_model=Result[DashboardStatsResponse])
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    获取后台看板的核心统计数据：
    1. 注册学生总数
    2. 咨询人次 (Session 数)
    3. 危险警报拦截 (高危)
    4. 违规行为拦截 (违规)
    """
    try:
        student_count = db.query(User).filter(User.role == "student").count()
        session_count = db.query(ChatSession).count()
        
        high_risk_count = db.query(SecurityActivityLog).filter(
            SecurityActivityLog.log_type == "high_risk"
        ).count()
        
        violation_count = db.query(SecurityActivityLog).filter(
            SecurityActivityLog.log_type == "violation"
        ).count()
        
        stats = DashboardStatsResponse(
            student_count=student_count,
            session_count=session_count,
            high_risk_count=high_risk_count,
            violation_count=violation_count
        )
        return Result.success(data=stats, message="获取仪表盘统计数据成功")
    except Exception as e:
        logger.error(f"获取仪表盘统计失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务异常: {str(e)}"
        )


@admin_bp.get("/security/logs", response_model=Result[PaginatedSecurityLogs])
def get_security_logs(
    page: int = Query(1, ge=1, description="当前页码"),
    size: int = Query(10, ge=1, le=100, description="每页限制"),
    log_type: Optional[str] = Query(None, description="日志分类 (high_risk / violation)"),
    db: Session = Depends(get_db)
):
    """
    分页拉取安全审计日志 (仅包含高危与违规的拦截事件)
    """
    try:
        query = db.query(SecurityActivityLog)
        
        if log_type:
            if log_type not in ["high_risk", "violation"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="日志类型必须为 high_risk 或 violation"
                )
            query = query.filter(SecurityActivityLog.log_type == log_type)
            
        # 按照创建时间降序
        query = query.order_by(SecurityActivityLog.created_at.desc())
        
        total = query.count()
        offset = (page - 1) * size
        logs = query.offset(offset).limit(size).all()
        
        # 封装为 Pydantic 兼容模型列表
        items = [SecurityActivityLogResponse.model_validate(log) for log in logs]
        
        # 对于匿名会话，日志中记录的 user_id 在模型中已支持为 Null/None
        
        data = PaginatedSecurityLogs(
            total=total,
            page=page,
            size=size,
            items=items
        )
        return Result.success(data=data, message="获取安全审计日志成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取安全审计日志失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务异常: {str(e)}"
        )


@admin_bp.get("/students", response_model=Result[PaginatedStudents])
def get_students(
    page: int = Query(1, ge=1, description="当前页码"),
    size: int = Query(10, ge=1, le=100, description="每页限制"),
    username: Optional[str] = Query(None, description="用户名模糊搜索"),
    db: Session = Depends(get_db)
):
    """
    分页获取学生列表，支持用户名模糊查询，并级联关联获取脱敏画像中设置的昵称
    """
    try:
        query = db.query(User).filter(User.role == "student")
        
        if username:
            query = query.filter(User.username.like(f"%{username}%"))
            
        query = query.order_by(User.id.asc())
        
        total = query.count()
        offset = (page - 1) * size
        users = query.offset(offset).limit(size).all()
        
        items = []
        for u in users:
            items.append(StudentResponse(
                id=u.id,
                username=u.username,
                role=u.role,
                is_active=u.is_active,
                created_at=u.created_at,
                nickname=u.profile.nickname if u.profile else None
            ))
            
        data = PaginatedStudents(
            total=total,
            page=page,
            size=size,
            items=items
        )
        return Result.success(data=data, message="获取学生列表成功")
    except Exception as e:
        logger.error(f"获取学生列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务异常: {str(e)}"
        )


@admin_bp.get("/students/{user_id}/profile", response_model=Result[UserProfileResponse])
def get_student_profile(user_id: int, db: Session = Depends(get_db)):
    """
    查阅指定学生的心理画像详情 (仅限角色为 student 的账号)
    """
    try:
        user = db.query(User).filter(User.id == user_id, User.role == "student").first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到该学生用户，或该用户非学生角色"
            )
            
        if not user.profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="该学生暂未生成心理特征画像"
            )
            
        # 返回脱敏画像详情
        profile_data = UserProfileResponse.model_validate(user.profile)
        return Result.success(data=profile_data, message="获取学生心理画像成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取学生心理画像失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务异常: {str(e)}"
        )


@admin_bp.put("/students/{user_id}/status", response_model=Result[UserResponse])
def update_student_status(
    user_id: int,
    status_data: UpdateStudentStatus,
    db: Session = Depends(get_db)
):
    """
    停用/激活指定学生账户 (禁止停用管理员账户)
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="指定用户不存在"
            )
            
        if user.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法停用或修改管理员的激活状态"
            )
            
        user.is_active = status_data.is_active
        db.commit()
        db.refresh(user)
        
        logger.info(f"管理员修改了用户 {user.username} 的激活状态为: {user.is_active}")
        return Result.success(data=UserResponse.model_validate(user), message="更新学生激活状态成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"修改学生状态异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务异常: {str(e)}"
        )


@admin_bp.get("/safety-keywords", response_model=Result[PaginatedSafetyKeywords])
def get_safety_keywords(
    page: int = Query(1, ge=1, description="当前页码"),
    size: int = Query(50, ge=1, le=500, description="每页限制"),
    word: Optional[str] = Query(None, description="敏感词搜索"),
    word_type: Optional[str] = Query(None, description="敏感分类 (high_risk / violation)"),
    db: Session = Depends(get_db)
):
    """
    分页查询活跃敏感词库配置
    """
    try:
        query = db.query(SafetyKeyword)
        
        if word:
            query = query.filter(SafetyKeyword.word.like(f"%{word}%"))
            
        if word_type:
            if word_type not in ["high_risk", "violation"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="词库类型必须为 high_risk 或 violation"
                )
            query = query.filter(SafetyKeyword.word_type == word_type)
            
        query = query.order_by(SafetyKeyword.created_at.desc())
        
        total = query.count()
        offset = (page - 1) * size
        keywords = query.offset(offset).limit(size).all()
        
        items = [SafetyKeywordResponse.model_validate(kw) for kw in keywords]
        
        data = PaginatedSafetyKeywords(
            total=total,
            page=page,
            size=size,
            items=items
        )
        return Result.success(data=data, message="获取敏感词列表成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取敏感词库失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务异常: {str(e)}"
        )


@admin_bp.post("/safety-keywords", response_model=Result[SafetyKeywordResponse], status_code=status.HTTP_201_CREATED)
def create_safety_keyword(
    keyword_data: SafetyKeywordCreate,
    db: Session = Depends(get_db)
):
    """
    新增拦截敏感词，并热同步同步至 safety_rules.yaml 以更新 AI 拦截服务
    """
    word = keyword_data.word.strip()
    word_type = keyword_data.word_type
    
    if word_type not in ["high_risk", "violation"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="敏感词类型必须为 high_risk 或 violation"
        )
        
    try:
        # 重名校验
        existing = db.query(SafetyKeyword).filter(SafetyKeyword.word == word).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"敏感词 '{word}' 已存在"
            )
            
        new_keyword = SafetyKeyword(
            word=word,
            word_type=word_type,
            is_enabled=keyword_data.is_enabled
        )
        db.add(new_keyword)
        db.commit()
        db.refresh(new_keyword)
        
        # 触发内存热更新
        intent_service.load_safety_rules()
        
        logger.info(f"新增敏感词成功并已热更新: {word} ({word_type})")
        return Result.success(data=SafetyKeywordResponse.model_validate(new_keyword), message="添加敏感词成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建敏感词异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务异常: {str(e)}"
        )


@admin_bp.put("/safety-keywords/{keyword_id}", response_model=Result[SafetyKeywordResponse])
def update_safety_keyword(
    keyword_id: int,
    keyword_data: SafetyKeywordUpdate,
    db: Session = Depends(get_db)
):
    """
    修改敏感词配置 (可支持修改词条文本、词条分类以及启用状态) 并同步至 YAML
    """
    try:
        keyword = db.query(SafetyKeyword).filter(SafetyKeyword.id == keyword_id).first()
        if not keyword:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到该敏感词配置"
            )
            
        if keyword_data.word is not None:
            word_val = keyword_data.word.strip()
            if word_val:
                # 重名冲突校验 (排除自身)
                conflict = db.query(SafetyKeyword).filter(
                    SafetyKeyword.word == word_val,
                    SafetyKeyword.id != keyword_id
                ).first()
                if conflict:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"敏感词 '{word_val}' 已经被其他项占用"
                    )
                keyword.word = word_val
                
        if keyword_data.word_type is not None:
            if keyword_data.word_type not in ["high_risk", "violation"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="词库类型必须为 high_risk 或 violation"
                )
            keyword.word_type = keyword_data.word_type
            
        if keyword_data.is_enabled is not None:
            keyword.is_enabled = keyword_data.is_enabled
            
        db.commit()
        db.refresh(keyword)
        
        # 触发内存热更新
        intent_service.load_safety_rules()
        
        logger.info(f"修改敏感词成功并已热更新: ID {keyword_id} -> {keyword.word} (启用: {keyword.is_enabled})")
        return Result.success(data=SafetyKeywordResponse.model_validate(keyword), message="修改敏感词配置成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"修改敏感词异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务异常: {str(e)}"
        )


@admin_bp.delete("/safety-keywords/{keyword_id}", response_model=Result[dict])
def delete_safety_keyword(keyword_id: int, db: Session = Depends(get_db)):
    """
    物理删除敏感过滤词，同步重写 YAML 配置文件并热重载
    """
    try:
        keyword = db.query(SafetyKeyword).filter(SafetyKeyword.id == keyword_id).first()
        if not keyword:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到该敏感词配置"
            )
            
        word_text = keyword.word
        db.delete(keyword)
        db.commit()
        
        # 触发内存热更新
        intent_service.load_safety_rules()
        
        logger.info(f"删除敏感词成功并已热更新: {word_text} (ID {keyword_id})")
        return Result.success(data={"deleted_id": keyword_id, "word": word_text}, message="删除敏感词成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除敏感词异常: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务异常: {str(e)}"
        )


# =======================================================
# 真实 RAG 向量嵌入、预警种子句管理与科普知识库接口
# =======================================================

class SafetySeedCreate(BaseModel):
    text: str
    type: str  # high_risk or violation

class SafetySeedResponse(BaseModel):
    id: str
    type: str
    text: str

class ManualKnowledgeCreate(BaseModel):
    title: str
    concept: str
    tip: str
    tags: Optional[str] = ""


class TraceRequest(BaseModel):
    query: str


@admin_bp.post("/safety-seeds", response_model=Result[dict])
def add_safety_seed(data: SafetySeedCreate, db: Session = Depends(get_db)):
    """
    添加安全预警 RAG 向量种子句到 MySQL 并在 ChromaDB (safety_warnings_kb 集合) 中建索引
    """
    text = data.text.strip()
    seed_type = data.type.strip()
    if not text:
        raise HTTPException(status_code=400, detail="内容不能为空")
    if seed_type not in ["high_risk", "violation"]:
        raise HTTPException(status_code=400, detail="类型必须为 high_risk 或 violation")
        
    try:
        from app.models.safety_warning_sample import SafetyWarningSample
        # 1. 检查 MySQL 中是否已存在
        existing = db.query(SafetyWarningSample).filter(SafetyWarningSample.text == text).first()
        if existing:
            if not existing.is_enabled:
                # 如果存在但未启用，则重新启用它
                existing.is_enabled = True
                existing.sample_type = seed_type
                db.commit()
            else:
                raise HTTPException(status_code=400, detail="该预警向量句已存在，请勿重复添加")
        else:
            # 2. 保存到 MySQL 数据库中以作持久化备份（同步火种）
            new_sample = SafetyWarningSample(
                text=text,
                sample_type=seed_type,
                is_enabled=True
            )
            db.add(new_sample)
            db.commit()
            db.refresh(new_sample)

        # 3. 实时写入 ChromaDB
        query_vector = llm_service.get_embedding(text)
        collection = vector_db.get_collection("safety_warnings_kb")
        
        # 使用固定的 ID 前缀方便识别
        db_sample = db.query(SafetyWarningSample).filter(SafetyWarningSample.text == text).first()
        seed_id = f"db_sample_{db_sample.id}"
        
        collection.add(
            ids=[seed_id],
            embeddings=[query_vector],
            metadatas=[{"type": seed_type, "text": text, "db_id": db_sample.id}],
            documents=[text]
        )
        logger.info(f"成功将安全预警 RAG 种子句同步写入 MySQL 与 ChromaDB (ID: {seed_id})")
        return Result.success(data={"id": seed_id}, message="成功导入数据库与 ChromaDB")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"导入安全预警 RAG 种子句失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@admin_bp.get("/safety-seeds", response_model=Result[list[SafetySeedResponse]])
def get_safety_seeds(db: Session = Depends(get_db)):
    """
    获取 MySQL 中已生效的预警向量样本列表
    """
    try:
        from app.models.safety_warning_sample import SafetyWarningSample
        # 直接从可信 MySQL 数据库拉取
        samples = db.query(SafetyWarningSample).filter(SafetyWarningSample.is_enabled == True).all()
        
        seeds = []
        for s in samples:
            seeds.append(SafetySeedResponse(
                id=f"db_sample_{s.id}",
                type=s.sample_type,
                text=s.text
            ))
        return Result.success(data=seeds, message="获取预警向量样本成功")
    except Exception as e:
        logger.error(f"获取预警向量样本失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@admin_bp.post("/safety-seeds/sync", response_model=Result[dict])
def sync_safety_seeds(db: Session = Depends(get_db)):
    """
    手动触发将 MySQL 里的安全预警样本重新生成向量并同步写入 ChromaDB (常用于更换向量模型后重建索引)
    """
    try:
        from app.database.mysql import sync_warning_samples_to_vector_db
        sync_warning_samples_to_vector_db()
        return Result.success(message="安全预警向量库同步重构成功")
    except Exception as e:
        logger.error(f"手动触发同步预警向量库异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"同步重构失败: {str(e)}")


@admin_bp.post("/knowledge/manual", response_model=Result[dict])
def add_manual_knowledge(data: ManualKnowledgeCreate, db: Session = Depends(get_db)):
    """
    手动录入科普卡片，在 MySQL 记录并分块向量化存入 ChromaDB (psychology_kb 集合)
    """
    title = data.title.strip()
    concept = data.concept.strip()
    tip = data.tip.strip()
    tags = data.tags.strip() if data.tags else ""
    
    if not title or not concept or not tip:
        raise HTTPException(status_code=400, detail="主题、解释和技巧均不能为空")
        
    try:
        # 使用标题 + 内容哈希以去重
        file_hash = hashlib.sha256(f"{title}-{concept}-{tip}".encode('utf-8')).hexdigest()
        
        existing = db.query(KnowledgeImport).filter(KnowledgeImport.file_hash == file_hash).first()
        if existing:
            raise HTTPException(status_code=400, detail="该知识点已存在，请勿重复导入")

        # 生成文本内容以物理写入 MinIO
        manual_text = f"【主题】{title}\n【概念解释】{concept}\n【调节技巧提示】{tip}\n【标签】{tags}"
        manual_bytes = manual_text.encode("utf-8")
        
        object_name = f"manual/{file_hash}.txt"
        
        # 物理上传到 MinIO
        minio_uploaded = storage_service.upload_file(
            object_name=object_name,
            data=manual_bytes,
            content_type="text/plain; charset=utf-8"
        )
        
        bucket_name = storage_service.bucket_name if minio_uploaded else "manual-entry"
            
        # 对概念和调节技巧分别进行二次切片（自动处理单句超长、段落合并等逻辑）
        concept_chunks = split_text_into_chunks(f"【概念解释】{concept}", max_chars=300, overlap=50)
        tip_chunks = split_text_into_chunks(f"【调节技巧提示】{tip}", max_chars=300, overlap=50)
        
        chunks = []
        for c in concept_chunks:
            chunks.append(f"【主题】{title}\n{c}")
        for t in tip_chunks:
            chunks.append(f"【主题】{title}\n{t}")
            
        task = KnowledgeImport(
            file_name=f"[手动录入] {title}",
            file_hash=file_hash,
            minio_bucket=bucket_name,
            minio_object_name=object_name,
            file_size=len(manual_bytes),
            status="processing",
            chunk_count=len(chunks)
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        collection = vector_db.get_collection("psychology_kb")
        
        # 批量向量化导入 ChromaDB
        for idx, chunk_text in enumerate(chunks):
            chunk_vec = llm_service.get_embedding(chunk_text)
            collection.add(
                ids=[f"{task.id}_chunk_{idx}"],
                embeddings=[chunk_vec],
                metadatas=[{"import_id": task.id, "file_name": task.file_name, "chunk_index": idx}],
                documents=[chunk_text]
            )
        
        task.status = "success"
        db.commit()
        logger.info(f"成功将手动知识卡片录入并向量化同步至 ChromaDB (Import ID: {task.id})")
        return Result.success(data={"import_id": task.id}, message="手动卡片录入及 ChromaDB 同步成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"录入手动知识卡片失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"录入失败: {str(e)}")



@admin_bp.post("/knowledge/upload", response_model=Result[dict])
async def upload_knowledge_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    上传 PDF/DOCX/TXT/MD 知识文档，通过统一 MD 管线自动解析、结构化切片并向量化写入 ChromaDB。
    """
    try:
        content_bytes = await file.read()
        file_size = len(content_bytes)

        # 1. 计算哈希去重
        file_hash = hashlib.sha256(content_bytes).hexdigest()
        existing = db.query(KnowledgeImport).filter(
            KnowledgeImport.file_hash == file_hash
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="该文档已导入，请勿重复上传")

        # 2. 创建 MySQL 导入任务记录 (pending)
        bucket_name = storage_service.bucket_name or "local-upload"
        task = KnowledgeImport(
            file_name=file.filename,
            file_hash=file_hash,
            minio_bucket=bucket_name,
            minio_object_name=f"uploads/{file_hash}_{file.filename}",
            file_size=file_size,
            status="processing",
            chunk_count=0
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # 3. 使用新管线入库
        chunk_count = ingest_document(
            file_bytes=content_bytes,
            filename=file.filename,
            file_hash=file_hash,
            task=task,
            db=db
        )

        logger.info(
            f"文档 《{file.filename}》 成功解析并结构化分块向量化！共生成 {chunk_count} 个 Chunks。"
        )
        return Result.success(
            data={"import_id": task.id, "chunk_count": chunk_count},
            message="文档导入及 ChromaDB 同步成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"文档导入向量化失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传处理失败: {str(e)}")


@admin_bp.post("/knowledge/trace", response_model=Result[dict])
def trace_knowledge_retrieval(data: TraceRequest, db: Session = Depends(get_db)):
    """
    全链路调试追踪：输入查询，返回 Query → Embedding → Search → Small-to-Big 展开
    每一步的详细数据，含命中 chunk、章节路径、相似度分数。不调用 LLM。
    """
    try:
        query = data.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="查询内容不能为空")

        trace = trace_retrieval(query)
        return Result.success(data=trace, message="链路追踪完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"链路追踪失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"追踪失败: {str(e)}")


@admin_bp.get("/knowledge/{import_id}/chunks", response_model=Result[dict])
def get_knowledge_chunks(import_id: int, db: Session = Depends(get_db)):
    """
    查看指定导入文档的所有 chunk 及章节结构。
    """
    try:
        task = db.query(KnowledgeImport).filter(KnowledgeImport.id == import_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="文档导入记录不存在")

        collection = vector_db.get_collection("psychology_kb")
        result = collection.get(
            where={"import_id": import_id},
            include=["documents", "metadatas"]
        )

        chunks = []
        if result and result.get("ids"):
            for i, cid in enumerate(result["ids"]):
                meta = result["metadatas"][i] if result["metadatas"] else {}
                chunks.append({
                    "chunk_id": cid,
                    "content": result["documents"][i] if result["documents"] else "",
                    "chunk_index": meta.get("chunk_index", i),
                    "h1": meta.get("h1", ""),
                    "h2": meta.get("h2", ""),
                    "h3": meta.get("h3", ""),
                    "section_id": meta.get("section_id", ""),
                })

        # 按 chunk_index 排序
        chunks.sort(key=lambda c: c["chunk_index"])

        return Result.success(data={
            "import_id": import_id,
            "file_name": task.file_name,
            "total_chunks": len(chunks),
            "chunks": chunks
        }, message="获取 chunk 列表成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 chunk 列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@admin_bp.post("/knowledge/{import_id}/reprocess", response_model=Result[dict])
def reprocess_knowledge(import_id: int, db: Session = Depends(get_db)):
    """
    对已入库文档重新执行 MD 转换 → 切片 → 向量化。

    会删除旧的 ChromaDB 数据并重新生成。适用于切换切片策略或转换器升级后重建索引。
    """
    try:
        task = db.query(KnowledgeImport).filter(KnowledgeImport.id == import_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="文档导入记录不存在")

        # 1. 从 MinIO 读取原始文件
        try:
            from minio import Minio
            client = Minio(
                endpoint=Config.MINIO_ENDPOINT,
                access_key=Config.MINIO_ACCESS_KEY,
                secret_key=Config.MINIO_SECRET_KEY,
                secure=Config.MINIO_SECURE
            )
            response = client.get_object(task.minio_bucket, task.minio_object_name)
            file_bytes = response.read()
            response.close()
            response.release_conn()
        except Exception as e:
            # 如果 MinIO 不可用，尝试从 processed/ MD 文件重建
            logger.warning(f"无法从 MinIO 读取原始文件 ({e})，尝试从 processed/ MD 重建")
            try:
                md_object = f"processed/{task.file_hash}.md"
                response = client.get_object(task.minio_bucket, md_object)
                md_bytes = response.read()
                response.close()
                response.release_conn()
                # 直接从 MD 重新切片
                md_text = md_bytes.decode("utf-8")
                chunks = split_markdown_into_chunks(md_text)
                file_bytes = md_bytes  # 用于后续重存
            except Exception as e2:
                raise HTTPException(
                    status_code=500,
                    detail=f"无法读取原始文件或处理后 MD: {e2}"
                )

        # 2. 删除旧的 ChromaDB 数据
        collection = vector_db.get_collection("psychology_kb")
        try:
            collection.delete(where={"import_id": import_id})
        except Exception:
            pass  # ChromaDB 可能没有 where 过滤删除，忽略

        # 3. 设置状态为 processing
        task.status = "processing"
        task.chunk_count = 0
        db.commit()

        # 4. 重新入库
        chunk_count = ingest_document(
            file_bytes=file_bytes,
            filename=task.file_name,
            file_hash=task.file_hash,
            task=task,
            db=db
        )

        return Result.success(
            data={"import_id": import_id, "chunk_count": chunk_count},
            message=f"重处理完成，生成 {chunk_count} 个 chunks"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"重处理失败 (import_id={import_id}): {str(e)}")
        raise HTTPException(status_code=500, detail=f"重处理失败: {str(e)}")


@admin_bp.get("/knowledge/{import_id}/markdown", response_model=Result[dict])
def get_knowledge_markdown(import_id: int, db: Session = Depends(get_db)):
    """
    获取文档处理后的 Markdown 原文（调试用）。
    从 MinIO processed/ 路径读取。
    """
    try:
        task = db.query(KnowledgeImport).filter(KnowledgeImport.id == import_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="文档导入记录不存在")

        try:
            from minio import Minio
            client = Minio(
                endpoint=Config.MINIO_ENDPOINT,
                access_key=Config.MINIO_ACCESS_KEY,
                secret_key=Config.MINIO_SECRET_KEY,
                secure=Config.MINIO_SECURE
            )
            md_object = f"processed/{task.file_hash}.md"
            response = client.get_object(task.minio_bucket, md_object)
            md_text = response.read().decode("utf-8")
            response.close()
            response.release_conn()
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"无法读取处理后的 Markdown 文件: {str(e)}"
            )

        return Result.success(data={
            "import_id": import_id,
            "file_name": task.file_name,
            "markdown": md_text
        }, message="获取 Markdown 原文成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 Markdown 原文失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@admin_bp.get("/knowledge", response_model=Result[dict])
def get_knowledge_imports(
    page: int = Query(1, ge=1, description="当前页码"),
    size: int = Query(10, ge=1, le=100, description="每页限制"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db)
):
    """
    分页查询已导入的科普知识库文档/表单记录列表
    """
    try:
        query = db.query(KnowledgeImport)
        if keyword:
            query = query.filter(KnowledgeImport.file_name.like(f"%{keyword}%"))
            
        query = query.order_by(KnowledgeImport.created_at.desc())
        
        total = query.count()
        offset = (page - 1) * size
        imports = query.offset(offset).limit(size).all()
        
        items = [imp.to_dict() for imp in imports]
        
        return Result.success(data={
            "total": total,
            "page": page,
            "size": size,
            "items": items
        }, message="获取知识库导入列表成功")
    except Exception as e:
        logger.error(f"获取知识库列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@admin_bp.get("/knowledge/search", response_model=Result[list])
def search_knowledge_base(
    query: str = Query(..., description="检索关键词"),
    limit: int = Query(3, ge=1, le=10, description="最大返回条数"),
    db: Session = Depends(get_db)
):
    """
    语义检索测试：在 ChromaDB 中测试知识库检索效果，查看匹配的 Chunks 文本段落与相似度分数
    """
    try:
        from app.services.rag import rag_service
        results = rag_service.search_knowledge(db, query, limit=limit)
        return Result.success(data=results, message="检索成功")
    except Exception as e:
        logger.error(f"知识库检索测试失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")
