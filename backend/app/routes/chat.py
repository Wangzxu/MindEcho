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
from app.services.workflow import workflow_agent
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
        # 即使是匿名会话，我们也关联当前用户以便在侧边栏加载列表，但因为 is_anonymous 为 True，消息本身不记录
        user_id = current_user.id
        
        session = ChatSession(user_id=user_id, title=title, is_anonymous=is_anonymous)
        db.add(session)
        db.commit()
        db.refresh(session)
        return Result.success(data=SessionResponse.model_validate(session), message="会话创建成功")
    except Exception as e:
        db.rollback()
        logger.error(f"创建会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@chat_bp.get("/chat/sessions", response_model=Result[list[SessionResponse]])
def get_user_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前登录用户的所有会话列表"""
    try:
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == current_user.id
        ).order_by(ChatSession.created_at.desc()).all()
        data = [SessionResponse.model_validate(s) for s in sessions]
        return Result.success(data=data, message="获取会话列表成功")
    except Exception as e:
        logger.error(f"获取会话列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


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
        # 1. 保存用户消息至数据库 (如果是非匿名/非无痕会话)
        user_msg_id = None
        if not session.is_anonymous:
            user_msg = ChatMessage(session_id=session_id, sender='user', content=content)
            db.add(user_msg)
            db.commit()
            db.refresh(user_msg)
            user_msg_id = user_msg.id

        # 2. 准备 LangGraph 初始状态
        initial_state = {
            "session_id": session_id,
            "user_input": content,
            "is_anonymous": session.is_anonymous,
            "current_user_id": current_user.id,
            "user_msg_id": user_msg_id,
            "intent": "",
            "intent_reason": "",
            "recent_history": "",
            "previous_summary": "",
            "user_profile": {},
            "rag_cards": [],
            "response_content": ""
        }

        # 3. 创建异步队列用于 SSE 消息流转
        queue = asyncio.Queue()
        config = {
            "configurable": {
                "queue": queue,
                "thread_id": session_id
            }
        }

        async def run_workflow():
            try:
                await workflow_agent.ainvoke(initial_state, config=config)
            except Exception as e:
                logger.error(f"LangGraph 工作流执行出错: {str(e)}")
                await queue.put({"type": "error", "message": str(e)})
            finally:
                # 放入哨兵对象标记结束
                await queue.put(None)

        # 后台执行工作流
        task = asyncio.create_task(run_workflow())

        # 4. 构建 SSE 异步事件生成器
        async def event_generator():
            try:
                while True:
                    event = await queue.get()
                    if event is None:
                        break

                    if event["type"] == "metadata":
                        yield {"data": json.dumps(event["data"], ensure_ascii=False)}
                    elif event["type"] == "content":
                        yield {"data": json.dumps({"content": event["content"]}, ensure_ascii=False)}
                    elif event["type"] == "error":
                        yield {"data": json.dumps({"error": "模型推理异常", "message": event["message"]}, ensure_ascii=False)}

                    queue.task_done()

                # 发送结束标记
                yield {"data": "[DONE]"}
            except Exception as ex:
                logger.error(f"SSE 消息流读取异常: {str(ex)}")
                yield {"data": json.dumps({"error": "事件流异常", "message": str(ex)}, ensure_ascii=False)}
                yield {"data": "[DONE]"}

        return EventSourceResponse(event_generator())

    except Exception as e:
        db.rollback()
        logger.error(f"处理发送消息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理消息失败: {str(e)}")
