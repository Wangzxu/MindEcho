# 技术细节 01：知识文档「上传 → 嵌入完成」全链路

> 本文档为 MindEcho 技术细节系列第一篇，从代码实现层面完整讲述知识文档从上传到完成向量嵌入（ChromaDB）的链路。
> 覆盖：前端上传交互、后端异步入口、后台入库 Worker、格式转换、对象存储、两层结构化切片、批量 Embedding、向量库写入、状态机、同名覆盖、文档删除与 Chunks 可视化。

---

## 1. 总体架构与数据流

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  教师端浏览器 (KnowledgeManager.vue)                                                  │
│   拖拽/选择文件 (.pdf .docx .doc .txt .md)                                             │
│        │  ① POST /api/admin/knowledge/upload  (multipart/form-data)                 │
│        ▼                                                                             │
│  后端路由 admin.py: upload_knowledge_file  ═══ 异步入口 ═══                          │
│        │  ② SHA256 哈希去重                                                           │
│        │  ③ 同名覆盖检查：file_name 相同 → 删旧版 chunks + 记录                        │
│        │  ④ 写 MySQL knowledge_imports (status=pending, processed_chunks=0)          │
│        │  ⑤ 暂存原始文件到 MinIO（失败仅告警不阻断）                                    │
│        │  ⑥ BackgroundTasks.add_task(process_knowledge_import) 入队                  │
│        ▼                                                                             │
│  立即返回 {import_id, status:"pending", replaced_import_id} ← HTTP 请求在此结束       │
│                                                                                      │
│  ════════════════════ 后台 worker 异步执行（独立线程 + 独立 DB 会话） ═══════════════  │
│  process_knowledge_import(import_id)                                                 │
│        │  ⑦ status: pending → processing（清空进度/错误）                              │
│        │  ⑧ 文件字节来源：优先 upload 传入的内存字节，否则从 MinIO 读取                 │
│        ▼                                                                             │
│  rag.py: ingest_document  ═══ 入库流水线 ═══                                          │
│        │  ⑨ convert_to_markdown()  多格式 → 统一 Markdown                             │
│        │  ⑩ 上传 MinIO：原始文件 + 处理后 MD（失败仅告警不阻断）                         │
│        │  ⑪ split_markdown_into_chunks()  两层结构化切片                               │
│        │  ⑫ llm_service.batch_embed()  批量向量化（100条/批 × 并发4 × 重试3）          │
│        │  ⑬ collection.add()  批量写入 ChromaDB psychology_kb 集合                    │
│        │  ⑭ 更新 MySQL status=success, chunk_count, processed_chunks                 │
│        ▼                                                                             │
│  前端 ①' 轮询 GET /api/admin/knowledge/{import_id}/status 直到 success / failed       │
│        → 任务卡片显示实时进度条 (processed_chunks / chunk_count) + 错误信息            │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**并行路径**（同样写入 `psychology_kb`）：

- 手动录入科普卡片：`POST /api/admin/knowledge/manual`（同步执行，见 §8）
- 旧数据重处理：`POST /api/admin/knowledge/{id}/reprocess`（异步 worker，见 §9）
- 文档删除：`DELETE /api/admin/knowledge/{id}`（见 §10）
- Chunks 可视化：`GET /api/admin/knowledge/{id}/chunks`（见 §11）

---

## 2. 前置初始化（服务启动时）

`backend/app/__init__.py` 的 `lifespan` 在服务启动时按序完成依赖初始化：

| 顺序 | 步骤 | 说明 |
|---|---|---|
| 1 | `init_mysql()` | 建表（含 `knowledge_imports`）+ **列迁移** `_ensure_column`：为已存在的表补齐 `processed_chunks` 列（`create_all` 只建新表，不加旧表列，故需 ALTER 兜底） |
| 2 | `vector_db.init_db()` | 初始化 ChromaDB 持久化客户端，预创建 `psychology_kb` 与 `safety_warnings_kb` 两个集合（cosine 度量） |
| 3 | `llm_service.init_service()` | 加载硅基流动 Embedding/LLM 客户端（`OpenAIEmbeddings`） |
| 4 | `sync_warning_samples_to_vector_db()` | 将 MySQL 安全预警样本批量向量化同步进向量库（失败不阻断） |
| 5 | `storage_service.init_service()` | 连接 MinIO 并确保 bucket（`mindecho-kb`）存在 |

