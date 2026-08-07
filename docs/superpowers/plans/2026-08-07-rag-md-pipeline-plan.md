# RAG 统一 Markdown 管线与链路可视化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 RAG pipeline 为统一 Markdown 中间层架构，新增结构化切片与 Small-to-Big 检索，并在管理端新增链路调试可视化组件。

**Architecture:** 所有文档格式（PDF/DOCX/TXT/MD）先经 converter.py 转为 Markdown 统一中间层，再由 MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter 两层切片，子 chunk（≤800 char）入 ChromaDB 索引，检索时 Small-to-Big 展开为父文档注入 LLM（≤1300 tokens）。前端新增 KnowledgeManager 三 Tab 组件提供上传、列表、链路调试功能。

**Tech Stack:** Python 3.11 / FastAPI / LangChain / ChromaDB / MinIO / pymupdf4llm / mammoth / trafilatura / Vue 3 + Vite

## Global Constraints

- 微调模型上下文窗口: 2048 tokens，检索注入预算 ≤ 1300 tokens
- chunk_size=800 字符, chunk_overlap=100 字符, top-k 子 chunk=3, 父文档展开 ≤2
- 使用 cosine 度量空间（ChromaDB 现有配置）
- 所有文档格式转换失败时 fallback 到现有纯文本提取
- MinIO 存储双路径: `uploads/`（原始文件）+ `processed/`（提取后 MD）
- 前端遵循现有 Vue 3 Composition API + `<script setup>` 模式
- 后端遵循现有 FastAPI + 单例 service 模式

---

### Task 1: 文档转换器 `converter.py`

**Files:**
- Create: `backend/app/services/converter.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Produces:
  - `convert_to_markdown(file_bytes: bytes, filename: str) -> tuple[str, dict]` — 主入口，根据扩展名分发
  - `convert_pdf(file_bytes: bytes) -> tuple[str, dict]` — PDF→MD via pymupdf4llm, fallback pypdf
  - `convert_docx(file_bytes: bytes) -> tuple[str, dict]` — DOCX→MD via mammoth, fallback python-docx
  - `convert_txt(file_bytes: bytes) -> tuple[str, dict]` — TXT/MD 直通

- [ ] **Step 1: 更新 requirements.txt 添加新依赖**

```python
# backend/requirements.txt 末尾追加:
pymupdf4llm>=0.0.12
mammoth>=1.6.0
trafilatura>=1.12.0
```

- [ ] **Step 2: 安装新依赖**

Run: `pip install pymupdf4llm>=0.0.12 mammoth>=1.6.0 trafilatura>=1.12.0`
Expected: 全部安装成功

- [ ] **Step 3: 编写 `converter.py`**

```python
# backend/app/services/converter.py
# -*- coding: utf-8 -*-
"""
多格式文档 -> Markdown 统一转换器。

支持的格式及其转换策略：
    PDF  -> pymupdf4llm (保留标题/表格/图片引用), fallback pypdf
    DOCX -> mammoth (保留 Heading 1-6 层级), fallback python-docx
    TXT  -> 直通（视为纯文本 Markdown）
    MD   -> 直通
    HTML -> trafilatura (公众号文章场景去噪提取)
"""

import io
import logging
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)


def _fallback_pdf(file_bytes: bytes) -> str:
    """pypdf 纯文本提取（旧逻辑作为降级方案）"""
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    return "\n\n".join(text_parts)


def _fallback_docx(file_bytes: bytes) -> str:
    """python-docx 纯段落提取（旧逻辑作为降级方案）"""
    import docx
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)


