# 技术细节 03：生成链路优化（回答生成）

> 本文档讲述 MindEcho 回答生成链路的实现与优化：从用户输入到最终回复的完整处理流程，
> 覆盖意图路由并行化、查询重写、Small-to-Big 检索、知识卡片提炼、意图定制温度、失败降级，
> 以及记忆维护的滑窗触发与合并提取。

---

## 1. 生成链路总览

```
用户输入
  → ① filter_and_route  三级安全路由（敏感词 / LLM三分类 / 预警向量，Level2+3 并行）
  → ② load_context      四层记忆装载 + RAG（查询重写 → Small-to-Big → 卡片提炼）
  → ③ standard_chat     拼装 system prompt → 流式生成（意图定制温度，两级降级链）
  → ④ save_message      落库 + 记忆维护（滑窗触发，画像+摘要合并一次调用）
```

---

## 2. 意图路由（filter_and_route_node）

### 2.1 三级安全路由

| 级别 | 机制 | 触发条件 | 说明 |
|---|---|---|---|
| Level 1 | 本地敏感词硬匹配 | `SafetyKeyword` 表中命中 | 不耗 API，毫秒级熔断 |
| Level 2 | 轻量大模型三分类 | Level 1 未命中 | Qwen 分类 `KNOWLEDGE / EMOTION / CRISIS` |
| Level 3 | 预警语义向量检索 | 始终执行 | `safety_warnings_kb` 相似度 > 0.85 → 升级 CRISIS |

### 2.2 并行化（TTFT 优化）

- **Level 2 与 Level 3 并行执行**（`asyncio.gather`）：两者只依赖 `user_input`，互不依赖，并行省一个 LLM 调用时延；
- 同步 LLM 调用用 `asyncio.to_thread` 包装，避免阻塞事件循环；
- 合并规则：Level 2 判 CRISIS 时忽略 Level 3 结果；否则 Level 3 相似度 > 0.85 可将 EMOTION/KNOWLEDGE 升级为 CRISIS。

---

## 3. 上下文装载与 RAG（load_context_node）

### 3.1 查询重写（Query Rewriting）

- `llm_service.rewrite_query(user_input)`：口语化长文本 → 1~2 个纯粹心理检索词；
- 例："这两天躺在床上脑子乱转，一闭眼就是明天的PPT，烦死了" → "焦虑引起的失眠 调节小技巧"；
- 用 Qwen simple 模型（temperature=0.0, max_tokens=30），Mock/失败回退原文本；
- **向量重算**：改写后的查询词需重新 embedding（不复用安全路由阶段的原始输入向量）。

### 3.2 Small-to-Big 检索

- `retrieve_with_context`：命中 top-3 子 chunk → 展开为完整父文档小节（H2 层级）；
- 返回章节路径 h1/h2/h3、父文档全文、相似度分数；
- 前端卡片 title 用 `h1 > h2 > h3` 拼接（无章节时用文件名兜底）。

### 3.3 知识卡片提炼（refine_knowledge_card）

- 父文档全文 → 结构化卡片 `{concept 概念释义, tip 调节技巧}`（Qwen，temperature=0.3）；
- 对 top-2 卡片并行提炼（`asyncio.gather` + `asyncio.to_thread`）；
- 失败回退：concept 取原文前 200 字，tip 为空；
- 注入 prompt 时优先展示 concept + tip，未提炼回退全文。

---

## 4. 回复生成（standard_chat_node）

### 4.1 意图定制温度

```python
intent_temperature = {"KNOWLEDGE": 0.3, "EMOTION": 0.8}.get(intent, 0.7)
```

| 意图 | 温度 | 理由 |
|---|---|---|
| KNOWLEDGE | 0.3 | 科普重准确，低随机性 |
| EMOTION | 0.8 | 共情重自然生动，高随机性 |
| 其他（默认） | 0.7 | 平衡 |

### 4.2 Prompt 组装（四层记忆 + RAG 卡片）

