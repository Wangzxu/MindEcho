# -*- coding: utf-8 -*-
from typing import TypedDict, List, Dict, Any

class ChatWorkflowState(TypedDict):
    # 基本会话环境标识
    session_id: str
    user_input: str
    is_anonymous: bool
    current_user_id: int | None
    user_msg_id: int | None
    
    # 意图检测结果
    intent: str  # CRISIS, KNOWLEDGE, EMOTION
    intent_reason: str
    
    # 唯一缓存的用户输入向量 (避免多节点重复计算)
    user_input_embedding: List[float] | None
    
    # 累计消息轮数计数器 (用于无痕会话等画像建模判定)
    message_count: int | None
    
    # 记忆系统的 5 部分装载
    recent_history: str             # 1. 6轮原始对话历史拼接字符串
    previous_summary: str           # 2. 其余轮次的历史摘要
    user_profile: Dict[str, Any]    # 3. 历史人物心理画像
    semantic_history_recall: str   # 4. 历史会话召回线索
    rag_cards: List[Dict[str, Any]] # 5. 向量库RAG检索知识卡片
    
    # 最终大模型回复内容
    response_content: str
    
    # 流式记忆与轮数追踪 (新增字段)
    history_messages: List[Dict[str, str]] # [{'sender': 'user'|'ai', 'content': str}]