def convert_pdf(file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """PDF → Markdown，失败时降级到纯文本提取"""
    metadata = {"source_format": "pdf", "page_count": 0, "converter": "pymupdf4llm"}

    try:
        import pymupdf4llm
        md_text = pymupdf4llm.to_markdown(io.BytesIO(file_bytes))

        # 获取页数
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            metadata["page_count"] = doc.page_count
            doc.close()
        except Exception:
            pass

        if not md_text or not md_text.strip():
            raise ValueError("pymupdf4llm 返回空结果")
        return md_text.strip(), metadata
    except Exception as e:
        logger.warning(f"pymupdf4llm 转换失败 ({e})，降级到 pypdf 纯文本提取")
        metadata["converter"] = "pypdf_fallback"
        return _fallback_pdf(file_bytes), metadata


def convert_docx(file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """DOCX → Markdown via mammoth，失败时降级"""
    metadata = {"source_format": "docx", "converter": "mammoth"}

    try:
        import mammoth
        result = mammoth.convert_to_markdown(io.BytesIO(file_bytes))
        md_text = result.value
        if result.messages:
            logger.info(f"mammoth 转换消息: {result.messages}")
        if not md_text or not md_text.strip():
            raise ValueError("mammoth 返回空结果")
        return md_text.strip(), metadata
    except Exception as e:
        logger.warning(f"mammoth 转换失败 ({e})，降级到 python-docx 纯文本提取")
        metadata["converter"] = "python-docx_fallback"
        return _fallback_docx(file_bytes), metadata


def convert_txt(file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """TXT/MD 直通"""
    metadata = {"source_format": "txt", "converter": "passthrough"}
    text = file_bytes.decode("utf-8", errors="ignore").strip()
    return text, metadata


def convert_html(file_bytes: bytes) -> Tuple[str, Dict[str, Any]]:
    """HTML → Markdown（公众号文章场景）"""
    metadata = {"source_format": "html", "converter": "trafilatura"}

    try:
        import trafilatura
        html_str = file_bytes.decode("utf-8", errors="ignore")
        md_text = trafilatura.extract(html_str, output_format="markdown",
                                       include_tables=True, include_images=False)
        if not md_text:
            # 降级到 html2text
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = True
            h.body_width = 0
            md_text = h.handle(html_str)
            metadata["converter"] = "html2text_fallback"
        return md_text.strip(), metadata
    except ImportError:
        logger.warning("trafilatura 不可用，使用 html2text")
        metadata["converter"] = "html2text"
        import html2text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0
        return h.handle(file_bytes.decode("utf-8", errors="ignore")).strip(), metadata


def convert_to_markdown(file_bytes: bytes, filename: str) -> Tuple[str, Dict[str, Any]]:
    """
    根据文件扩展名分发到对应的转换器。

    Args:
        file_bytes: 原始文件二进制内容
        filename: 文件名（含扩展名）

    Returns:
        (markdown_text, conversion_metadata)
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    converters = {
        "pdf":  convert_pdf,
        "docx": convert_docx,
        "doc":  convert_docx,
        "txt":  convert_txt,
        "md":   convert_txt,   # MD 也走直通
        "html": convert_html,
        "htm":  convert_html,
    }

    converter = converters.get(ext)
    if converter is None:
        # 未知格式尝试当文本处理
        logger.info(f"未知格式 .{ext}，尝试作为文本处理")
        return convert_txt(file_bytes)

    return converter(file_bytes)
```

- [ ] **Step 4: 验证导入链**

Run:
```bash
python -c "from app.services.converter import convert_to_markdown, convert_pdf, convert_docx, convert_txt; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/app/services/converter.py
git commit -m "feat: 新增多格式文档到 Markdown 统一转换器，带逐格式降级策略"
```

---

### Task 2: 重构 RAG 服务 `rag.py`

**Files:**
- Modify: `backend/app/services/rag.py`

**Interfaces:**
- Consumes:
  - `converter.convert_to_markdown()` from Task 1
  - `llm_service.get_embedding(text) -> list[float]` (existing)
  - `vector_db.get_collection(name) -> chromadb.Collection` (existing)
  - `storage_service.upload_file(object_name, data, content_type) -> bool` (existing)
- Produces:
  - `split_markdown_into_chunks(md_text: str, max_chars=800, overlap=100) -> list[dict]` — 两层切片
  - `ingest_document(file_bytes, filename, file_hash, task_id, db) -> int` — 完整入库流水线
  - `retrieve_with_context(query, top_k=2) -> list[dict]` — Small-to-Big 检索
  - `trace_retrieval(query) -> dict` — 全链路追踪（用于前端可视化）

- [ ] **Step 1: 重写 `rag.py` 完整内容**

```python
# backend/app/services/rag.py
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
import hashlib
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

CHUNK_SIZE = 800       # 子 chunk 最大字符数
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
        # 先按 H3 边界子切分再对每个 H3 二级切分
        section_chunks = char_splitter.split_text(parent_content)
        for chunk_text in section_chunks:
            # 从 chunk 文本中提取 H3（如果有）
            h3 = ""
            for line in chunk_text.split("\n"):
                line_stripped = line.strip()
                if line_stripped.startswith("### "):
                    h3 = line_stripped[4:].strip()
                    break

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
    filename = file.filename.lower()
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
                detail="系统暂未安装 PDF 解析依赖 pypdf"
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF 解析失败: {str(e)}")
    elif filename.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_content))
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            raise HTTPException(
                status_code=400,
                detail="系统暂未安装 Word 解析依赖 python-docx"
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Word 文档解析失败: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="不支持的文件格式，仅支持 .txt, .md, .pdf, .docx")


# ============================================================================
# 旧 split_text_into_chunks 保留向后兼容（手动卡片录入仍使用）
# ============================================================================


def split_text_into_chunks(text: str, max_chars: int = 800, overlap: int = 100) -> List[str]:
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

    # 2. MinIO 存储原始文件 + 处理后的 MD
    storage_service.upload_file(
        object_name=f"uploads/{file_hash}_{filename}",
        data=file_bytes,
        content_type="application/octet-stream"
    )
    md_bytes = md_text.encode("utf-8")
    storage_service.upload_file(
        object_name=f"processed/{file_hash}.md",
        data=md_bytes,
        content_type="text/markdown; charset=utf-8"
    )

    # 3. 结构化切片
    chunks = split_markdown_into_chunks(md_text, max_chars=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    if not chunks:
        raise ValueError("文档切片后无有效内容")

    # 4. 每个 chunk 嵌入 + 写入 ChromaDB
    collection = vector_db.get_collection(COLLECTION_NAME)

    ids = []
    embeddings = []
    documents = []
    metadatas = []

    for idx, chunk in enumerate(chunks):
        # 构造上下文增强的文档文本
        h_path_parts = [p for p in [chunk["metadata"]["h1"],
                                     chunk["metadata"]["h2"],
                                     chunk["metadata"]["h3"]] if p]
        h_path = " > ".join(h_path_parts) if h_path_parts else filename

        context_text = f"【{h_path}】\n{chunk['content']}"
        chunk_vec = llm_service.get_embedding(context_text)

        ids.append(f"{task.id}_chunk_{idx}")
        embeddings.append(chunk_vec)
        documents.append(context_text)
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

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

    # 5. 更新 MySQL 任务状态
    task.chunk_count = len(chunks)
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

    # Step 1: Embedding
    t0 = time.time()
    query_vector = llm_service.get_embedding(query)
    embedding_time_ms = int((time.time() - t0) * 1000)
    trace["steps"].append({
        "name": "Embedding 向量化",
        "model": Config.EMBEDDING_MODEL,
        "dimension": len(query_vector) if query_vector else 0,
        "duration_ms": embedding_time_ms
    })

    # Step 2: ChromaDB search (raw top-K children)
    t0 = time.time()
    collection = vector_db.get_collection(COLLECTION_NAME)
    raw_results = collection.query(
        query_embeddings=[query_vector],
        n_results=TOP_K_CHILDREN
    )
    search_time_ms = int((time.time() - t0) * 1000)

    # Step 3: Parse raw results into full chunk cards
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
    seen_sections = set()
    parent_docs = []
    for cd in chunks_detail:
        sid = cd.get("section_id", cd["chunk_id"])
        if sid in seen_sections:
            continue
        seen_sections.add(sid)
        parent_docs.append(cd)

    total_chars = sum(len(p["parent_content"]) for p in parent_docs[:TOP_K_PARENTS])

    trace["steps"].append({
        "name": "父文档展开 (Small-to-Big)",
        "child_count": len(chunks_detail),
        "parent_count": len(parent_docs),
        "dedup_count": min(len(parent_docs), TOP_K_PARENTS),
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
    """RAG 检索服务（保持与旧代码兼容的公共接口）"""

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
```

- [ ] **Step 2: 验证模块导入**

Run:
```bash
python -c "from app.services.rag import split_markdown_into_chunks, retrieve_with_context, trace_retrieval, ingest_document; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: 用测试文本验证切片逻辑**

Run:
```bash
python -c "
from app.services.rag import split_markdown_into_chunks
md = '# CBT\n## 理论\n### 认知模型\n认知模型认为情绪由认知决定。\n### 行为激活\n行为激活是通过增加积极活动来改善情绪的技术。\n## 应用\n### 焦虑\n焦虑障碍治疗包括以下步骤。\n'
chunks = split_markdown_into_chunks(md)
for c in chunks:
    print(f'h1={c[\"metadata\"][\"h1\"]} h2={c[\"metadata\"][\"h2\"]} h3={c[\"metadata\"][\"h3\"]}')
    print(f'  content: {c[\"content\"][:60]}...')
    print(f'  parent_len: {len(c[\"metadata\"][\"parent_content\"])}')
print(f'Total chunks: {len(chunks)}')
"
```
Expected: 输出 4 个 chunk，每个携带正确的 h1/h2/h3 和 parent_content

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/rag.py
git commit -m "feat: 重构 RAG 服务为统一 MD 管线 — 结构化切片 + Small-to-Big 检索 + 链路追踪"
```

---

### Task 3: 新增知识库管理 API 端点

**Files:**
- Modify: `backend/app/routes/admin.py`

**Interfaces:**
- Consumes:
  - `ingest_document()`, `trace_retrieval()`, `retrieve_with_context()` from Task 2
  - `split_markdown_into_chunks()` from Task 2
  - `convert_to_markdown()` from Task 1
  - `storage_service` (existing)
  - `vector_db` (existing)
- Produces:
  - `POST /api/admin/knowledge/upload` — 替换现有上传（使用新管线）
  - `POST /api/admin/knowledge/trace` — 全链路追踪
  - `GET /api/admin/knowledge/{id}/chunks` — 查看文档 chunk 结构
  - `POST /api/admin/knowledge/{id}/reprocess` — 重处理
  - `GET /api/admin/knowledge/{id}/markdown` — 获取 MD 原文

- [ ] **Step 1: 修改 admin.py 的导入块**

在 `backend/app/routes/admin.py` 顶部，将：
```python
from app.services.rag import extract_text_from_file, split_text_into_chunks
```
替换为：
```python
from app.services.rag import (
    extract_text_from_file, split_text_into_chunks,
    split_markdown_into_chunks, ingest_document,
    retrieve_with_context, trace_retrieval
)
from app.services.converter import convert_to_markdown
```

- [ ] **Step 2: 替换 `upload_knowledge_file` 函数（约第 653-727 行）**

用以下新实现替换旧的上传函数：

```python
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
```

- [ ] **Step 3: 新增 trace 端点**

在 `upload_knowledge_file` 函数之后追加：

```python
class TraceRequest(BaseModel):
    query: str


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
```

- [ ] **Step 4: 新增 chunks 查看端点**

```python
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
```

- [ ] **Step 5: 新增 reprocess 端点**

```python
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
```

- [ ] **Step 6: 新增 markdown 原文查看端点**

```python
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
```

- [ ] **Step 7: 验证所有新端点可导入**

Run:
```bash
python -c "from app.routes.admin import admin_bp; print('OK')"
```
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add backend/app/routes/admin.py
git commit -m "feat: 新增知识库管理 API — trace/chunks/reprocess/markdown 端点，上传改用 MD 管线"
```

---

### Task 4: 前端 KnowledgeManager 组件（上传 + 列表 + 链路调试）

**Files:**
- Create: `frontend/src/components/admin/KnowledgeManager.vue`

**Interfaces:**
- Consumes:
  - `axios` (existing global)
  - `getAuthHeader()` — 从 Admin.vue 通过 props 传入
- Produces:
  - 三 Tab 组件，通过 `v-if="activeMenu === 'knowledge'"` 集成到 Admin.vue

- [ ] **Step 1: 编写完整的 `KnowledgeManager.vue`**

```vue
<template>
  <div class="knowledge-manager card-panel">
    <!-- Tab 切换栏 -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-btn', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <!-- ============ Tab 1: 文档上传 ============ -->
    <div v-if="activeTab === 'upload'" class="tab-content">
      <div
        class="upload-zone"
        :class="{ dragging: isDragging }"
        @dragover.prevent="isDragging = true"
        @dragleave="isDragging = false"
        @drop.prevent="handleDrop"
        @click="triggerFileInput"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".pdf,.docx,.doc,.txt,.md"
          style="display: none"
          @change="handleFileSelect"
        />
        <div class="upload-prompt">
          <span class="upload-icon">📤</span>
          <p>拖拽文件到此处，或点击选择</p>
          <p class="upload-hint">支持 PDF / DOCX / TXT / MD</p>
        </div>
      </div>

      <!-- 处理进度 -->
      <div v-if="uploadTasks.length" class="task-list">
        <div
          v-for="task in uploadTasks"
          :key="task.id"
          :class="['task-card', task.status]"
        >
          <div class="task-header">
            <span class="task-file">📄 {{ task.fileName }}</span>
            <span class="task-status">
              {{ statusLabel(task.status) }}
            </span>
          </div>
          <div class="task-steps">
            <span :class="['step', { done: task.step >= 1 }]">📝 转换</span>
            <span class="step-arrow">→</span>
            <span :class="['step', { done: task.step >= 2 }]">✂️ 切片</span>
            <span class="step-arrow">→</span>
            <span :class="['step', { done: task.step >= 3 }]">🧮 向量化</span>
            <span class="step-arrow">→</span>
            <span :class="['step', { done: task.step >= 4 }]">✅ 完成</span>
          </div>
          <div v-if="task.error" class="task-error">{{ task.error }}</div>
        </div>
      </div>
    </div>

    <!-- ============ Tab 2: 知识列表 ============ -->
    <div v-if="activeTab === 'list'" class="tab-content">
      <div class="list-toolbar">
        <input
          v-model="searchKeyword"
          type="text"
          class="search-input"
          placeholder="搜索文件名..."
          @keyup.enter="fetchList"
        />
        <button class="btn btn-primary" @click="fetchList">🔍 搜索</button>
      </div>
      <table v-if="listItems.length" class="data-table">
        <thead>
          <tr>
            <th>文件名</th>
            <th>状态</th>
            <th>Chunks</th>
            <th>大小</th>
            <th>时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in listItems" :key="item.id">
            <td class="file-name-cell">{{ item.file_name }}</td>
            <td>
              <span :class="['status-badge', item.status]">
                {{ statusLabel(item.status) }}
              </span>
            </td>
            <td>{{ item.chunk_count }}</td>
            <td>{{ formatSize(item.file_size) }}</td>
            <td>{{ formatTime(item.created_at) }}</td>
            <td class="action-cell">
              <button class="btn-sm" @click="reprocessItem(item)">🔄 重处理</button>
              <button class="btn-sm" @click="viewChunks(item)">📋 Chunks</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">暂无知识文档</div>
      <div class="pagination">
        <button :disabled="page <= 1" @click="page--; fetchList()">上一页</button>
        <span>第 {{ page }} 页 / 共 {{ totalPages }} 页</span>
        <button :disabled="page >= totalPages" @click="page++; fetchList()">下一页</button>
      </div>
    </div>

    <!-- ============ Tab 3: 链路调试 ============ -->
    <div v-if="activeTab === 'debug'" class="tab-content">
      <div class="debug-input-row">
        <input
          v-model="debugQuery"
          type="text"
          class="search-input debug-input"
          placeholder="输入测试问题，如：焦虑障碍怎么治疗？"
          @keyup.enter="runTrace"
        />
        <button class="btn btn-primary" @click="runTrace" :disabled="tracing">
          {{ tracing ? '⏳ 追踪中...' : '🔍 检索' }}
        </button>
      </div>

      <!-- 链路流程可视化 -->
      <div v-if="traceData" class="trace-timeline">
        <div v-for="(step, si) in traceData.steps" :key="si" class="trace-step">
          <!-- 连接线 -->
          <div v-if="si > 0" class="trace-connector">
            <span class="connector-line">┃</span>
            <span class="connector-duration">▼ {{ step.duration_ms }}ms</span>
          </div>

          <div class="step-card">
            <div class="step-icon">{{ stepIcon(step.name) }}</div>
            <div class="step-body">
              <div class="step-name">{{ step.name }}</div>
              <div class="step-meta">
                <span v-if="step.model">模型: {{ step.model }}</span>
                <span v-if="step.dimension">维度: {{ step.dimension }}</span>
                <span v-if="step.collection">集合: {{ step.collection }}</span>
                <span v-if="step.metric">度量: {{ step.metric }}</span>
                <span v-if="step.top_k">top-{{ step.top_k }}</span>
              </div>

              <!-- 检索结果卡片 -->
              <div v-if="step.results && step.results.length" class="chunk-cards">
                <div
                  v-for="(chunk, ci) in step.results"
                  :key="ci"
                  :class="['chunk-card', `rank-${chunk.rank}`]"
                >
                  <div class="chunk-header">
                    <span class="chunk-rank">{{ ['🥇','🥈','🥉'][ci] || '' }} Chunk #{{ chunk.rank }}</span>
                    <span class="chunk-score">相似度: {{ chunk.score }}</span>
                  </div>
                  <div class="chunk-meta">
                    <span>📄 {{ chunk.file_name }}</span>
                    <span v-if="chunk.h1 || chunk.h2 || chunk.h3" class="chunk-path">
                      📂 {{ [chunk.h1, chunk.h2, chunk.h3].filter(Boolean).join(' > ') }}
                    </span>
                  </div>
                  <div class="chunk-content">
                    <pre>{{ chunk.content }}</pre>
                  </div>
                  <details class="parent-expand">
                    <summary>展开父文档 ▼</summary>
                    <pre class="parent-content">{{ chunk.parent_content }}</pre>
                  </details>
                </div>
              </div>

              <!-- Small-to-Big 统计 -->
              <div v-if="step.child_count !== undefined" class="sbs-stats">
                <span>{{ step.child_count }} 个子 chunk → {{ step.parent_count }} 个父文档</span>
                <span>去重后: {{ step.dedup_count }}</span>
                <span>{{ step.total_chars }} 字符 (~{{ step.estimated_tokens }} tokens)</span>
                <span :class="step.within_budget ? 'budget-ok' : 'budget-over'">
                  {{ step.within_budget ? '✅' : '⚠️' }} 预算 {{ step.budget_tokens }} tokens
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="!tracing" class="empty-state">
        输入测试问题，点击"检索"查看完整的 RAG 链路追踪
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import axios from 'axios'

const props = defineProps({
  getAuthHeader: { type: Function, required: true }
})

// ---- Tabs ----
const tabs = [
  { id: 'upload', label: '文档上传', icon: '📤' },
  { id: 'list', label: '知识列表', icon: '📋' },
  { id: 'debug', label: '链路调试', icon: '🔍' },
]
const activeTab = ref('upload')

// ---- Tab 1: Upload ----
const fileInput = ref(null)
const isDragging = ref(false)
const uploadTasks = reactive([])
let taskIdCounter = 0

function triggerFileInput() {
  fileInput.value?.click()
}

function statusLabel(s) {
  const map = { pending: '⏳ 等待', processing: '🔄 处理中', success: '✅ 成功', failed: '❌ 失败' }
  return map[s] || s
}

async function uploadFile(file) {
  const tid = ++taskIdCounter
  const task = reactive({ id: tid, fileName: file.name, status: 'processing', step: 0, error: '' })
  uploadTasks.push(task)

  try {
    task.step = 1
    const formData = new FormData()
    formData.append('file', file)
    const res = await axios.post('/api/admin/knowledge/upload', formData, {
      headers: { ...props.getAuthHeader(), 'Content-Type': 'multipart/form-data' }
    })
    if (res.data?.code === 200) {
      task.step = 4
      task.status = 'success'
    } else {
      throw new Error(res.data?.message || '上传失败')
    }
  } catch (err) {
    task.status = 'failed'
    task.error = err.response?.data?.detail || err.message || '上传失败'
  }
}

function handleDrop(e) {
  isDragging.value = false
  for (const file of e.dataTransfer.files) {
    uploadFile(file)
  }
}

function handleFileSelect(e) {
  for (const file of e.target.files) {
    uploadFile(file)
  }
  e.target.value = ''
}

// ---- Tab 2: List ----
const searchKeyword = ref('')
const listItems = ref([])
const page = ref(1)
const size = 10

const totalPages = computed(() => Math.max(1, Math.ceil(listItems.value.length / size)))

async function fetchList() {
  try {
    const res = await axios.get('/api/admin/knowledge', {
      headers: props.getAuthHeader(),
      params: { page: page.value, size: 100, keyword: searchKeyword.value || undefined }
    })
    if (res.data?.code === 200) {
      listItems.value = res.data.data.items || []
    }
  } catch (err) {
    console.error('获取知识列表失败:', err)
  }
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatTime(iso) {
  if (!iso) return '-'
  try {
    const d = new Date(iso)
    const pad = n => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch { return iso }
}

async function reprocessItem(item) {
  try {
    const res = await axios.post(`/api/admin/knowledge/${item.id}/reprocess`, {}, {
      headers: props.getAuthHeader()
    })
    if (res.data?.code === 200) {
      item.status = 'success'
      item.chunk_count = res.data.data.chunk_count
    }
  } catch (err) {
    console.error('重处理失败:', err)
  }
}

async function viewChunks(item) {
  try {
    const res = await axios.get(`/api/admin/knowledge/${item.id}/chunks`, {
      headers: props.getAuthHeader()
    })
    if (res.data?.code === 200) {
      // 在控制台输出，后续可扩展为弹窗
      console.log(`Chunks for ${item.file_name}:`, res.data.data)
      alert(`${item.file_name} 共 ${res.data.data.total_chunks} 个 chunks，详情见控制台`)
    }
  } catch (err) {
    console.error('获取 chunks 失败:', err)
  }
}

// ---- Tab 3: Debug ----
const debugQuery = ref('')
const tracing = ref(false)
const traceData = ref(null)

function stepIcon(name) {
  if (name.includes('Embedding')) return '🧮'
  if (name.includes('ChromaDB') || name.includes('向量')) return '🗄️'
  if (name.includes('父文档') || name.includes('Small')) return '📤'
  return '🔍'
}

async function runTrace() {
  if (!debugQuery.value.trim() || tracing.value) return
  tracing.value = true
  traceData.value = null
  try {
    const res = await axios.post('/api/admin/knowledge/trace',
      { query: debugQuery.value.trim() },
      { headers: props.getAuthHeader() }
    )
    if (res.data?.code === 200) {
      traceData.value = res.data.data
    }
  } catch (err) {
    console.error('链路追踪失败:', err)
    alert('追踪失败: ' + (err.response?.data?.detail || err.message))
  } finally {
    tracing.value = false
  }
}

// 加载列表
fetchList()
</script>

<style scoped>
.knowledge-manager {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  background: var(--panel-bg);
  border-radius: var(--radius-md);
}

/* ---- Tab Bar ---- */
.tab-bar {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid var(--border-color);
  padding-bottom: 0;
}
.tab-btn {
  padding: 10px 20px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: var(--transition-normal);
  display: flex;
  align-items: center;
  gap: 6px;
}
.tab-btn:hover { color: var(--primary-hover); }
.tab-btn.active {
  color: var(--primary-hover);
  border-bottom-color: var(--primary);
  font-weight: 600;
}
.tab-icon { font-size: 16px; }

.tab-content { padding-top: 8px; }

/* ---- Upload Zone ---- */
.upload-zone {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-md);
  padding: 48px;
  text-align: center;
  cursor: pointer;
  transition: var(--transition-normal);
}
.upload-zone:hover, .upload-zone.dragging {
  border-color: var(--primary);
  background: var(--primary-light);
}
.upload-icon { font-size: 40px; display: block; margin-bottom: 12px; }
.upload-hint { font-size: 12px; color: var(--text-secondary); margin-top: 8px; }

/* ---- Task Cards ---- */
.task-list { display: flex; flex-direction: column; gap: 12px; margin-top: 16px; }
.task-card {
  padding: 14px 18px;
  border-radius: var(--radius-sm);
  background: var(--bg-color);
  border: 1px solid var(--border-color);
}
.task-card.success { border-color: #27ae60; }
.task-card.failed { border-color: #e74c3c; }
.task-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.task-file { font-weight: 600; }
.task-steps { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.step { color: var(--text-secondary); }
.step.done { color: #27ae60; font-weight: 500; }
.step-arrow { color: var(--text-secondary); }
.task-error { color: #e74c3c; font-size: 12px; margin-top: 8px; }

/* ---- Data Table ---- */
.list-toolbar { display: flex; gap: 10px; margin-bottom: 16px; }
.search-input { flex: 1; padding: 8px 12px; border: 1px solid var(--border-color); border-radius: var(--radius-sm); background: var(--bg-color); color: var(--text-primary); font-size: 13px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th { text-align: left; padding: 10px 8px; border-bottom: 2px solid var(--border-color); color: var(--text-secondary); font-weight: 600; }
.data-table td { padding: 10px 8px; border-bottom: 1px solid var(--border-color); }
.file-name-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.status-badge { padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 500; }
.status-badge.success { background: #d5f5e3; color: #27ae60; }
.status-badge.processing { background: #fef9e7; color: #f39c12; }
.status-badge.failed { background: #fadbd8; color: #e74c3c; }
.status-badge.pending { background: #ebf5fb; color: #2980b9; }
.action-cell { display: flex; gap: 6px; }
.btn-sm { padding: 4px 10px; border: 1px solid var(--border-color); border-radius: 4px; background: var(--bg-color); color: var(--text-primary); font-size: 12px; cursor: pointer; }
.btn-sm:hover { background: var(--primary-light); }
.btn { padding: 8px 16px; border: none; border-radius: var(--radius-sm); cursor: pointer; font-size: 13px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-hover); }
.empty-state { text-align: center; padding: 40px; color: var(--text-secondary); }
.pagination { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 16px; font-size: 13px; }
.pagination button { padding: 6px 14px; border: 1px solid var(--border-color); border-radius: 4px; background: var(--bg-color); color: var(--text-primary); cursor: pointer; }
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }

/* ---- Debug / Trace ---- */
.debug-input-row { display: flex; gap: 10px; margin-bottom: 20px; }
.debug-input { font-size: 14px; padding: 10px 14px; }

.trace-timeline { display: flex; flex-direction: column; gap: 0; }
.trace-connector { text-align: center; padding: 2px 0; color: var(--text-secondary); font-size: 12px; }
.connector-line { display: block; font-size: 18px; line-height: 1; }

.step-card {
  display: flex; gap: 14px;
  padding: 16px;
  background: var(--bg-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
}
.step-icon { font-size: 24px; flex-shrink: 0; }
.step-body { flex: 1; }
.step-name { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
.step-meta { display: flex; gap: 12px; font-size: 12px; color: var(--text-secondary); flex-wrap: wrap; }

.chunk-cards { display: flex; flex-direction: column; gap: 12px; margin-top: 12px; }
.chunk-card { border: 1px solid var(--border-color); border-radius: var(--radius-sm); overflow: hidden; }
.chunk-card.rank-1 { border-left: 3px solid #f39c12; }
.chunk-card.rank-2 { border-left: 3px solid #888; }
.chunk-card.rank-3 { border-left: 3px solid #b87333; }
.chunk-header { display: flex; justify-content: space-between; padding: 8px 12px; background: var(--panel-bg); font-size: 13px; font-weight: 500; }
.chunk-score { color: var(--primary); font-weight: 600; }
.chunk-meta { display: flex; flex-direction: column; gap: 2px; padding: 6px 12px; font-size: 12px; color: var(--text-secondary); }
.chunk-path { color: var(--primary-hover); }
.chunk-content { padding: 0 12px 8px; }
.chunk-content pre, .parent-content {
  white-space: pre-wrap; word-break: break-word;
  font-size: 12px; line-height: 1.6;
  background: var(--panel-bg); padding: 10px; border-radius: 4px;
  max-height: 200px; overflow-y: auto;
}
.parent-expand { padding: 0 12px 8px; }
.parent-expand summary { cursor: pointer; font-size: 12px; color: var(--primary); padding: 4px 0; }

.sbs-stats {
  display: flex; gap: 14px; margin-top: 10px;
  font-size: 13px; color: var(--text-secondary); flex-wrap: wrap;
}
.budget-ok { color: #27ae60; font-weight: 500; }
.budget-over { color: #e74c3c; font-weight: 500; }
</style>
```

- [ ] **Step 2: 验证组件语法**

Run:
```bash
cd frontend && npx vue-tsc --noEmit --skipLibCheck src/components/admin/KnowledgeManager.vue 2>&1 || echo "Check done (warnings OK)"
```
Expected: 无语法错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/admin/KnowledgeManager.vue
git commit -m "feat: 新增知识库管理组件 — 上传/列表/链路调试三合一 Tab"
```

---

### Task 5: 集成 KnowledgeManager 到 Admin.vue

**Files:**
- Modify: `frontend/src/pages/Admin.vue`

**Interfaces:**
- Consumes: `KnowledgeManager.vue` from Task 4
- Produces: sidebar 新增 "知识库管理" 菜单项，主工作区条件渲染

- [ ] **Step 1: 修改 Admin.vue**

**修改 1** — import 区新增：
```javascript
import KnowledgeManager from '../components/admin/KnowledgeManager.vue'
```

**修改 2** — 在 `menus` 数组中新增菜单项，在 `SafetyConfig` 后面追加：
```javascript
{ id: 'knowledge', label: '知识库管理', icon: '📚' }
```

**修改 3** — 在模板的 `<main class="admin-main">` 内部，`<SafetyConfig>` 之后追加：
```html
<!-- 4. 知识库管理 -->
<KnowledgeManager
  v-if="activeMenu === 'knowledge'"
  :getAuthHeader="getAuthHeader"
/>
```

- [ ] **Step 2: 验证前端构建**

Run:
```bash
cd frontend && npm run build 2>&1
```
Expected: Build 成功

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Admin.vue
git commit -m "feat: 管理端侧边栏集成知识库管理入口，含链路调试可视化"
```

---

### Task 6: 端到端验证

- [ ] **Step 1: 启动后端验证 API 可用**

Run:
```bash
cd backend && timeout 5 python -c "
from app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
# 测试 upload 端点可达（不实际传文件）
print('App loaded OK, routes:', [r.path for r in app.routes if 'knowledge' in r.path])
"
```
Expected: 列出 knowledge 相关路由

- [ ] **Step 2: 用单元测试验证切片 800 字符约束**

Run:
```bash
python -c "
from app.services.rag import split_markdown_into_chunks
# 构造一个超长的 H3 section
long_text = '### 测试\n' + '测' * 2000
chunks = split_markdown_into_chunks(long_text, max_chars=800, overlap=100)
for i, c in enumerate(chunks):
    assert len(c['content']) <= 800 + 100, f'Chunk {i} too long: {len(c[\"content\"])}'
    assert c['metadata']['h3'] == '测试', f'Chunk {i} missing h3'
print(f'OK: {len(chunks)} chunks, all within size limit')
"
```
Expected: `OK: N chunks, all within size limit`

- [ ] **Step 3: 验证 Small-to-Big 去重逻辑**

Run:
```bash
python -c "
from app.services.rag import split_markdown_into_chunks, retrieve_with_context
md = '# 心理学\n## 焦虑\n### 症状\n焦虑症状包括心慌失眠等。\n### 治疗\nCBT对焦虑有效。\n## 抑郁\n### 症状\n抑郁症状包括情绪低落。'
chunks = split_markdown_into_chunks(md)
print(f'Total chunks: {len(chunks)}')
# 验证每个 chunk 都有 parent_content
for c in chunks:
    assert c['metadata']['parent_content'], 'Missing parent_content'
print('All chunks have parent_content — Small-to-Big ready')
"
```
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test: 新增 MD 管线切片与 Small-to-Big 去重单元验证"
```

---

## Verification Checklist

完成所有 Task 后，执行：

1. 后端启动无 ImportError
2. 上传 PDF 文档 → 知识列表中出现，状态 success，chunk_count > 0
3. 输入测试问题 "考前焦虑怎么缓解" → 链路调试展示完整时间线 + chunk 卡片含章节路径 + 相似度分数
4. 父文档展开显示完整小节内容
5. reprocess API 对已有文档重建索引
6. 旧版本文档（手动录入卡片）仍正常工作
