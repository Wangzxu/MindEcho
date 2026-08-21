# -*- coding: utf-8 -*-
"""
RAG 知识库服务 — 统一 Markdown 管线版。

架构流水线：
  原始文件 → converter.convert_to_markdown() → Markdown
  → MarkdownHeaderTextSplitter (H1/H2/H3 边界)
  → RecursiveCharacterTextSplitter (800 字符上限)
  → Embedding → ChromaDB (子 chunk 索引 + 父文档 metadata)

检索策略 (Small-to-Big)：
  用户查询 → Embedding → ChromaDB top-3 子 chunk
  → 每个子 chunk 展开为所属 H2 父文档 → 去重 → top-2
  → 注入 LLM (≤ 1300 tokens)
"""

import io
import logging
from typing import List, Dict, Any, Optional, Tuple

from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter

from app.database.vector import vector_db
from app.models import KnowledgeImport
from app.services.llm import llm_service
from app.services.storage import storage_service
from app.services.converter import convert_to_markdown
from config import Config

logger = logging.getLogger(__name__)

# ============================================================================
# 常量
# ============================================================================

CHUNK_SIZE = 800        # 子 chunk 最大字符数
CHUNK_OVERLAP = 100     # 重叠字符数
HEADERS_TO_SPLIT = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]
TOP_K_CHILDREN = 3      # 检索时返回 top-3 子 chunk
TOP_K_PARENTS = 2       # 父文档展开后最多 2 个
MAX_RETRIEVAL_CHARS = 1000  # 控制在 ~1300 tokens 以内
COLLECTION_NAME = "psychology_kb"

# ============================================================================
# 切片
# ============================================================================


def split_markdown_into_chunks(
    md_text: str,
    max_chars: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
) -> List[Dict[str, Any]]:
    """
    两层切片：先按 H1/H2/H3 边界切分（保留结构），再对过长段落做二级切分。

    Returns:
        [
            {
                "content": "### 认知重构技术\n认知重构是CBT...",
                "metadata": {
                    "h1": "认知行为疗法",
                    "h2": "治疗方法",
                    "h3": "认知重构技术",
                    "section_id": "doc_sec_0",
                    "parent_content": "## 治疗方法\n### 认知重构技术\n...(完整父文档)"
                }
            },
            ...
        ]
    """
    if not md_text or not md_text.strip():
        return []

    # 第一层：Markdown 标题边界切分
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT,
        strip_headers=False,  # 保留标题文本在 chunk 中
    )
    md_splits = md_splitter.split_text(md_text)

    # 构建父文档索引: 将相同 H2 的所有 H3 子块归组
    # key = (h1, h2), value = 完整拼接文本
    parent_sections: Dict[Tuple[str, str], str] = {}
    for split in md_splits:
        h1 = split.metadata.get("h1", "") or ""
        h2 = split.metadata.get("h2", "") or ""
        section_key = (h1, h2)
        content = split.page_content
        if section_key not in parent_sections:
            header_line = ""
            if h1:
                header_line += f"# {h1}\n"
            if h2:
                header_line += f"## {h2}\n"
            parent_sections[section_key] = header_line + content
        else:
            parent_sections[section_key] += "\n\n" + content

    # 第二层：对过长的子块做 RecursiveCharacterTextSplitter 二级切分
    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chars,
        chunk_overlap=overlap,
        length_function=len,
        is_separator_regex=False,
    )

    chunks = []
    section_counter = 0

    for section_key, parent_content in parent_sections.items():
        h1, h2 = section_key

        # 按 H3 边界子切分：将 H2 父文档按 "### " 拆分为独立 H3 段，
        # 再对每段做二级字符切分，确保 chunk 边界不跨 H3 标题
        h3_segments = parent_content.split("\n### ")

        for seg_idx, seg in enumerate(h3_segments):
            if seg_idx == 0:
                # 第一段：H1/H2 标题 + 可能的 H2 级介绍文本（无 H3 标题）
                h3 = ""
                seg_text = seg
            else:
                # 后续段：各自对应一个 H3 小节，还原 "### " 前缀
                h3_line_end = seg.find("\n")
                h3 = seg[:h3_line_end].strip() if h3_line_end > 0 else seg.strip()
                seg_text = "### " + seg

            if not seg_text.strip():
                continue

            # 对每个 H3 段做二级字符切分（控制单块不超过 max_chars）
            sub_chunks = char_splitter.split_text(seg_text)
            for chunk_text in sub_chunks:
                chunks.append({
                    "content": chunk_text.strip(),
                    "metadata": {
                        "h1": h1,
                        "h2": h2,
                        "h3": h3,
                        "section_id": f"sec_{section_counter}",
                        "parent_content": parent_content.strip(),
                    }
                })
        section_counter += 1

    return chunks


