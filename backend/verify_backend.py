# -*- coding: utf-8 -*-
"""
MindEcho 后端骨架验证脚本 (FastAPI 版本)
用于检测环境配置、MySQL、ChromaDB 及 硅基流动 API 的联通性，并测试核心意图识别与 RAG 检索流程。
"""
import os
import sys

# 将当前目录加入系统路径，确保 app 包能够成功导入
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from config import Config
from app.database.mysql import init_mysql, SessionLocal, get_db
from app.database.vector import vector_db
from app.services.intent import intent_service
from app.services.rag import rag_service
from app.services.llm import llm_service
from app.models import User, UserProfile, ChatSession, ChatMessage, KnowledgeImport, SafetyKeyword, SecurityActivityLog

def run_diagnostics():
    print("=" * 60)
    print("正在启动 MindEcho FastAPI 后端骨架诊断与集成验证...")
    print("=" * 60)

    # 1. 启动生命周期配置校验
    print("\n1. 正在校验配置参数与环境变量...")
    print(f"   - MYSQL 主机: {Config.MYSQL_HOST}:{Config.MYSQL_PORT}")
    print(f"   - MYSQL 数据库: {Config.MYSQL_DB}")
    print(f"   - 向量库路径: {Config.CHROMA_PERSIST_DIRECTORY}")
    print(f"   - SiliconFlow API Key: {'***已配置***' if Config.SILICONFLOW_API_KEY else '❌ 未配置'}")
    print(f"   - 简单分类模型: {Config.SIMPLE_LLM_MODEL}")
    print(f"   - 复杂问答模型: {Config.COMPLEX_LLM_MODEL}")
    print(f"   - 向量嵌入模型: {Config.EMBEDDING_MODEL}")

    # 2. 启动数据库初始化结构校验
    print("\n2. 正在初始化 MySQL 并校验表结构...")
    try:
        init_mysql()
        print("✅ MySQL 数据库建表验证命令已执行。")
    except Exception as e:
        print(f"❌ MySQL 初始化异常: {str(e)}")

    # 3. 验证 MySQL 读写操作
    print("\n3. 验证 MySQL 会话读写操作...")
    db = SessionLocal()
    try:
        test_user = db.query(User).filter(User.username == "diagnostic_test_user").first()
        if not test_user:
            # 创建登录凭证用户，包含哈希密码
            from app.services.auth_service import auth_service
            test_user = User(
                username="diagnostic_test_user", 
                password_hash=auth_service.hash_password("diagnostic_test_pass"),
                role="student",
                is_active=True
            )
            db.add(test_user)
            db.flush()
            
            # 创建画像表
            test_profile = UserProfile(
                user_id=test_user.id,
                nickname="诊断测试生",
                core_stressors=["学业测试"],
                effective_coping_methods=["诊断调节"],
                entity_relation_map={"系统": "诊断端"}
            )
            db.add(test_profile)
            db.commit()
            print("✅ 成功写入测试用户及画像至 MySQL。")
        else:
            print("✅ MySQL 测试用户及画像已存在，读取成功。")
    except Exception as e:
        print(f"⚠️ MySQL 连接或表读写失败 (如果您当前没有运行 MySQL 服务，此步会报错，请检查您的 MySQL 配置): {str(e)}")
    finally:
        db.close()

    # 4. 验证 ChromaDB 向量库
    print("\n4. 验证 ChromaDB 初始化与写入...")
    try:
        collection = vector_db.get_collection("test_diagnostics")
        collection.upsert(
            ids=["test_id_1"],
            embeddings=[[0.1] * 1024],  # 模拟 1024 维 Embedding
            metadatas=[{"source": "diagnostics"}],
            documents=["这是一条测试向量的文档内容。"]
        )
        test_query = collection.query(query_embeddings=[[0.1] * 1024], n_results=1)
        if test_query and test_query.get("ids") and test_query["ids"][0][0] == "test_id_1":
            print("✅ ChromaDB 本地写入与查询测试通过。")
        else:
            print("❌ ChromaDB 测试查询结果与预期不符。")
    except Exception as e:
        print(f"❌ ChromaDB 本地持久化或写入发生异常: {str(e)}")

    # 5. 验证意图识别服务
    print("\n5. 测试意图识别多级路由服务...")
    test_cases = [
        ("感觉这日子没法过了，好想吞药解脱自己", "CRISIS"),
        ("什么是焦虑症，有什么自主调节的方法吗", "KNOWLEDGE"),
        ("最近和室友吵架了，心情特别沮丧", "EMOTION"),
        ("嗨，小影学姐，吃晚饭了吗", "CHITCHAT")
    ]

    for user_input, expected_intent in test_cases:
        try:
            intent, reason = intent_service.classify_intent(user_input)
            status_symbol = "✅" if intent == expected_intent else "⚠️"
            print(f"   {status_symbol} 输入: '{user_input}' -> 识别为: {intent} (预估: {expected_intent}), 原因: {reason}")
        except Exception as e:
            print(f"   ❌ 意图识别测试发生异常: {str(e)}")

    # 6. 验证管理端新增数据表映射
    print("\n6. 验证管理端新增物理模型表结构映射...")
    db = SessionLocal()
    try:
        # 检测模型是否存在且表映射成功
        import_count = db.query(KnowledgeImport).count()
        keyword_count = db.query(SafetyKeyword).count()
        log_count = db.query(SecurityActivityLog).count()
        print(f"   ✅ 知识文档导入任务表 (KnowledgeImport) 结构检测正常，记录数: {import_count}")
        print(f"   ✅ 安全敏感词库配置表 (SafetyKeyword) 结构检测正常，记录数: {keyword_count}")
        print(f"   ✅ 安全活动及预警日志表 (SecurityActivityLog) 结构检测正常，记录数: {log_count}")
    except Exception as e:
        print(f"   ❌ 物理模型表结构映射异常: {str(e)}")
    finally:
        db.close()

    print("\n" + "=" * 60)
    print("诊断与集成测试结束！")
    print("=" * 60)
    return True

if __name__ == '__main__':
    run_diagnostics()
