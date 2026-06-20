# -*- coding: utf-8 -*-
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import Config
import logging

logger = logging.getLogger(__name__)

# 创建 SQLAlchemy 引擎
engine = create_engine(
    Config.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,  # 每次使用连接前进行 ping 测试，防止连接超时断开
    pool_recycle=3600    # 一小时自动回收连接
)

# 创建本地会话类
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明式模型基类
Base = declarative_base()

def get_db():
    """
    FastAPI 依赖注入（Depends）生成器函数。
    为每一个请求单独生成一个会话，请求结束时自动关闭会话。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 默认的高危自残敏感词汇（CRISIS）
DEFAULT_CRISIS_KEYWORDS = [
    "自杀", "想死", "不想活了", "不活了", "想结束生命", "结束生命", "离开这个世界", 
    "活着太痛苦了", "痛苦的解脱", "活着没意思", "人间蒸发", "写遗书", "遗嘱", 
    "怎么死不痛苦", "怎么死比较快", "吞药", "吃安眠药", "服毒", "吃药自残", "割腕", 
    "割颈", "跳楼", "跳河", "跳海", "上吊", "烧炭", "自残", "寻死", "想跳下去", 
    "去死吧", "终结生命"
]

# 默认的违规暴力敏感词汇（SAFETY）
DEFAULT_SAFETY_KEYWORDS = [
    "制造炸弹", "炸学校", "制作毒药", "制毒", "化学毒剂", "买枪", "买大马刀", "买刀", 
    "杀人", "去报复", "报复制药", "砍死他", "弄死你", "毒死他", "下毒", "同归于尽", 
    "暴力报复", "恐怖袭击", "垃圾AI", "智障AI", "傻逼", "蠢货", "去死", "裸聊"
]

def seed_safety_keywords_from_list():
    """
    自默认 Python 列表向数据库 safety_keywords 表初始化填充数据（仅当表中无数据时生效）
    """
    db = SessionLocal()
    try:
        from app.models.safety_keyword import SafetyKeyword
        # 仅当表数据为空时，导入默认配置
        if db.query(SafetyKeyword).count() == 0:
            for w in DEFAULT_CRISIS_KEYWORDS:
                if w.strip():
                    db.add(SafetyKeyword(word=w.strip(), word_type="high_risk", is_enabled=True))
            for w in DEFAULT_SAFETY_KEYWORDS:
                if w.strip():
                    db.add(SafetyKeyword(word=w.strip(), word_type="violation", is_enabled=True))
            db.commit()
            logger.info(f"已成功将默认词库导入数据库。高危词 {len(DEFAULT_CRISIS_KEYWORDS)}个，违规词 {len(DEFAULT_SAFETY_KEYWORDS)}个。")
    except Exception as e:
        db.rollback()
        logger.error(f"从默认列表初始化导入敏感词数据异常: {str(e)}")
    finally:
        db.close()


def seed_safety_warning_samples_from_list():
    """
    自默认 Python 列表向数据库 safety_warning_samples 表初始化填充数据（仅当表中无数据时生效）
    """
    db = SessionLocal()
    try:
        from app.models.safety_warning_sample import SafetyWarningSample
        if db.query(SafetyWarningSample).count() == 0:
            default_samples = [
                {"text": "好像离开这个世界啊", "sample_type": "high_risk"},
                {"text": "卖片，裸聊加我进群", "sample_type": "violation"}
            ]
            for s in default_samples:
                db.add(SafetyWarningSample(
                    text=s["text"],
                    sample_type=s["sample_type"],
                    is_enabled=True
                ))
            db.commit()
            logger.info("已成功将默认安全预警 RAG 向量种子样本导入数据库。")
    except Exception as e:
        db.rollback()
        logger.error(f"从默认列表初始化导入安全预警向量样本数据异常: {str(e)}")
    finally:
        db.close()


def init_mysql():
    """
    在应用启动时初始化并建表
    """
    try:
        # 创建所有表（如果它们不存在的话）
        # 注意：需要在此处导入所有 model，否则 create_all 不会生效
        from app.models import User, UserProfile, ChatSession, ChatMessage, KnowledgeImport, SafetyKeyword, SecurityActivityLog, SafetyWarningSample
        Base.metadata.create_all(bind=engine)
        logger.info("MySQL 数据库表结构同步完成。")
        seed_safety_keywords_from_list()
        seed_safety_warning_samples_from_list()
        
        # 导入内存热加载服务并运行热更新
        from app.services.intent import intent_service
        intent_service.load_safety_rules()
    except Exception as e:
        logger.error(f"MySQL 数据库表初始化建表失败: {str(e)}")


def sync_warning_samples_to_vector_db():
    """
    将 MySQL 中的所有活跃预警向量样本同步到 ChromaDB 的 safety_warnings_kb 集合中
    """
    db = SessionLocal()
    try:
        from app.models.safety_warning_sample import SafetyWarningSample
        from app.database.vector import vector_db
        from app.services.llm import llm_service

        logger.info("开始从 MySQL 同步安全预警 RAG 向量样本到 ChromaDB...")
        
        # 1. 获取所有启用中的样本
        samples = db.query(SafetyWarningSample).filter(SafetyWarningSample.is_enabled == True).all()
        
        # 2. 获取 ChromaDB 集合
        collection = vector_db.get_collection("safety_warnings_kb")
        
        # 3. 清空原有 ChromaDB 数据以防残留或因模型切换引起的冲突
        results = collection.get()
        if results and results.get("ids"):
            collection.delete(ids=results["ids"])
            logger.info(f"已清空 ChromaDB 中的旧预警向量数据，共 {len(results['ids'])} 条记录。")

        if not samples:
            logger.info("MySQL 中无活跃预警样本，同步结束。")
            return

        # 4. 重新计算向量并写入 ChromaDB
        ids = []
        embeddings = []
        metadatas = []
        documents = []

        for s in samples:
            # 文本向量化
            vec = llm_service.get_embedding(s.text)
            ids.append(f"db_sample_{s.id}")
            embeddings.append(vec)
            metadatas.append({"type": s.sample_type, "text": s.text, "db_id": s.id})
            documents.append(s.text)

        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )
        logger.info(f"成功同步 {len(samples)} 个安全预警 RAG 向量样本至 ChromaDB！")
    except Exception as e:
        logger.error(f"同步预警 RAG 向量到 ChromaDB 发生异常: {str(e)}")
    finally:
        db.close()

        # 捕获异常，方便在无数据库环境下的开发测试