---

## 3. 前端上传交互

`frontend/src/components/admin/KnowledgeManager.vue`（Tab 1: 文档上传）

- **触发**：拖拽 `@drop` 或点击选择 `@change`，`accept=".pdf,.docx,.doc,.txt,.md"`。
- **`uploadFile(file)`**：构造 `FormData` → `axios.post('/api/admin/knowledge/upload', ...)`。
- **异步轮询**：
  1. 上传接口立即返回 `{import_id, replaced_import_id}` → 进入 `startPolling(task)`；
  2. 每 1.5s（`POLL_INTERVAL_MS`）轮询 `GET /api/admin/knowledge/{import_id}/status`；
  3. 按 `status` 更新任务卡片：`processing` 时展示**实时进度条**（`processed_chunks / chunk_count`），`success` → 步骤 4 完成，`failed` → 展示后端 `error_message`；
  4. 组件卸载时 `onUnmounted` 清理全部轮询定时器。
- **覆盖提示**：响应含 `replaced_import_id` 时任务卡片显示"♻️ 已覆盖旧版本（import_id=xxx）"。

---

## 4. 后端异步入口（upload）

`backend/app/routes/admin.py` → `POST /api/admin/knowledge/upload`

```python
@admin_bp.post("/knowledge/upload", response_model=Result[dict])
async def upload_knowledge_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
```

挂在 `admin_bp`（prefix `/api/admin`，依赖 `get_current_admin` 鉴权）。**只做 6 件事，不跑任何重逻辑**：

1. **读取字节流**：`content_bytes = await file.read()`。
2. **SHA256 哈希去重**：`file_hash = sha256(content_bytes)`，若 `knowledge_imports.file_hash` 已存在 → 400「该文档已导入，请勿重复上传」。
3. **同名覆盖检查**（步骤 2 未命中时）：查 `file_name` 相同的旧记录 → 删除其 ChromaDB chunks + 物理删 MySQL 记录，记录 `replaced_import_id`（详见 §10.1）。
4. **写 MySQL 任务记录**（`status="pending"`，`processed_chunks=0`）。
5. **暂存 MinIO**：`storage_service.upload_file(...)`，失败仅 warning（ChromaDB 仍为主存储）。
6. **入队**：`background_tasks.add_task(process_knowledge_import, import_id=task.id, file_bytes=content_bytes, delete_existing=False)`。

**立即返回** `{import_id, chunk_count: 0, status: "pending", replaced_import_id}`。

> **不阻塞 event loop 的原因**：`BackgroundTasks` 对同步 callable 在线程池中执行（Starlette 行为），后台 `ingest_document` 不会卡住聊天 SSE 等其他异步请求。

---

## 5. 后台入库 Worker

`backend/app/routes/admin.py` → `process_knowledge_import(import_id, file_bytes=None, delete_existing=False)`

独立线程 + **独立 DB 会话**（`SessionLocal()`，不复用请求级 session），**全程维护状态机**：

```python
def process_knowledge_import(import_id, file_bytes=None, delete_existing=False):
    db = SessionLocal()
    try:
        task = db.query(KnowledgeImport).filter(KnowledgeImport.id == import_id).first()
        if not task: return                       # 任务已被删（如并发覆盖）→ 静默退出
        if delete_existing:                       # reprocess 场景：先删旧 ChromaDB 数据
            vector_db.get_collection("psychology_kb").delete(where={"import_id": import_id})
        task.status = "processing"; task.processed_chunks = 0; task.error_message = None
        db.commit()
        if file_bytes is None:                    # 未传内存字节（如 reprocess）→ 从 MinIO 读取
            file_bytes = _read_import_source_bytes(task)   # 原始文件 → processed MD 兜底
        chunk_count = ingest_document(file_bytes=..., filename=..., file_hash=..., task=task, db=db)
        # 成功：ingest_document 内部已置 status=success / chunk_count / processed_chunks 并 commit
    except Exception as e:
        db.rollback()
        task.status = "failed"                    # 失败绝不卡死在 processing
        task.error_message = str(e)[:2000]
        db.commit()
    finally:
        db.close()
```

