# 技术细节 02：记忆系统架构（四层记忆）

> 本文档讲述 MindEcho 的会话记忆系统实现：**四层记忆**（RAG 召回 / 窗口 / 中期摘要 / 长期画像）
> 如何装载、注入与维护，以及双会话产品形态与触发机制。

---

## 1. 四层记忆架构总览

```
┌─ 每轮注入 prompt（standard_chat_node）─────────────────────────┐
│ ① RAG 召回        rag_cards       专业科普卡片（仅 KNOWLEDGE）  │
│ ② 窗口层          recent_history   最近 12 条原始对话           │
│ ③ 中期记忆        previous_summary 窗口之外的会话摘要（内存）   │
│ ④ 长期画像        user_profile     MySQL user_profiles         │
└────────────────────────────────────────────────────────────────┘
┌─ 写入管线（后台异步）──────────────────────────────────────────┐
│ 每 20 条消息: update_profile_background → 合并更新 user_profiles│
│ 窗口超 20 条: compress_summary_background → 内存中期摘要        │
└────────────────────────────────────────────────────────────────┘
```

| 层 | 数据源 | 存储 | 生命周期 | 注入方式 |
|---|---|---|---|---|
| ① RAG 召回 | `psychology_kb`（ChromaDB） | 向量库 | 持久 | 仅 KNOWLEDGE 意图注入 |
| ② 窗口层 | `chat_messages`（MySQL）/ state | 会话内 state | 最近 12 条 | 原始对话拼接 |
| ③ 中期记忆 | 滚动摘要 LLM | **内存** `midterm_summaries_map` | 进程内 | 摘要文本 |
| ④ 长期画像 | `user_profiles`（MySQL） | 关系型 | 持久 | 结构化 JSON 字段 |

---

## 2. 各层实现细节

### 2.1 ① RAG 召回层（rag_cards）

- **触发**：仅当意图为 `KNOWLEDGE`（用户提问心理学概念/自助方法）时；
- **实现**：`load_context_node` 调用 `rag_service.search_knowledge(db, user_input, limit=2)`，在 `psychology_kb` 集合做 Small-to-Big 混合检索，返回最多 2 张科普卡片；
- **向量复用**：优先复用安全路由阶段缓存的 `user_input_embedding`，避免重复计算；
- **注入**：`standard_chat_node` 将卡片拼进 prompt 的【专业知识库检索内容】段。

### 2.2 ② 窗口层（recent_history）

- **定义**：最近 12 条消息（6 轮对话）的原始文本；
- **来源**：LangGraph state 中的 `history_messages` 滑动窗口；服务重启后从 MySQL 加载最近 12 条（`limit(12)`）回补；
- **排除当前轮**：注入时剔除刚插入的当前用户输入（`history[:-1]`），只展示已完成的对话；
- **注入格式**：
  ```
  - 学生: ...
  - AI: ...
  ```

### 2.3 ③ 中期记忆层（previous_summary）

- **定义**：12 条窗口之外的较老对话，压缩为 150 字以内的滚动摘要；
- **存储**：进程内内存字典 `midterm_summaries_map = { session_id: summary }`，**不落库**，服务重启即清空；
- **目的**：应对高强度连续聊天——连续聊 50 条时，前 38 条由摘要承载，上下文不丢失，同时不污染持久化存储；
- **写入**：`compress_summary_background`（后台异步）把窗口外的对话连同旧摘要一起交给摘要模型合并生成新摘要，覆盖写入内存；
- **读取**：`load_context_node` 从 `midterm_summaries_map.get(session_id, "无往期历史。")` 读取。

### 2.4 ④ 长期画像层（user_profile）

- **存储**：MySQL `user_profiles` 表，结构：
  ```python
  nickname: str                # 用户昵称
  core_stressors: List[str]    # 核心压力源
  effective_coping_methods: List[str]  # 历史有效应对方法
  entity_relation_map: Dict[str, str]  # 关键人际关系网
  ```
- **写入**：`update_profile_background`（后台异步）每 20 条消息触发一次，将最近 20 条对话原文 + 现有画像交给 `extract_profile`，由 LLM 合并更新画像字段；
- **读取**：`load_context_node` 查询 `UserProfile` 并注入 prompt 的【长期记忆与用户画像】段。

---

## 3. 数据流（一次消息的完整链路）

```
用户消息 → filter_and_route（三级安全路由 + 意图分类）
    │
    ├─ CRISIS → crisis_handler（固定预案，不注入记忆）
    │
    └─ 其他 → load_context（装载四层记忆）
         │   ├─ ① RAG: intent==KNOWLEDGE 时 search_knowledge
         │   ├─ ② 窗口: history_messages 最近12条 → recent_history
         │   ├─ ③ 中期: midterm_summaries_map[session_id] → previous_summary
         │   └─ ④ 画像: user_profiles → user_profile
         ▼
    standard_chat（拼装 system prompt → 流式回复）
         ▼
    save_message
         ├─ 非无痕: AI 回复落库
         ├─ 每20条: 后台 update_profile_background（画像合并）
         └─ 窗口>20条: 后台 compress_summary_background（内存摘要）
```

