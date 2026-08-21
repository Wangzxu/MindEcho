# MindEcho (FastAPI) 后端架构说明书

MindEcho 后端基于 **FastAPI** 构建，拆分了数据模型与数据契约，采用 **LangGraph 状态化工作流** 驱动对话生成，并以 MySQL + ChromaDB 双轨存储支撑"感性右脑 + 理性左脑"双驱动架构。

## 1. 后端目录结构

```
backend/
├── main.py                     # 后端入口文件 (Uvicorn 运行，端口 5000)
├── app.py                      # 旧入口提示（已迁移至 main.py，避免与 app/ 冲突）
├── config.py                   # 环境变量配置加载模块 (模型/MinIO/Chroma/JWT)
├── requirements.txt            # 项目依赖声明列表
├── .env                        # 本地环境变量配置文件
├── .env.example                # 环境变量配置模板
├── verify_backend.py           # 骨架与集成验证脚本
└── app/                        # 应用核心包
    ├── __init__.py             # FastAPI App 工厂函数与 Lifespan 生命周期
    ├── database/               # 数据库集成层
    │   ├── __init__.py
    │   ├── mysql.py            # MySQL (SQLAlchemy) Session + 建表迁移
    │   └── vector.py           # ChromaDB 向量数据库持久客户端
    ├── models/                 # SQLAlchemy 物理数据模型包
    │   ├── __init__.py         # 统一导出
    │   ├── user.py             # User 账号凭证与角色模型
    │   ├── user_profile.py     # UserProfile 心理画像模型（长期记忆）
    │   ├── session.py          # ChatSession 会话模型（固定双会话）
    │   ├── message.py          # ChatMessage 对话明细模型
    │   ├── knowledge.py        # KnowledgeImport 文档导入任务模型
    │   ├── safety_keyword.py   # SafetyKeyword 敏感词模型
    │   ├── safety_warning_sample.py  # SafetyWarningSample 预警向量样本
    │   └── security_activity_log.py  # SecurityActivityLog 安全日志
    ├── schemas/                # Pydantic 传输模型与数据契约包
    │   ├── __init__.py
    │   ├── base.py             # 统一响应结构 Result
    │   ├── auth.py             # 注册、登录、Token及画像契约
    │   ├── session.py / message.py / health.py / safety.py / knowledge.py
    ├── services/               # 业务核心服务层
    │   ├── __init__.py
    │   ├── auth_service.py     # 密码 Bcrypt 哈希与 JWT Token 服务
    │   ├── llm.py              # 硅基流动 LLM/Embedding 客户端（含批量嵌入、重写、提炼）
    │   ├── rag.py              # RAG 入库管线 + Small-to-Big 检索 + 链路追踪
    │   ├── intent.py           # 意图路由服务（安全词热加载）
    │   ├── converter.py        # 多格式文档 → Markdown 统一转换器
    │   ├── storage.py          # MinIO 对象存储服务
    │   └── workflow/           # LangGraph 状态化工作流（核心生成链路）
    │       ├── __init__.py
    │       ├── graph.py        # StateGraph 节点编排与条件边
    │       ├── state.py        # ChatWorkflowState 状态定义
    │       └── nodes.py        # 五节点：路由/装载/危机/生成/持久化
    └── routes/                 # FastAPI APIRouter 路由控制层
        ├── __init__.py
        ├── auth.py             # 注册、登录、get_current_user/get_current_admin 鉴权
        ├── health.py           # 系统健康状况诊断接口
        ├── chat.py             # 心理会话 + SSE 流式接口
        └── admin.py            # 教师端后台（安全词/学生画像/知识库管理）
```