**状态查询接口**：`GET /api/admin/knowledge/{import_id}/status` → 返回 `task.to_dict()`（含 `status / chunk_count / processed_chunks / error_message / file_name`）。

---

## 6. 入库流水线 `ingest_document`

`backend/app/services/rag.py`（L227 起），共 5 步，由后台 worker 调用。

### 6.1 格式转换 → 统一 Markdown

`convert_to_markdown(file_bytes, filename)`（`backend/app/services/converter.py`），按扩展名分发：

| 扩展名 | 主转换器 | 降级方案 | 说明 |
|---|---|---|---|
| `.pdf` | `pymupdf4llm` | `pypdf` 纯文本 | 保留标题层级/表格/图片引用 |
| `.docx` / `.doc` | `mammoth` | `python-docx` 段落 | 保留 Heading 1-6 层级 |
| `.txt` / `.md` | 直通 | — | 视为纯文本 Markdown |
| `.html` / `.htm` | `trafilatura` | `html2text` | 公众号文章去噪 |
| 其他 | 当作文本处理 | — | 未知格式兜底 |

**失败熔断**：转换结果为空 → `raise ValueError("文档转换后内容为空")`。

### 6.2 MinIO 对象存储（物理备份）

两份备份，**失败不阻断主流程**：

| 对象路径 | 内容 |
|---|---|
| `uploads/{file_hash}_{filename}` | 原始文件（审计溯源） |
| `processed/{file_hash}.md` | 处理后 Markdown（可离线重建索引） |

### 6.3 两层结构化切片 `split_markdown_into_chunks`

`backend/app/services/rag.py`（L56 起）：

**第一层：标题边界切片**
- `MarkdownHeaderTextSplitter(headers_to_split_on=[("#","h1"),("##","h2"),("###","h3")], strip_headers=False)`。
- 按相同 `(h1, h2)` 归组拼接为**父文档** `parent_content`（含标题行）。

**第二层：字符级二级切分**
- 将父文档按 `### ` 拆成 H3 段，每段用 `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)` 切分，保证 chunk 边界不跨 H3 标题。

**产出**：每个 chunk 携带结构化元数据：

```python
{
    "content": chunk_text,
    "metadata": {
        "h1": ..., "h2": ..., "h3": ...,       # 章节路径
        "section_id": f"sec_{N}",              # 父文档小节 ID（去重键）
        "parent_content": ...,                 # 完整父文档（Small-to-Big 展开用）
    }
}
```

**失败熔断**：无有效 chunk → `raise ValueError("文档切片后无有效内容")`。

### 6.4 批量 Embedding（batch_embed）

`backend/app/services/llm.py` → `batch_embed(texts, batch_size=100, max_workers=4, max_retries=3)`：

- 每批最多 100 条；最多 **4 个并发批次**（`ThreadPoolExecutor`）；
- 单批失败按 **2^n 秒指数退避**重试 3 次，最终失败该批降级全零向量（不中断主流程）；
- 结果与输入 `texts` 一一对应。
- 正常模式：`OpenAIEmbeddings.embed_documents`（批量一次请求多条，默认模型 `BAAI/bge-large-zh-v1.5`）；
- **Mock 模式**（无 API key）：直接返回全零向量列表。

`ingest_document` 中的嵌入过程：

1. 为每个 chunk 构造**上下文增强文本**：`context_text = f"【{h1 > h2 > h3}】\n{content}"`（路径为空时用文件名）——注意向量化的是带标题路径前缀的文本；
2. 按 **每 50 条一批** 调用 `batch_embed`，每批完成后 `task.processed_chunks += 批内条数` 并 `db.commit()`——**前端进度条的数据来源**。

### 6.5 批量写入 ChromaDB

