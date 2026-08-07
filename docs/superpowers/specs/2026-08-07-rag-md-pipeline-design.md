# RAG 统一 Markdown 管线与链路可视化设计

**日期**: 2026-08-07  
**状态**: 设计中  
**关联**: MindEcho 心理咨询平台 - 知识库模块

---

## 1. 背景与动机

### 1.1 当前架构问题

当前 RAG pipeline 存在结构性的上游缺陷：

```
原始文档 → [丢失结构的文本提取] → [盲切 300 字符] → [无上下文的 chunk]
              ↑                        ↑                    ↑
         pypdf 展平一切          RecursiveCharSplit       metadata 只有
         python-docx 无层级      不理解标题边界          file_name + index
```

**具体问题：**

| 问题 | 表现 | 根因 |
|------|------|------|
| 混合召回不如纯向量 | BM25 的 TF 分量在 300 字符内退化 | chunk 太短，关键词基本只出现 1 次 |
| 检索结果缺上下文 | LLM 收到语义碎片，无法定位知识来源 | 标题层级丢失，chunk 不自包含 |
| 无法增量重建索引 | 改策略就要重新上传原始文件 | MinIO 存了原始二进制但从不复用 |
| 扩展格式成本高 | 每加一种格式要改提取+切片两处 | 没有统一中间层 |

### 1.2 约束条件

- **微调模型上下文窗口**: 2048 tokens
- **检索可用预算**: ~1300 tokens（约 800-1000 中文字）
- **知识库内容**: 心理学论文 PDF + 校园公众号文章 + 手动录入卡片
- **目标用户**: 在校学生（心理咨询场景）
- **开发语言**: Python 3.11 后端 / Vue 3 前端
- **现有基础设施**: MinIO 对象存储、ChromaDB 向量库、MySQL 元数据

---

## 2. 方案设计

### 2.1 核心思想：统一 Markdown 中间层

在所有文档格式之上加一层 Markdown 抽象，使下游的切片、检索、可视化都面向统一的结构化文本。

```
PDF/DOCX/TXT/MD/HTML
       ↓
  [格式特定转换器]    ← 唯一感知格式差异的地方
       ↓
    Markdown          ← 统一中间层（标题/列表/表格结构完整）
       ↓
MarkdownHeaderTextSplitter  ← 标题边界感知切片
       ↓
  结构化 Chunk          ← 每个chunk自带 H1>H2>H3 路径
       ↓
  Embedding → ChromaDB   ← 小chunk入索引，父文档存metadata
       ↓
Small-to-Big 检索        ← 用小chunk搜，返回父文档（完整小节）
```

### 2.2 文档转换器（新增 `converter.py`）

| 源格式 | 转换工具 | 输出特点 |
|--------|---------|---------|
| PDF | `pymupdf4llm` | 保留标题层级、表格转 MD table、提取图片引用 |
| DOCX | `mammoth` | 完整保留 Heading 1-6 层级、列表嵌套 |
| TXT | 直通 | 无需转换 |
| MD | 直通 | 无需转换 |
| HTML（公众号） | `trafilatura` + `html2text` | 去噪提取正文 + 标题结构 |

**降级策略**: 每种转换器失败时 fallback 到当前纯文本提取逻辑，确保兼容性。

**输出契约**:
```python
def convert_to_markdown(file_bytes: bytes, filename: str) -> tuple[str, dict]:
    """
    Returns:
        markdown_text: 结构化 Markdown 文本
        metadata: {"title": str, "source_format": str, "page_count": int|None, ...}
    """
```

### 2.3 切片策略（重构 `rag.py`）

**两层切片架构**:

```
第一层: MarkdownHeaderTextSplitter (按 H1/H2/H3 边界)
  "# CBT 综述"           → section
  "## 理论基础"           → section
  "### 认知模型"          → section (成为子 chunk)
  "认知模型认为..."       → 归属到 ### 认知模型

第二层: RecursiveCharacterTextSplitter (chunk_size=800, overlap=100)
  对过长的 section 内部做二级切分，保证每个 chunk ≤ 800 字符
```

