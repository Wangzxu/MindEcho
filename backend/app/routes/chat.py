# -*- coding: utf-8 -*-
import json
import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from app.database.mysql import get_db
from app.models import User, ChatSession, ChatMessage
from app.schemas import Result, SessionCreate, SessionResponse, MessageCreate, MessageResponse
from app.services.intent import intent_service
from app.services.rag import rag_service
from app.services.llm import llm_service
from app.routes.auth import get_current_user

chat_bp = APIRouter(prefix="/api", tags=["心理会话"])
logger = logging.getLogger(__name__)

@chat_bp.post("/chat/session", response_model=Result[SessionResponse])
def create_session(
    data: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新的聊天会话"""
    title = data.title
    is_anonymous = data.is_anonymous

    try:
        # 如果是匿名会话，不需要关联 user_id (保持为 None)
        user_id = None if is_anonymous else current_user.id
        
        session = ChatSession(user_id=user_id, title=title, is_anonymous=is_anonymous)
        db.add(session)
        db.commit()
        db.refresh(session)
        return Result.success(data=SessionResponse.model_validate(session), message="会话创建成功")
    except Exception as e:
        db.rollback()
        logger.error(f"创建会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@chat_bp.get("/chat/session/{session_id}/history", response_model=Result[list[MessageResponse]])
def get_session_history(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取会话历史消息"""
    session = db.query(ChatSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 安全鉴权：非匿名会话中，非拥有者且非管理员禁止访问历史
    if not session.is_anonymous and session.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问此会话记录")

    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
    # 转换为 MessageResponse 列表
    history = [MessageResponse.model_validate(msg) for msg in messages]
    return Result.success(data=history, message="获取历史消息成功")


@chat_bp.post("/chat/message")
async def send_message(
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    发送消息接口 (流式 SSE 渲染)
    接收: MessageCreate (session_id, content)
    返回: EventSourceResponse
    """
    session_id = data.session_id
    content = data.content.strip()

    session = db.query(ChatSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 安全鉴权：非匿名会话中，非拥有者且非管理员禁止向该会话发送消息
    if not session.is_anonymous and session.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权向此会话发送消息")

    try:
        # 1. 保存用户消息至数据库
        user_msg = ChatMessage(session_id=session_id, sender='user', content=content)
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        # 2. 意图识别分类
        intent, reason = intent_service.classify_intent(content)
        user_msg.intent = intent
        db.commit()

        # 3. 处理 RAG 知识检索
        rag_cards = []
        if intent == "KNOWLEDGE":
            # 检索知识库 (此处已适配传入 db)
            rag_cards = rag_service.search_knowledge(db, content, limit=2)
            logger.info(f"RAG 检索结果: 找到 {len(rag_cards)} 张知识卡片")

        # 4. 构建 SSE 异步事件生成器
        async def event_generator():
            # 获取一个新的数据库 Session 保证在异步迭代中数据库事务隔离完整性
            # 因为 SSE 运行在异步迭代中，可能会超出外部 Depends(get_db) 事务的作用域
            from app.database.mysql import SessionLocal
            async_db = SessionLocal()
            try:
                # 首先发送意图标签与RAG卡片元数据给前端
                meta_event = {
                    "intent": intent,
                    "reason": reason,
                    "rag_cards": rag_cards
                }
                yield {"data": json.dumps(meta_event, ensure_ascii=False)}

                # A. 危机干预机制 (CRISIS) 熔断处理
                if intent == "CRISIS":
                    crisis_reply = (
                        "看到你写下这些，我非常担心你。请相信你不需要独自面对这些痛苦，我很在乎你的安全，我们一起找专业老师来帮帮我们。\n\n"
                        "❤️ **校园 24小时心理危机干预热线**: 010-XXXX-XXXX (或拨打全国援助专线 800-810-1117)\n"
                        "📍 **心理咨询中心地址**: 综合教学楼 302 室 (工作时间: 周一至周五 8:00 - 17:00)\n"
                        "请允许我们陪伴在你身边，不要放弃希望！"
                    )
                    
                    chunk_size = 5
                    for i in range(0, len(crisis_reply), chunk_size):
                        chunk = crisis_reply[i:i+chunk_size]
                        yield {"data": json.dumps({'content': chunk}, ensure_ascii=False)}
                        await asyncio.sleep(0.05)

                    # 写入 AI 危机消息回复至数据库
                    ai_msg = ChatMessage(session_id=session_id, sender='ai', content=crisis_reply, intent=intent)
                    async_db.add(ai_msg)
                    async_db.commit()

                # B. 专业知识库 & 日常倾诉流式大模型输出 (KNOWLEDGE, EMOTION, CHITCHAT)
                else:
                    # 获取长期记忆 (用户画像)
                    user_nickname = "同学"
                    core_stressors = "未明确"
                    effective_coping_methods = "未明确"
                    entity_relation_map = "无"
                    semantic_history_recall = "无"

                    # 重新从 async_db 载入 session 对应实体，防止 session 跨线程解耦
                    session_entity = async_db.query(ChatSession).get(session_id)
                    if session_entity and not session_entity.is_anonymous and session_entity.user:
                        user = session_entity.user
                        profile = user.profile
                        if profile:
                            user_nickname = profile.nickname or user.username
                            if profile.core_stressors:
                                core_stressors = ", ".join(profile.core_stressors)
                            if profile.effective_coping_methods:
                                effective_coping_methods = ", ".join(profile.effective_coping_methods)
                            if profile.entity_relation_map:
                                entity_relation_map = ", ".join([f"{k}:{v}" for k, v in profile.entity_relation_map.items()])
                            if profile.semantic_history_recall:
                                semantic_history_recall = profile.semantic_history_recall

                    # 获取短期记忆：最近 6 轮消息历史（不包含当前这条）
                    recent_messages = async_db.query(ChatMessage).filter(
                        ChatMessage.session_id == session_id,
                        ChatMessage.id < user_msg.id
                    ).order_by(ChatMessage.created_at.desc()).limit(6).all()
                    recent_messages.reverse()

                    chat_history_buffer = ""
                    for m in recent_messages:
                        role_name = "学生" if m.sender == 'user' else "AI"
                        chat_history_buffer += f"- {role_name}: {m.content}\n"

                    # 动态配置响应风格
                    style_constraints = ""
                    if intent == "KNOWLEDGE":
                        style_constraints = "当前用户正在咨询专业心理学知识。请结合【专业知识库检索内容】进行科学、温和的解答，并引导用户尝试卡片中的调节小技巧。"
                    elif intent == "EMOTION":
                        style_constraints = "当前用户正在进行倾诉。请开启情绪容器模式：专注于同理心共情、积极倾听和情绪合理化，温和引导其进行自我觉察，不要急于给出具体的科学建言。"
                    elif intent == "CHITCHAT":
                        style_constraints = "当前用户为日常闲聊或打招呼。请用温柔温和、具备亲和力的语气简短回应，保持学姐/学长的亲切人设。"

                    # 格式化 RAG 检索知识卡片
                    rag_text = ""
                    if rag_cards:
                        for card in rag_cards:
                            rag_text += f"标题: {card['title']}\n解释: {card['concept']}\n技巧: {card['tip']}\n\n"

                    # 统一上下文构建 System Prompt
                    system_prompt = (
                        "你是一个面向高校学生的 AI 心理委员，名字叫「小影」，角色定位是温柔、包容、非批判性的心理学长学姐。\n\n"
                        f"【响应风格约束】\n{style_constraints}\n\n"
                        "【长期记忆与用户画像】\n"
                        f"- 用户昵称: {user_nickname}\n"
                        f"- 核心压力源: {core_stressors}\n"
                        f"- 历史有效技巧: {effective_coping_methods}\n"
                        f"- 关键关系网: {entity_relation_map}\n"
                        f"- 历史会话召回线索: {semantic_history_recall}\n\n"
                        "【专业知识库检索内容（若有，请按需润色结合）】\n"
                        f"{rag_text or '无相关知识卡片。'}\n\n"
                        f"【会话历史记录（短期记忆）】\n{chat_history_buffer or '无往期历史。'}"
                    )

                    messages = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content}
                    ]

                    # 调用复杂 LLM 的流式输出
                    response_stream = llm_service.call_complex_model_stream(messages, temperature=0.7)
                    
                    full_reply = ""
                    for chunk in response_stream:
                        full_reply += chunk
                        yield {"data": json.dumps({'content': chunk}, ensure_ascii=False)}
                        # 给事件循环让出资源以执行并发任务
                        await asyncio.sleep(0.01)

                    # 将最终完整的 AI 回复存入数据库
                    ai_msg = ChatMessage(session_id=session_id, sender='ai', content=full_reply, intent=intent)
                    async_db.add(ai_msg)
                    async_db.commit()

                # 发送结束标记
                yield {"data": "[DONE]"}

            except Exception as ex:
                async_db.rollback()
                logger.error(f"SSE 流式生成异常: {str(ex)}")
                yield {"data": json.dumps({'error': '模型推理异常', 'message': str(ex)}, ensure_ascii=False)}
                yield {"data": "[DONE]"}
            finally:
                async_db.close()

        return EventSourceResponse(event_generator())

    except Exception as e:
        db.rollback()
        logger.error(f"处理发送消息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理消息失败: {str(e)}")