```python
collection.add(
    ids=[f"{task.id}_chunk_{idx}" for idx in range(len(chunks))],
    embeddings=all_vecs,                       # 一次性批量写入
    documents=context_texts,
    metadatas=[{
        "import_id": task.id, "file_name": filename, "chunk_index": idx,
        "h1": ..., "h2": ..., "h3": ...,
        "section_id": ..., "parent_content": ..., "converter": ...,
    }]
)
```

存储于 `psychology_kb` 集合（cosine 度量，持久化目录 `backend/instance/chroma_db`）。

### 6.6 状态回写

`task.chunk_count = len(chunks); task.processed_chunks = len(chunks); task.status = "success"; db.commit()`，返回 chunk 数。

---

## 7. 状态机（上传任务生命周期）

| 状态 | 含义 | 进入方式 | 退出方式 |
|---|---|---|---|
| `pending` | 已入队，等待 worker 处理 | upload/reprocess 成功 | worker 置 `processing` |
| `processing` | worker 正在转换/切片/向量化 | worker 开始 | 成功 → `success`；异常 → `failed` |
| `success` | 入库完成 | `ingest_document` 收尾 | — |
| `failed` | 入库失败（含原因） | worker 捕获异常 | 可 reprocess 重试 |

**进度字段**：`processed_chunks`（已向量化完成的 chunk 数，随批次递增回写），前端据此渲染进度条。
**失败不再卡死**：worker 用 `try/except` 兜底，任何异常都会把任务置为 `failed` 并写入 `error_message`。

---

## 8. 并行路径：手动录入科普卡片

`POST /api/admin/knowledge/manual`（`admin.py`），同步执行，同样写入 `psychology_kb`，**但不经过 Markdown 管线**：

1. 标题+内容 SHA256 去重（`knowledge_imports.file_hash` 唯一）。
2. 拼装 `manual_text` 上传 MinIO（`manual/{hash}.txt`）。
3. 用**旧版纯文本切片器** `split_text_into_chunks(max_chars=300, overlap=50)` 分别切「概念解释」与「调节技巧」。
4. `llm_service.batch_embed(chunks)` 一次批量向量化，`collection.add` 一次批量写入。
5. **metadata 只有 3 个字段**：
   ```python
   metadatas=[{"import_id": task.id, "file_name": task.file_name, "chunk_index": idx}]
   ```
   ⚠️ 没有 `parent_content` / `section_id` / `h1/h2/h3`——链路调试 Step 4 已兜底：缺父文档时自动拼接子文档（`source: "children_concat"`）。

---

## 9. 并行路径：旧数据重处理（reprocess，异步）

`POST /api/admin/knowledge/{import_id}/reprocess`（`admin.py`）：

1. 任务置 `pending`（清空进度/错误）并入队 `process_knowledge_import(import_id, file_bytes=None, delete_existing=True)`。
2. worker 内：删除旧 ChromaDB chunk → 从 MinIO 读原始文件（失败回退 `processed/{hash}.md`）→ 重新执行完整入库流水线。
3. 用途：把 §8 之前入库、缺 `parent_content` 的旧数据迁移到新管线（补全父文档结构）。

---

## 10. 文档管理：同名覆盖 / 删除

### 10.1 同名覆盖（只留存一份）

上传时（§4 步骤 3）：

```
新文件 file_name 与库中旧记录相同？
   ├─ 否 → 正常新建入库
   └─ 是 → 视为"更新该文档"：
        ① 删除旧记录的全部 ChromaDB chunks（collection.delete(where={"import_id": 旧id})）
        ② 物理删除旧 MySQL 记录
        ③ 新文件正常入队 → 全量重建
        ④ 响应返回 replaced_import_id，前端任务卡片提示"♻️ 已覆盖旧版本"
```

- **去重双闸**：`file_hash` 相同（内容完全一致）→ 400 拒绝；`file_name` 相同但内容不同 → 覆盖更新。
- 覆盖后库中只保留最新一份，不保留版本历史。

### 10.2 删除文档

`DELETE /api/admin/knowledge/{import_id}`：

