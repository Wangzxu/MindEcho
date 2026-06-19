# -*- coding: utf-8 -*-
import logging
import io
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.database.vector import vector_db
from app.models import KnowledgeImport
from app.services.llm import llm_service

logger = logging.getLogger(__name__)

from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_text_into_chunks(text: str, max_chars: int = 300, overlap: int = 50) -> list[str]:
    """
    将文档大文本切分为固定长度的段落切片（Chunks），使用 LangChain 的 RecursiveCharacterTextSplitter，
    能够智能地根据中文段落和标点进行级联切割，防止单句过长并保持语义饱满。
    """
    if not text:
        return []
    
    # 初始化 LangChain 递归字符文本切片器
    # 默认分割符号优先级：\n\n, \n, " ", "" (即双换行、单换行、空格、单字符)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chars,
        chunk_overlap=overlap,
        length_function=len,
        is_separator_regex=False
    )
    return splitter.split_text(text)


def extract_text_from_file(file: UploadFile, file_content: bytes) -> str:
    """
    自上传的文件（TXT, PDF, Word）中提取文本内容，带依赖防崩溃隔离
    """
    filename = file.filename.lower()
    if filename.endswith(".txt"):
        return file_content.decode("utf-8", errors="ignore")
    elif filename.endswith(".pdf"):
        try:
            import pypdf
            pdf_reader = pypdf.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
            return text
        except ImportError:
            raise HTTPException(
                status_code=400,
                detail="系统暂未安装 PDF 解析依赖 pypdf，请联系管理员执行 pip install pypdf 安装"
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF 解析失败: {str(e)}")
    elif filename.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_content))
            text = ""
            for para in doc.paragraphs:
                text += para.text + "\n"
            return text
        except ImportError:
            raise HTTPException(
                status_code=400,
                detail="系统暂未安装 Word 解析依赖 python-docx，请联系管理员执行 pip install python-docx 安装"
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Word 文档解析失败: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="不支持的文件格式，仅支持 .txt, .pdf, .docx")


class RAGService:
    """RAG (检索增强生成) 检索与知识管理服务 (云原生架构版)"""

    def __init__(self, collection_name="psychology_kb"):
        self.collection_name = collection_name

    def add_knowledge_import_task(self, db: Session, file_name: str, file_hash: str, minio_bucket: str, minio_object_name: str, file_size: int):
        """
        管理端调用：在 MySQL 中存储 RAG 原始文档导入任务的记录 (作为冷备份与重建索引的数据火种)
        """
        task = db.query(KnowledgeImport).filter(KnowledgeImport.file_hash == file_hash).first()
        if task:
            task.file_name = file_name
            task.minio_bucket = minio_bucket
            task.minio_object_name = minio_object_name
            task.file_size = file_size
            task.status = "pending"
            logger.info(f"更新 MySQL 中的 RAG 导入任务: {file_name}")
        else:
            task = KnowledgeImport(
                file_name=file_name,
                file_hash=file_hash,
                minio_bucket=minio_bucket,
                minio_object_name=minio_object_name,
                file_size=file_size,
                status="pending"
            )
            db.add(task)
            logger.info(f"新增 MySQL 中的 RAG 导入任务: {file_name}")
            
        db.commit()
        db.refresh(task)
        return task

    def search_knowledge(self, db: Session, query: str, limit=2):
        """
        云原生 RAG 检索：直接从 ChromaDB 检索返回 Chunks 文本段落
        无需从 MySQL 查询大文本原文，因为大文本段落已经自治存储在 Chroma 向量集合中。
        """
        cards = []
        try:
            # 1. 对查询进行向量化
            query_vector = llm_service.get_embedding(query)
            
            # 2. 从 ChromaDB 检索文本块与元数据
            collection = vector_db.get_collection(self.collection_name)
            results = collection.query(
                query_embeddings=[query_vector],
                n_results=limit
            )

            if results and results.get("ids") and len(results["ids"][0]) > 0:
                ids = results["ids"][0]
                documents = results["documents"][0]
                metadatas = results["metadatas"][0]
                distances = results["distances"][0] if "distances" in results else [0.0] * len(ids)
                
                for idx, chunk_id in enumerate(ids):
                    cards.append({
                        "chunk_id": chunk_id,
                        "content": documents[idx],
                        "file_name": metadatas[idx].get("file_name", "未知文件"),
                        "import_id": metadatas[idx].get("import_id"),
                        "score": float(1.0 - distances[idx])
                    })
        except Exception as e:
            logger.error(f"ChromaDB 向量检索发生异常: {str(e)}")

        return cards

# 导出单例
rag_service = RAGService()
