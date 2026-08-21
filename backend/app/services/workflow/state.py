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
    
    # 记忆系统的 4 部分装载（四层记忆架构）
    recent_history: str             # 1. 最近12条原始对话拼接字符串（窗口层）
    previous_summary: str           # 2. 中期记忆：窗口之外的会话摘要（内存，不落库）
    user_profile: Dict[str, Any]    # 3. 长期记忆：用户心理画像（MySQL user_profiles）
    rag_cards: List[Dict[str, Any]] # 4. 专业RAG检索知识卡片（仅KNOWLEDGE意图）
    
    # 最终大模型回复内容
    response_content: str
    
    # 流式记忆与轮数追踪 (新增字段)
    history_messages: List[Dict[str, str]] # [{'sender': 'user'|'ai', 'content': str}]
