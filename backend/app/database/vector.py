# -*- coding: utf-8 -*-
import os
import chromadb
from config import Config
import logging

logger = logging.getLogger(__name__)

class VectorDBClient:
    """ChromaDB 向量数据库客户端封装"""
    def __init__(self):
        self.client = None

    def init_db(self):
        """根据 Config 初始化向量数据库连接"""
        persist_dir = Config.CHROMA_PERSIST_DIRECTORY
        
        # 确保目录存在
        os.makedirs(persist_dir, exist_ok=True)
        
        try:
            # 初始化持久化 ChromaDB 客户端
            self.client = chromadb.PersistentClient(path=persist_dir)
            logger.info(f"ChromaDB 持久化客户端连接成功，路径: {persist_dir}")
        except Exception as e:
            logger.error(f"ChromaDB 客户端连接失败: {str(e)}。尝试切换至内存临时客户端 (EphemeralClient)")
            # 降级方案：使用内存数据库
            self.client = chromadb.EphemeralClient()

        # 预先定义并初始化所需的两个核心向量集合，保证在服务启动时即创建完毕
        try:
            self.get_collection("safety_warnings_kb")
            self.get_collection("psychology_kb")
            logger.info("ChromaDB 核心向量集合 [safety_warnings_kb, psychology_kb] 初始化定义完成 (度量空间: cosine)。")
        except Exception as e:
            logger.error(f"ChromaDB 核心向量集合定义失败: {str(e)}")

    def get_collection(self, name="psychology_kb"):
        """获取或创建向量集合"""
        if not self.client:
            self.init_db()
        # 显式指定向量空间的度量标准为余弦距离 (cosine)
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )

# 导出单例
vector_db = VectorDBClient()