# ============================================================================
# 兼容旧接口：extract_text_from_file 保留 fallback 行为
# ============================================================================


def extract_text_from_file(file: UploadFile, file_content: bytes) -> str:
    """
    旧接口保留，用于非 MD 管线的降级路径。
    新代码应使用 convert_to_markdown()。
    """
    filename = file.filename.lower() if file.filename else ""
    if filename.endswith(".txt") or filename.endswith(".md"):
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
        raise HTTPException(status_code=400, detail="不支持的文件格式，仅支持 .txt, .md, .pdf, .docx")


# ============================================================================
# 旧 split_text_into_chunks 保留向后兼容（手动卡片录入仍使用）
# ============================================================================


def split_text_into_chunks(text: str, max_chars: int = 300, overlap: int = 50) -> List[str]:
    """旧版纯文本切片器，保留用于手动卡片录入等非 MD 场景"""
    if not text:
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chars,
        chunk_overlap=overlap,
        length_function=len,
        is_separator_regex=False
    )
    return splitter.split_text(text)


# ============================================================================
# 入库流水线
# ============================================================================


def ingest_document(
    file_bytes: bytes,
    filename: str,
    file_hash: str,
    task: KnowledgeImport,
    db: Session
) -> int:
    """
    完整入库流水线：原始文件 → MD 转换 → 切片 → Embedding → ChromaDB。

    Args:
        file_bytes: 原始文件二进制
        filename: 原始文件名
        file_hash: SHA256 哈希
        task: MySQL 中的 KnowledgeImport 记录（已 commit 的 pending 状态）
        db: 数据库会话

    Returns:
        chunk_count: 生成的 chunk 数量
    """
    # 1. 转为 Markdown
    md_text, conv_meta = convert_to_markdown(file_bytes, filename)
    if not md_text:
        raise ValueError("文档转换后内容为空")

    # 2. MinIO 存储原始文件 + 处理后的 MD（MinIO 为备份，失败不阻断主流程）
    raw_uploaded = storage_service.upload_file(
        object_name=f"uploads/{file_hash}_{filename}",
        data=file_bytes,
        content_type="application/octet-stream"
    )
    if not raw_uploaded:
        logger.warning(
            f"原始文件 《{filename}》 上传 MinIO 失败，ChromaDB 仍为主存储，"
            f"建议检查 MinIO 服务状态后手动补传"
        )

    md_bytes = md_text.encode("utf-8")
    md_uploaded = storage_service.upload_file(
        object_name=f"processed/{file_hash}.md",
        data=md_bytes,
        content_type="text/markdown; charset=utf-8"
    )
    if not md_uploaded:
        logger.warning(
            f"处理后 Markdown 《{filename}》 上传 MinIO 失败，"
            f"原始文件可通过 converter 重新生成，建议检查 MinIO 服务状态"
        )

    # 3. 结构化切片
    chunks = split_markdown_into_chunks(md_text, max_chars=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    if not chunks:
        raise ValueError("文档切片后无有效内容")

    # 4. 批量嵌入 + 写入 ChromaDB（逐批更新进度，避免大文档长时间无反馈）
    collection = vector_db.get_collection(COLLECTION_NAME)

    ids = []
    embeddings = []
    documents = []
    metadatas = []

    # 构造上下文增强文本
    context_texts = []
    for idx, chunk in enumerate(chunks):
        h_path_parts = [p for p in [chunk["metadata"]["h1"],
                                     chunk["metadata"]["h2"],
                                     chunk["metadata"]["h3"]] if p]
        h_path = " > ".join(h_path_parts) if h_path_parts else filename
        context_texts.append(f"【{h_path}】\n{chunk['content']}")

    # 分批嵌入：每批 50 条，批间回写 processed_chunks 进度
    EMBED_PROGRESS_BATCH = 50
    for start in range(0, len(context_texts), EMBED_PROGRESS_BATCH):
        batch_texts = context_texts[start:start + EMBED_PROGRESS_BATCH]
        batch_vecs = llm_service.batch_embed(batch_texts)

        for j, (ctx, vec) in enumerate(zip(batch_texts, batch_vecs)):
            idx = start + j
            chunk = chunks[idx]
            ids.append(f"{task.id}_chunk_{idx}")
            embeddings.append(vec)
            documents.append(ctx)
            metadatas.append({
                "import_id": task.id,
                "file_name": filename,
                "chunk_index": idx,
                "h1": chunk["metadata"]["h1"],
                "h2": chunk["metadata"]["h2"],
                "h3": chunk["metadata"]["h3"],
                "section_id": chunk["metadata"]["section_id"],
                "parent_content": chunk["metadata"]["parent_content"],
                "converter": conv_meta.get("converter", "unknown"),
            })

        # 进度回写（每完成一批 commit 一次，失败可定位到进度）
        task.processed_chunks = min(start + len(batch_texts), len(chunks))
        db.commit()

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

    # 5. 更新 MySQL 任务状态
    task.chunk_count = len(chunks)
    task.processed_chunks = len(chunks)
    task.status = "success"
    db.commit()

    logger.info(f"文档 《{filename}》 入库完成：{len(chunks)} chunks（转换器: {conv_meta.get('converter')})")
    return len(chunks)


# ============================================================================
# Small-to-Big 检索
# ============================================================================


def retrieve_with_context(
    query: str,
    top_k: int = TOP_K_PARENTS,
    query_vector: Optional[List[float]] = None
) -> List[Dict[str, Any]]:
    """
    Small-to-Big 检索：

    1. 向量检索 top-3 子 chunk
    2. 每个子 chunk 展开为所属 H2 父文档
    3. 按 section_id 去重
    4. 截断控制总字符数 ≤ MAX_RETRIEVAL_CHARS

    Returns:
        [
            {
                "content": "(父文档完整小节)",
                "file_name": "CBT综述.pdf",
                "h1": "认知行为疗法",
                "h2": "临床应用",
                "score": 0.89,
                "source_chunks": [{"chunk_id": "42_5", "content": "...", "score": 0.89}]
            },
            ...
        ]
    """
    if query_vector is None:
        query_vector = llm_service.get_embedding(query)

    collection = vector_db.get_collection(COLLECTION_NAME)
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=TOP_K_CHILDREN
    )

    if not results or not results.get("ids") or len(results["ids"][0]) == 0:
        return []

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0] if "distances" in results else [0.0] * len(ids)

    # 收集所有命中的子 chunk → 按 section_id 去重 → 展开为父文档
    seen_sections = set()
    parent_results = []

    for idx, chunk_id in enumerate(ids):
        meta = metadatas[idx]
        section_id = meta.get("section_id", chunk_id)
        if section_id in seen_sections:
            continue
        seen_sections.add(section_id)

        parent_content = meta.get("parent_content", documents[idx])
        parent_results.append({
            "content": parent_content,
            "file_name": meta.get("file_name", "未知"),
            "h1": meta.get("h1", ""),
            "h2": meta.get("h2", ""),
            "score": float(1.0 - distances[idx]),
            "source_chunks": [{
                "chunk_id": chunk_id,
                "content": documents[idx],
                "score": float(1.0 - distances[idx])
            }]
        })

    # 截断控制总长
    total_chars = 0
    truncated = []
    for pr in parent_results[:top_k]:
        if total_chars + len(pr["content"]) > MAX_RETRIEVAL_CHARS:
            remaining = MAX_RETRIEVAL_CHARS - total_chars
            if remaining > 200:
                pr["content"] = pr["content"][:remaining] + "\n...(截断)"
                truncated.append(pr)
            break
        truncated.append(pr)
        total_chars += len(pr["content"])

    return truncated