以及在工作区根目录下导出的数据库脚本：
- **[sql/create_tables.sql](file:///f:/python_dev/projects/MindEcho/sql/create_tables.sql)**：包含物理 MySQL DDL 建表语句（含字段注释、外键级联与索引配置）。

---

## 2. 核心组件与功能实现详情

### ⚡ 1. 登录注册鉴权模块 (Authentication System)
- **密码哈希安全**：在 [auth_service.py](file:///f:/python_dev/projects/MindEcho/backend/app/services/auth_service.py) 中，使用 **Bcrypt** 算法对用户明文密码进行安全加盐哈希，并提供高效的校验接口。
- **无状态令牌（JWT）**：登录成功后，系统在 Token 载荷中压入用户名、角色与唯一 ID，并以 `HS256` 算法生成 JWT。令牌生命周期默认为 1 天，时效参数在 `.env` 中控制。
- **安全依赖注入**：在 [routes/auth.py](file:///f:/python_dev/projects/MindEcho/backend/app/routes/auth.py) 中提供了依赖项 `get_current_user`。此方法通过 FastAPI 的 Depends 机制自动拦截包含 Bearer 令牌的请求头。如果 Token 伪造、过期或该账号未激活（`is_active=False`），则抛出对应的 HTTP 认证异常。

### 🗄️ 2. 画像隔离设计 (Privacy & Decoupling)
为了保障心理数据的绝对私密：
- **表结构拆分**：将账号凭证 `users` 与心理特征画像 `user_profiles` 进行了 1:1 拆分。[user.py](file:///f:/python_dev/projects/MindEcho/backend/app/models/user.py) 仅存储基本鉴权凭证、角色类型（管理员 `admin` / 普通学生 `student`）以及激活状态。敏感的心理画像则全数转移至 [user_profile.py](file:///f:/python_dev/projects/MindEcho/backend/app/models/user_profile.py) 中。
- **逻辑关联**：在 [chat.py](file:///f:/python_dev/projects/MindEcho/backend/app/routes/chat.py) 中，创建会话时不再依赖硬编码的学生账号，而是通过 `Depends(get_current_user)` 获取。非匿名会话将自动关联登录用户的 ID，并在 SSE 大模型检索上下文时，通过 `user.profile` 关系链安全、静默地加载画像（压力源、有效调适方法等）。

### 🛡️ 3. 数据隔离鉴权 (Security Gate)
- 会话历史 `/api/chat/session/{session_id}/history` 与发送消息 `/api/chat/message` 新增了严格的所有权校验：非匿名会话中，非拥有者且非 `admin` 管理员的角色将直接触发 `HTTP 403 Forbidden` 拦截，杜绝了会话隐私越权漏洞。

### 🔀 4. 对话生成工作流 (LangGraph)
对话生成由 `services/workflow/` 下的 LangGraph 状态化工作流驱动，共 5 个节点：

| 节点 | 职责 |
|---|---|
| `filter_and_route` | 三级安全路由（敏感词 / LLM 三分类 / 预警向量，Level2+3 并行） |
| `load_context` | 装载四层记忆（RAG 卡片 + 窗口 + 中期摘要 + 画像），KNOWLEDGE 时做查询重写 + Small-to-Big 检索 + 卡片提炼 |
| `crisis_handler` | 危机固定预案（热线/地址），不注入记忆 |
| `standard_chat` | 拼装 prompt → 流式生成（意图定制温度 + 两级降级链） |
| `save_message` | 消息落库 + 记忆维护（画像滑窗 + 摘要合并一次调用） |

详见 [tech-details/02-memory-architecture.md](file:///F:/python_dev/projects/MindEcho/docx/tech-details/02-memory-architecture.md) 与 [tech-details/03-generation-optimization.md](file:///F:/python_dev/projects/MindEcho/docx/tech-details/03-generation-optimization.md)。

---

## 3. 验证与诊断指南

一键诊断验证脚本 [verify_backend.py](file:///f:/python_dev/projects/MindEcho/backend/verify_backend.py) 已经升级。它会在执行数据库诊断时自动尝试通过 `auth_service` 生成哈希密码写入测试用户，并同步初始化其画像表 `user_profiles`。

您可以在终端中运行该脚本测试组件及连接状态：
```bash
python verify_backend.py
```
