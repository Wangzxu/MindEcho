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
from app.services.rag import extract_text_from_file, split_text_into_chunks

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


@admin_bp.post("/safety-seeds", response_model=Result[dict])
def add_safety_seed(data: SafetySeedCreate):
    """
    添加安全预警 RAG 向量种子句到 ChromaDB (safety_warnings_kb 集合)
    """
    text = data.text.strip()
    seed_type = data.type.strip()
    if not text:
        raise HTTPException(status_code=400, detail="内容不能为空")
    if seed_type not in ["high_risk", "violation"]:
        raise HTTPException(status_code=400, detail="类型必须为 high_risk 或 violation")
        
    try:
        query_vector = llm_service.get_embedding(text)
        collection = vector_db.get_collection("safety_warnings_kb")
        seed_id = str(uuid.uuid4())
        collection.add(
            ids=[seed_id],
            embeddings=[query_vector],
            metadatas=[{"type": seed_type, "text": text}],
            documents=[text]
        )
        logger.info(f"成功将安全预警 RAG 种子句写入 ChromaDB (ID: {seed_id})")
        return Result.success(data={"id": seed_id}, message="成功导入 ChromaDB")
    except Exception as e:
        logger.error(f"导入安全预警 RAG 种子句失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@admin_bp.get("/safety-seeds", response_model=Result[list[SafetySeedResponse]])
def get_safety_seeds():
    """
    获取 ChromaDB 中已生效的预警向量样本列表
    """
    try:
        collection = vector_db.get_collection("safety_warnings_kb")
        results = collection.get()
        
        seeds = []
        if results and results.get("ids"):
            ids = results["ids"]
            metadatas = results["metadatas"]
            for idx, sid in enumerate(ids):
                meta = metadatas[idx] or {}
                seeds.append(SafetySeedResponse(
                    id=sid,
                    type=meta.get("type", "high_risk"),
                    text=meta.get("text", "")
                ))
        return Result.success(data=seeds, message="获取预警向量样本成功")
    except Exception as e:
        logger.error(f"获取预警向量样本失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


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
    上传 PDF/TXT/Word 知识文档，自动解析切片并向量化写入 ChromaDB
    """
    try:
        content_bytes = await file.read()
        file_size = len(content_bytes)
        
        # 1. 计算哈希去重
        file_hash = hashlib.sha256(content_bytes).hexdigest()
        
        existing = db.query(KnowledgeImport).filter(KnowledgeImport.file_hash == file_hash).first()
        if existing:
            raise HTTPException(status_code=400, detail="该文档已导入，请勿重复上传")
            
        # 2. 提取文本内容
        text = extract_text_from_file(file, content_bytes)
        text = text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="文档内容为空或无法提取文本")

        object_name = f"uploads/{file_hash}_{file.filename}"
        
        # 物理上传至 MinIO
        minio_uploaded = storage_service.upload_file(
            object_name=object_name,
            data=content_bytes,
            content_type=file.content_type or "application/octet-stream"
        )
        
        bucket_name = storage_service.bucket_name if minio_uploaded else "local-upload"
            
        # 3. 创建 MySQL 导入任务记录
        task = KnowledgeImport(
            file_name=file.filename,
            file_hash=file_hash,
            minio_bucket=bucket_name,
            minio_object_name=object_name,
            file_size=file_size,
            status="processing",
            chunk_count=0
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # 4. 对文本进行智能二次切片 (Chunking)，限制块大小并在超长时滑动切分句段
        chunks = split_text_into_chunks(text, max_chars=300, overlap=50)
            
        # 5. 生成 Embedding 并写入 ChromaDB (psychology_kb)
        collection = vector_db.get_collection("psychology_kb")
        
        for idx, chunk_text in enumerate(chunks):
            context_text = f"【来源文件】{file.filename}\n{chunk_text}"
            chunk_vec = llm_service.get_embedding(context_text)
            collection.add(
                ids=[f"{task.id}_chunk_{idx}"],
                embeddings=[chunk_vec],
                metadatas=[{"import_id": task.id, "file_name": file.filename, "chunk_index": idx}],
                documents=[context_text]
            )
            
        task.chunk_count = len(chunks)
        task.status = "success"
        db.commit()
        
        logger.info(f"文档 《{file.filename}》 成功解析并分块向量化！共生成 {len(chunks)} 个 Chunks。")
        return Result.success(data={"import_id": task.id, "chunk_count": len(chunks)}, message="文档导入及 ChromaDB 同步成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"文档导入向量化失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传处理失败: {str(e)}")


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