**参数设定**:

| 参数 | 值 | 理由 |
|------|-----|------|
| chunk_size | 800 字符 | 2 个 chunk 填满 1300 token 检索预算 |
| chunk_overlap | 100 字符 | 保护边界语义连续性 |
| headers_to_split_on | H1, H2, H3 | 心理学论文的标准层级深度 |
| strip_headers | False | 保留标题在 chunk 中，信息密度更高 |

### 2.4 父子文档检索（Small-to-Big）

```
索引层: H3 级别的子 chunk（500-800 字符）→ Embedding → ChromaDB
         ↓ top-2 命中
展开层: 子 chunk 对应的 H2 父文档（完整小节，约 1500-3000 字符）
         ↓
去重合并，token 预算控制 ≤ 1300
         ↓
注入 LLM
```

**ChromaDB 存储结构**:
```python
{
    "id": "42_chunk_5",
    "document": "### 认知重构技术\n认知重构是CBT的核心技术...",
    "embedding": [...],
    "metadata": {
        "import_id": 42,
        "file_name": "CBT综述.pdf",
        "chunk_index": 5,
        "h1": "认知行为疗法",
        "h2": "治疗方法",
        "h3": "认知重构技术",
        "parent_doc_id": "42_section_2",       # ← 指向父文档
        "parent_content": "## 治疗方法\n### 认知重构技术\n...(完整小节)..."  # ← 父文档内联存储
    }
}
```

### 2.5 MinIO 存储策略升级

```
MinIO Bucket: mindecho-kb
├── uploads/{file_hash}_{filename}     ← 原始文件（不可变，审计溯源）
└── processed/{file_hash}.md           ← 提取后的 Markdown（可重建索引）
```

- `processed/` 下的 MD 可用于重新切片、重新向量化，无需重新上传原始文件
- 切换 embedding 模型或切片策略时，直接从 MD 重建整个索引

### 2.6 检索参数

| 参数 | 值 | 理由 |
|------|-----|------|
| top-k（子 chunk） | 3 | 召回 3 个最相关的小块 |
| 展开到父文档 | top-2（去重后） | 3 个子 chunk 可能归属于 2 个父文档 |
| 总注入 token | ≤ 1300 | 2048 - 750(system+历史+回复) = 1300 |
| 相似度阈值 | cosine ≥ 0.5 | 低于此值不纳入召回 |
| 度量空间 | cosine | ChromaDB 现有配置 |

---

## 3. 前端可视化设计

### 3.1 入口：管理端侧边栏新增菜单

```
侧边栏菜单新增：
  { id: 'knowledge', label: '知识库管理', icon: '📚' }
```

路由复用 `/admin`，通过 `activeMenu` 切换组件。

### 3.2 组件结构

```
Admin.vue
  └── <KnowledgeManager>           ← 新增组件
        ├── Tab 1: 文档上传
        │     ├── 拖拽上传区（PDF/DOCX/MD/TXT）
        │     └── 处理进度（转换→切片→向量化 步骤可视化）
        ├── Tab 2: 知识列表
        │     └── 分页表格（复用现有 API）
        └── Tab 3: 链路调试 ← 核心
              ├── 查询输入框 + 检索按钮
              ├── 链路流程图（Query → Embedding → Search → Chunks → LLM）
              ├── 命中 chunk 详情卡片（含相似度、章节路径、内容高亮）
              └── 父文档展开查看
```

### 3.3 链路调试 Tab 视觉设计

**垂直时间线布局**，每个步骤一个卡片：