# ============================================================================
# 全链路追踪（供前端可视化）
# ============================================================================


def trace_retrieval(query: str) -> dict:
    """
    全链路追踪：执行检索但不调用 LLM，返回每一步的中间数据。
    用于前端链路调试 Tab。
    """
    import time

    trace = {
        "query": query,
        "steps": []
    }

    # Step 1: Query Rewriting 查询重写
    t0 = time.time()
    rewritten_query = llm_service.rewrite_query(query)
    rewrite_time_ms = int((time.time() - t0) * 1000)
    trace["steps"].append({
        "name": "查询重写 (Query Rewriting)",
        "original": query,
        "rewritten": rewritten_query,
        "duration_ms": rewrite_time_ms
    })

    # Step 2: Embedding（对改写后的查询向量化）
    t0 = time.time()
    query_vector = llm_service.get_embedding(rewritten_query)
    embedding_time_ms = int((time.time() - t0) * 1000)
    trace["steps"].append({
        "name": "Embedding 向量化",
        "model": Config.EMBEDDING_MODEL,
        "dimension": len(query_vector) if query_vector else 0,
        "duration_ms": embedding_time_ms
    })

    # Step 3: ChromaDB search (raw top-K children)
    t0 = time.time()
    collection = vector_db.get_collection(COLLECTION_NAME)
    raw_results = collection.query(
        query_embeddings=[query_vector],
        n_results=TOP_K_CHILDREN
    )
    search_time_ms = int((time.time() - t0) * 1000)

    # Step 3.5: Parse raw results into full chunk cards
    chunks_detail = []
    if raw_results and raw_results.get("ids") and len(raw_results["ids"][0]) > 0:
        ids = raw_results["ids"][0]
        documents = raw_results["documents"][0]
        metadatas = raw_results["metadatas"][0]
        distances = raw_results["distances"][0] if "distances" in raw_results else [0.0] * len(ids)

        for idx, chunk_id in enumerate(ids):
            meta = metadatas[idx]
            chunks_detail.append({
                "rank": idx + 1,
                "chunk_id": chunk_id,
                "score": round(float(1.0 - distances[idx]), 4),
                "content": documents[idx],
                "file_name": meta.get("file_name", "未知"),
                "import_id": meta.get("import_id", ""),
                "chunk_index": meta.get("chunk_index", ""),
                "h1": meta.get("h1", ""),
                "h2": meta.get("h2", ""),
                "h3": meta.get("h3", ""),
                "parent_content": meta.get("parent_content", ""),
                "section_id": meta.get("section_id", ""),
            })

    trace["steps"].append({
        "name": "ChromaDB 向量检索",
        "collection": COLLECTION_NAME,
        "metric": "cosine",
        "top_k": TOP_K_CHILDREN,
        "duration_ms": search_time_ms,
        "results": chunks_detail
    })

    # Step 4: Small-to-Big expansion
    # 分组：优先按 section_id（同一父文档小节的子 chunk 归组）；
    # 旧数据无 section_id 时按 import_id 归组；再无则按 chunk_id 独立成组。
    groups = {}
    for cd in chunks_detail:
        sid = cd.get("section_id") or ""
        if sid:
            key = ("sec", sid)
        else:
            import_id = cd.get("import_id") or ""
            if import_id:
                key = ("import", import_id)
            else:
                key = ("chunk", cd["chunk_id"])
        groups.setdefault(key, []).append(cd)

    # 每组展开：优先使用父文档内容；找不到父文档时，把该组全部子文档拼接作为测试内容
    parent_docs = []
    fallback_count = 0
    for key, members in groups.items():
        members.sort(key=lambda m: m["rank"])  # 保持命中顺序
        parent_content = next(
            (m["parent_content"] for m in members if m.get("parent_content")), ""
        )
        source = "parent"
        if not parent_content:
            parent_content = "\n\n".join(m["content"] for m in members)
            source = "children_concat"
            fallback_count += 1
        first = members[0]
        parent_docs.append({
            "section_id": first.get("section_id", ""),
            "import_id": first.get("import_id", ""),
            "file_name": first.get("file_name", "未知"),
            "h1": first.get("h1", ""),
            "h2": first.get("h2", ""),
            "h3": first.get("h3", ""),
            "source": source,               # parent=真实父文档 | children_concat=子文档拼接
            "chunk_count": len(members),
            "score": max(m["score"] for m in members),
            "content": parent_content,
        })

    parent_count = len(parent_docs)
    dedup_count = min(parent_count, TOP_K_PARENTS)
    total_chars = sum(len(p["content"]) for p in parent_docs[:TOP_K_PARENTS])

    trace["steps"].append({
        "name": "父文档展开 (Small-to-Big)",
        "child_count": len(chunks_detail),
        "parent_count": parent_count,
        "dedup_count": dedup_count,
        "fallback_concat_count": fallback_count,
        "expanded": parent_docs[:TOP_K_PARENTS],
        "total_chars": total_chars,
        "estimated_tokens": total_chars // 2,  # 中文字符粗略估算
        "budget_tokens": 1300,
        "within_budget": (total_chars // 2) <= 1300
    })

    return trace


# ============================================================================
# RAGService 保留向后兼容
# ============================================================================


class RAGService:
    """RAG 检索与知识管理服务（保持与旧代码兼容的公共接口）"""

    def __init__(self, collection_name="psychology_kb"):
        self.collection_name = collection_name

    def add_knowledge_import_task(
        self, db: Session, file_name: str, file_hash: str,
        minio_bucket: str, minio_object_name: str, file_size: int
    ):
        """管理端：在 MySQL 中创建 RAG 导入任务记录"""
        task = db.query(KnowledgeImport).filter(
            KnowledgeImport.file_hash == file_hash
        ).first()
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

    def search_knowledge(
        self, db: Session, query: str, limit=2, query_vector=None
    ):
        """旧接口保留：直接检索子 chunk"""
        cards = []
        try:
            if query_vector is None:
                query_vector = llm_service.get_embedding(query)

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