```
【系统人设】AI 心理委员「小影」
【回复风格约束】按意图动态注入
【长期记忆与用户画像】昵称 / 压力源(≤5) / 有效技巧(≤5) / 关系网(≤5)
【专业知识库检索内容】概念释义 + 调节技巧（仅 KNOWLEDGE）
【会话历史记录】中期摘要 + 最近 12 条窗口
【当前输入】学生: {user_input}
```

- **画像字段裁剪**：压力源/应对方法各取前 5 条、关系网前 5 条，控制 prompt 长度。

### 4.3 两级失败降级

```
DeepSeek-V3 流式生成（意图温度）
   │ 成功 → 正常流式输出
   ▼ 失败
Qwen 简单模型非流式兜底（同温度）
   │ 成功 → 输出降级回复
   ▼ 失败
固定安抚话术（"听到你说了这么多…我一直在这里陪着你。"）
```

- 降级不再向 SSE 抛 error，用户始终得到回复；
- 降级时推送 `metadata.fallback: true` 供前端标识。

---

## 5. 记忆维护（save_message_node）

### 5.1 滑窗触发（画像提取）

- 旧逻辑：`消息数 % 20 == 0`（恰好 20 的倍数才触发，19 条停手不更新）；
- 新逻辑：**`消息数 ≥ 20 且 自上次提取增量 ≥ 10`**（滑窗触发）；
- 状态字段 `last_profile_message_count` 记录上次提取时的消息数，随 state 流转。

### 5.2 合并提取（update_memory_background）

一次后台 LLM 调用同时完成画像 + 摘要：

```
update_memory_background（触发条件：画像滑窗 或 窗口 > 20 条）
  → extract_memory_bundle（Qwen simple，一次调用）
       ├─ 画像增量 → 合并更新 MySQL user_profiles
       └─ 滚动摘要 → 覆盖内存 midterm_summaries_map
```

- 替代原两条独立管线（`update_profile_background` + `compress_summary_background`），减少一次重复分析与 LLM 调用；
- `history_segment` 为空时只做摘要；`to_compress_segment` 为空时只做画像；
- 窗口裁剪逻辑保留：`len(history) > 20` 时窗口回到 12 条。

---

## 6. 关键代码位置

| 模块 | 文件 | 说明 |
|---|---|---|
| 路由并行化 | `backend/app/services/workflow/nodes.py` `filter_and_route_node` | Level2+3 asyncio.gather 并行 |
| 查询重写 | `backend/app/services/llm.py` `rewrite_query` | 口语 → 检索词 |
| Small-to-Big | `backend/app/services/rag.py` `retrieve_with_context` | 子 chunk → 父文档 |
| 卡片提炼 | `backend/app/services/llm.py` `refine_knowledge_card` | 父文档 → concept/tip |
| 意图温度 | `nodes.py` `standard_chat_node` | KNOWLEDGE 0.3 / EMOTION 0.8 |
| 失败降级 | 同文件 | 两级降级链 |
| 滑窗触发 | 同文件 `save_message_node` | 增量 ≥ 10 触发画像 |
| 合并提取 | 同文件 `update_memory_background` | 画像+摘要一次调用 |
| 合并输出 | `backend/app/services/llm.py` `extract_memory_bundle` | 一次调用双输出 |

---

## 7. 关键参数速查

| 参数 | 值 | 位置 |
|---|---|---|
| KNOWLEDGE 温度 | 0.3 | `standard_chat_node` |
| EMOTION 温度 | 0.8 | 同文件 |
| 查询重写模型参数 | temp 0.0 / max_tokens 30 | `llm.py rewrite_query` |
| 卡片提炼参数 | temp 0.3 / max_tokens 200 | `llm.py refine_knowledge_card` |
| RAG 召回条数 | top-2（Small-to-Big） | `load_context_node` |
| 画像滑窗触发 | 增量 ≥ 10 条 | `save_message_node` |
| 摘要触发 | 窗口 > 20 条 | 同文件 |
| 画像字段裁剪 | 各 ≤ 5 条 | `standard_chat_node` |