```
🔍 用户查询
  "焦虑障碍怎么治疗？"
  ┃
  ▼ 120ms
🧮 Embedding 向量化
  模型: BAAI/bge-large-zh-v1.5
  维度: 1024
  ┃
  ▼ 45ms
🗄️ ChromaDB 向量检索
  集合: psychology_kb  |  top-3  |  度量: cosine
  ┃
  ├─ 🥇 Chunk #1  相似度: 0.89  ──────────────
  │  📄 CBT综述.pdf
  │  📂 认知行为疗法 > 临床应用 > 焦虑障碍治疗
  │  ┌──────────────────────────────────────┐
  │  │ ### 焦虑障碍治疗                       │
  │  │ 焦虑障碍的CBT治疗包括以下核心步骤：     │
  │  │ 1. 心理教育 - 帮助来访者理解...        │
  │  │ 2. 认知重构 - 识别并挑战...            │
  │  └──────────────────────────────────────┘
  │  [展开父文档 ▼]
  │
  ├─ 🥈 Chunk #2  相似度: 0.76  ──────────────
  │  ...
  │
  ┃
  ▼
📤 父文档展开 (Small-to-Big)
  3 个子chunk → 2 个父文档 → 去重 → 1240 tokens
  ┃
  ▼
🤖 LLM 生成回复
  模型: Qwen/Qwen2.5-7B-Instruct
```

### 3.4 新增后端 API

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/admin/knowledge/trace` | 输入 query，返回全链路追踪数据 |
| GET | `/api/admin/knowledge/{id}/chunks` | 查看某文档的所有 chunk 及章节结构 |
| POST | `/api/admin/knowledge/{id}/reprocess` | 重新转换+切片+向量化 |
| GET | `/api/admin/knowledge/{id}/markdown` | 获取处理后存储的 MD 原文（调试用） |

---

## 4. 文件变更清单

### 4.1 新增文件

| 文件 | 内容 |
|------|------|
| `backend/app/services/converter.py` | 多格式→MD 转换器 |
| `frontend/src/components/admin/KnowledgeManager.vue` | 知识库管理三合一组件 |

### 4.2 修改文件

| 文件 | 改动 |
|------|------|
| `backend/app/services/rag.py` | 替换切片策略、新增父子文档检索、新增 trace 方法 |
| `backend/app/routes/admin.py` | 新增 4 个知识库 API 端点 |
| `backend/requirements.txt` | 新增 `pymupdf4llm`、`mammoth`、`trafilatura` |
| `frontend/src/pages/Admin.vue` | 侧边栏新菜单项 + 引入 KnowledgeManager |
| `frontend/src/router/index.js` | 无需改动（复用 /admin 路由） |

### 4.3 不修改文件

| 文件 | 原因 |
|------|------|
| `backend/app/services/storage.py` | 接口不变，仅下游调用方式变化 |
| `backend/app/database/vector.py` | ChromaDB 接口不变 |
| `backend/app/models/knowledge.py` | 表结构不变（metadata 字段足够承载新信息） |
| `backend/config.py` | 无需新增配置项 |

---

## 5. 风险与降级

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| pymupdf4llm 转换复杂排版 PDF 失败 | 中 | 单文档无法入库 | fallback 到现有 pypdf 纯文本提取 |
| mammoth 不支持某些 DOCX 特性 | 低 | 部分格式丢失 | fallback 到 python-docx 提取 |
| 父子展开后超 1300 token | 中 | LLM 截断 | 截断父文档末尾 + 日志告警 |
| 旧入库文档与新管线不兼容 | 高 | 旧文档检索不到结构化上下文 | reprocess API 手动触发重处理，或标记为 legacy |

---

## 6. 验收标准

1. 上传 PDF/DOCX/TXT/MD 文档，均能正确入库并显示在知识列表中
2. 链路调试输入测试问题，可视化展示完整的 Query→Embedding→Search→Chunks 流程
3. 命中 chunk 卡片展示章节路径（H1>H2>H3）和相似度分数
4. 父文档展开功能正确返回完整小节内容
5. 旧版本文档可通过 reprocess API 迁移到新管线
6. 转换失败的文档优雅降级，不影响入库流程
