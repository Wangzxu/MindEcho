# MindEcho (FastAPI) 后端骨架说明书

我们已经成功将 MindEcho 后端框架由 Flask 迁移至 **FastAPI**，拆分了数据模型与数据契约，并引入了外部配置文件管理安全红线词库。
同时，我们完成了首个核心业务功能——**登录与注册模块**的开发，设计了账号鉴权（`users`）与心理画像（`user_profiles`）1对1分离的高隐私数据隔离架构。

## 1. 后端骨架目录结构

重构并增加登录注册鉴权后的后端代码结构如下所示：

```
backend/
├── app.py                      # 后端入口文件 (使用 Uvicorn 运行)
├── config.py                   # 环境变量配置加载模块 (含 JWT 鉴权配置)
├── requirements.txt            # 项目依赖声明列表 (包含 PyJWT 与 bcrypt 依赖)
├── .env                        # 本地环境变量配置文件
├── .env.example                # 环境变量配置模板
├── verify_backend.py           # 骨架与集成验证脚本 (适配用户注册登录与多子模型)
└── app/                        # 应用核心包
    ├── __init__.py             # FastAPI App 工厂函数与 Lifespan 生命周期定义
    ├── data/                   # 外部静态数据/配置库
    │   └── safety_rules.yaml   # 安全红线硬规则敏感词库
    ├── database/               # 数据库集成层
    │   ├── __init__.py
    │   ├── mysql.py            # MySQL (SQLAlchemy) Session 依赖注入源
    │   └── vector.py           # ChromaDB 向量数据库持久客户端
    ├── models/                 # SQLAlchemy 物理数据模型包 (已拆分并隔离)
    │   ├── __init__.py         # 统一导出
    │   ├── user.py             # User 账号凭证与鉴权角色模型 (修改)
    │   ├── user_profile.py     # UserProfile 敏感心理画像模型 (新建)
    │   ├── session.py          # ChatSession 会话模型
    │   ├── message.py          # ChatMessage 对话明细模型
    │   └── knowledge.py        # KnowledgeCard 心理科普卡片模型
    ├── schemas/                # Pydantic 传输模型与数据契约包 (已拆分)
    │   ├── __init__.py         # 统一导出
    │   ├── base.py             # 统一响应结构 Result
    │   ├── auth.py             # 注册、登录、Token及画像校验契约 (新建)
    │   ├── session.py          # 会话接口请求与响应模型
    │   ├── message.py          # 消息接口请求与响应模型
    │   └── health.py           # 健康状态诊断实体
    ├── services/               # 业务核心服务层
    │   ├── __init__.py
    │   ├── auth_service.py     # 密码 Bcrypt 哈希与 JWT Token 生成校验服务 (新建)
    │   ├── llm.py              # 硅基流动 API 客户端封装
    │   ├── intent.py           # 三级混合路由意图分类服务
    │   └── rag.py              # 向量库同步与混合检索服务
    └── routes/                 # FastAPI APIRouter 路由控制层
        ├── __init__.py
        ├── auth.py             # 注册、登录路由与全局 get_current_user 鉴权依赖项 (新建)
        ├── health.py           # 系统健康状况诊断接口
        └── chat.py             # 心理会话管理与 sse-starlette 流式接口 (已关联登录用户)
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

---

## 3. 验证与诊断指南

一键诊断验证脚本 [verify_backend.py](file:///f:/python_dev/projects/MindEcho/backend/verify_backend.py) 已经升级。它会在执行数据库诊断时自动尝试通过 `auth_service` 生成哈希密码写入测试用户，并同步初始化其画像表 `user_profiles`。

您可以在终端中运行该脚本测试组件及连接状态：
```bash
python verify_backend.py
```