1. 删除该 import 在 ChromaDB 中的全部 chunks（`where={"import_id": ...}`，失败仅告警）；
2. 物理删除 MySQL 记录；
3. 前端列表"🗑️ 删除"按钮带 `confirm` 二次确认。

---

## 11. Chunks 可视化（含父文档）

`GET /api/admin/knowledge/{import_id}/chunks` 返回每个 chunk 的：

| 字段 | 来源 |
|---|---|
| `chunk_index` | Chroma metadata |
| `content` | Chroma document（上下文增强文本） |
| `h1 / h2 / h3` | Chroma metadata（章节路径） |
| `section_id` | Chroma metadata（父文档小节 ID） |
| `parent_content` | Chroma metadata（**父文档全文**，可折叠展开） |
| `file_name` / `converter` | Chroma metadata |

前端"📋 Chunks"按钮打开**可视化弹窗**：文档基本信息（文件名、chunk 总数）+ 每个 chunk 的章节路径、子 chunk 内容、可折叠的父文档全文；无父文档元数据的旧数据/手动录入显示"⚠️ 无父文档"。

---

## 12. 涉及文件清单

| 层 | 文件 | 职责 |
|---|---|---|
| 前端 | `frontend/src/components/admin/KnowledgeManager.vue` | 上传交互、异步轮询、进度条、知识列表、删除按钮、Chunks 可视化弹窗、链路调试 |
| 路由 | `backend/app/routes/admin.py` | `/knowledge/upload`（异步入口+同名覆盖）、`process_knowledge_import`（worker）、`/knowledge/{id}/status`、`/knowledge/manual`、`/knowledge/{id}/reprocess`、`DELETE /knowledge/{id}`、`/knowledge/{id}/chunks`、`/knowledge/trace` |
| 服务 | `backend/app/services/rag.py` | `ingest_document`（批量嵌入+进度回写）、`split_markdown_into_chunks`、`retrieve_with_context`、`trace_retrieval` |
| 服务 | `backend/app/services/llm.py` | `get_embedding`、`batch_embed`（批量/并发/重试）、LLM 客户端（含 Mock 降级） |
| 服务 | `backend/app/services/converter.py` | 多格式 → Markdown 统一转换 |
| 服务 | `backend/app/services/storage.py` | MinIO 对象存储 |
| 数据 | `backend/app/database/vector.py` | ChromaDB 客户端与集合管理 |
| 数据 | `backend/app/database/mysql.py` | 建表 + `processed_chunks` 列迁移 + 预警样本批量同步 |
| 数据 | `backend/app/models/knowledge.py` | `knowledge_imports` 表模型（含 `processed_chunks`） |
| SQL | `sql/create_tables.sql` | `knowledge_imports` 建表语句（含 `processed_chunks`） |
| 配置 | `backend/config.py` | 模型 / MinIO / 向量库路径等 |

---

## 13. 关键参数速查

| 参数 | 值 | 位置 |
|---|---|---|
| 批量嵌入批大小 | 100 条 | `llm.py batch_embed(batch_size=100)` |
| 批量嵌入并发 | 4 个批次 | `llm.py batch_embed(max_workers=4)` |
| 批量嵌入重试 | 3 次（2^n 秒退避） | `llm.py batch_embed(max_retries=3)` |
| 进度回写粒度 | 每 50 条 | `rag.py ingest_document` |
| 子 chunk 最大字符 | 800 | `rag.py CHUNK_SIZE` |
| chunk 重叠 | 100 | `rag.py CHUNK_OVERLAP` |
| 切分标题层级 | H1/H2/H3 | `rag.py HEADERS_TO_SPLIT` |
| 旧版手动录入切片 | 300/50 | `rag.py split_text_into_chunks` 默认 |
| 前端轮询间隔 | 1.5s | `KnowledgeManager.vue POLL_INTERVAL_MS` |
| Embedding 模型 | `BAAI/bge-large-zh-v1.5`（可配） | `config.py EMBEDDING_MODEL` |
| 向量集合 | `psychology_kb`（cosine） | `rag.py COLLECTION_NAME` |
| MinIO bucket | `mindecho-kb`（可配） | `config.py MINIO_BUCKET` |