Prompt 组装结构（`standard_chat_node`）：

```
【系统人设】AI 心理委员「小影」
【回复风格约束】按意图动态注入
【长期记忆与用户画像】昵称 / 压力源 / 有效技巧 / 关系网
【专业知识库检索内容】rag_cards（仅 KNOWLEDGE）
【会话历史记录】
   - 中期记忆（窗口之外的对话摘要）: previous_summary
   - 最近对话窗口: recent_history
【当前输入】学生: {user_input}
```

---

## 4. 触发机制

| 任务 | 触发条件 | 频率 | 数据来源 | 落库? |
|---|---|---|---|---|
| 画像提取 `update_profile_background` | `消息数 % 20 == 0` | 每 10 轮一次 | 常规：MySQL 最近 20 条；无痕：state 窗口 | ✅ 更新 `user_profiles` |
| 中期摘要 `compress_summary_background` | `len(history) > 20` | 窗口涨到 20 条压一次 | state 滑动窗口 12 条之外 | ❌ 仅内存 |

- 画像计数：常规会话以**数据库真实消息数**为准（防重启重置）；无痕会话用 state 累计数；
- 摘要压缩：压缩后窗口回到 12 条，继续聊到 20 条再触发，循环进行。

---

## 5. 双会话产品形态

前端不提供多会话列表，**每个用户固定两个会话**（注册时创建，存量用户首次进入自动补齐）：

| 模式 | 固定会话名 | 消息存储 | 记忆 |
|---|---|---|---|
| 💬 直接聊天 | `直接聊天` | MySQL（落库） | 四层全量生效（窗口从库加载） |
| 🔒 无痕树洞 | `无痕树洞` | 不落库（仅内存） | 画像仅内存；中期摘要内存 |

- **注册即建双会话**：`auth.py register_user` 同时创建 `ChatSession(title="直接聊天", is_anonymous=False)` 与 `ChatSession(title="无痕树洞", is_anonymous=True)`；
- **固定名称**：标题固定，不做自动命名；`Chat.vue` 头部与 `ChatSidebar` 固定展示当前模式名称；
- **存量兼容**：`Chat.vue ensureSession` 按 `(is_anonymous, title)` 查找固定会话，找不到则自动创建；
- **用户画像可视化**：`ProfilePanel.vue` 调用 `GET /api/auth/profile` 展示昵称、核心压力源、应对方法、关系网。

---

## 6. 关键代码位置

| 模块 | 文件 | 说明 |
|---|---|---|
| 四层注入 | `backend/app/services/workflow/nodes.py` `load_context_node` | 装载窗口/摘要/画像/RAG |
| Prompt 组装 | 同文件 `standard_chat_node` | 画像 + RAG + 中期摘要 + 窗口 |
| 中期摘要写入 | 同文件 `compress_summary_background` | 内存 map，不落库 |
| 画像更新 | 同文件 `update_profile_background` | 每 20 条合并画像 |
| 触发调度 | 同文件 `save_message_node` | 消息落库 + 画像/摘要触发判断 |
| 状态字段 | `backend/app/services/workflow/state.py` | 4 部分记忆字段 |
| 画像模型 | `backend/app/models/user_profile.py` | `core_stressors` 等字段 |
| 用户画像接口 | `backend/app/routes/auth.py` `GET /api/auth/profile` | 前端画像可视化 |
| 双会话创建 | 同文件 `register_user` | 注册即建两个固定会话 |
| 前端画像面板 | `frontend/src/components/chat/ProfilePanel.vue` | 用户端画像弹窗 |
| 双模式侧边栏 | `frontend/src/components/chat/ChatSidebar.vue` | 直接聊天/无痕树洞切换 |

---

## 7. 关键参数速查

| 参数 | 值 | 位置 |
|---|---|---|
| 窗口大小（最近消息条数） | 12 条 | `nodes.py load_context_node` |
| 画像提取触发 | 每 20 条消息（`% 20 == 0`） | `nodes.py save_message_node` |
| 中期摘要触发 | 窗口 > 20 条 | 同文件 |
| 摘要长度上限 | 150 字 | `compress_summary_background` |
| RAG 召回条数 | 2 张卡片（仅 KNOWLEDGE） | `load_context_node` |
| 摘要存储 | 内存 `midterm_summaries_map` | `nodes.py` 模块级 |
| 画像存储 | MySQL `user_profiles` | `user_profile.py` |
