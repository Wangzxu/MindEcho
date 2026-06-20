# -*- coding: utf-8 -*-
import json
import logging
import asyncio
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig

from app.services.llm import llm_service
from app.services.rag import rag_service
from app.database.vector import vector_db
from app.database.mysql import SessionLocal
from app.models import ChatSession, ChatMessage, SecurityActivityLog, SafetyKeyword, UserProfile
from app.services.workflow.state import ChatWorkflowState

logger = logging.getLogger(__name__)

# Removed safe_parse_json in favor of LangChain native structured output (.with_structured_output).

# 内存版匿名会话摘要缓存，结构: { [session_id]: summary_str }
anonymous_summaries_map = {}

async def filter_and_route_node(state: ChatWorkflowState, config: RunnableConfig) -> Dict[str, Any]:
    """
    网关级节点：完成安全词硬过滤 (Level 1) + 预警向量匹配 (Level 2) + 模型意图分类 (Level 3)
    附加：
    1. 判断用户消息是否具备心理学特征值 (Meaningfulness Judge) 并做向量嵌入召回。
    2. 更新用户消息的 intent 进 MySQL (非无痕会话)。
    """
    user_input = state["user_input"].strip()
    queue = config.get("configurable", {}).get("queue")
    user_msg_id = state.get("user_msg_id")
    current_user_id = state.get("current_user_id")
    session_id = state.get("session_id")
    is_anonymous = state.get("is_anonymous", False)
    
    intent = None
    reason = ""
    log_type = None
    matched_rule = ""
    
    db = SessionLocal()
    try:
        # Level 1: 本地敏感词硬匹配
        keywords = db.query(SafetyKeyword).filter(SafetyKeyword.is_enabled == True).all()
        for kw in keywords:
            if kw.word in user_input:
                logger.info(f"触发网关敏感词匹配: {kw.word}")
                intent = "CRISIS"
                reason = f"敏感词匹配过滤: {kw.word}"
                log_type = kw.word_type
                matched_rule = f"命中敏感词: {kw.word}"
                break
                
        # Level 2: 预警语义向量检索 (ChromaDB 检索)
        if not intent:
            try:
                query_vector = llm_service.get_embedding(user_input)
                collection = vector_db.get_collection("safety_warnings_kb")
                results = collection.query(
                    query_embeddings=[query_vector],
                    n_results=1
                )
                if results and results.get("distances") and len(results["distances"][0]) > 0:
                    distance = results["distances"][0][0]
                    similarity = 1.0 - distance
                    if similarity > 0.85:  # 余弦相似度大于 0.85
                        matched_text = results["documents"][0][0]
                        logger.info(f"触发预警向量库语义相似匹配: {matched_text}, 相似度: {similarity:.2f}")
                        intent = "CRISIS"
                        reason = f"语义相似度匹配危机样本: {matched_text} ({similarity*100:.1f}%)"
                        
                        matched_type = "high_risk"
                        if results.get("metadatas") and len(results["metadatas"][0]) > 0:
                            matched_type = results["metadatas"][0][0].get("type", "high_risk")
                        
                        log_type = matched_type
                        matched_rule = f"预警语义匹配: {matched_text} (相似度: {similarity:.2f})"
            except Exception as ve:
                logger.error(f"预警向量库语义检索异常: {ve}")

        # Level 3: 轻量大模型二分类 (KNOWLEDGE / EMOTION)
        if not intent:
            classifier_messages = [
                {"role": "system", "content": (
                    "你是一个校园心理咨询系统的路由网关。请分析用户的当前输入，并将其精确分类为以下两类之一：\n"
                    "- \"KNOWLEDGE\": 用户在提问具体的心理学概念、自助方法（例如CBT、蝴蝶抱抱法）或查询学校心理咨询中心的信息。\n"
                    "- \"EMOTION\": 用户在进行倾诉、分享生活困扰（如考试挂科、科研不顺、室友关系差、失恋等），或进行日常打招呼、闲聊等互动。\n\n"
                    "【约束条件】\n"
                    "必须仅返回符合以下 Schema 的有效 JSON 串。不要包裹任何 Markdown 标记 (如 ```json) 且不要包含任何解释性文字：\n"
                    '{"intent": "KNOWLEDGE" | "EMOTION", "reason": "分类理由"}'
                )},
                {"role": "user", "content": user_input}
            ]

            try:
                res_json = llm_service.classify_intent(classifier_messages)
                intent = res_json.get("intent", "EMOTION")
                reason = res_json.get("reason", "模型意图分类")
            except Exception as le:
                logger.error(f"大模型结构化意图分类调用失败: {le}")
                intent = "EMOTION"
                reason = "分类接口异常降级"

        # 自动生成会话标题 (若是默认的初始化标题，根据首条消息提炼并更新)
        new_title = None
        session = None
        try:
            session = db.query(ChatSession).get(session_id)
            if session and session.title in ["新对话", "无痕新对话"]:
                title_prompt = [
                    {"role": "system", "content": "你是一个会话标题生成器。请根据用户的输入，生成一个简短、概括性的会话标题（不超过 8 个字），不要包含任何标点符号、两边引号或任何解释性文字。"},
                    {"role": "user", "content": user_input}
                ]
                generated_title = llm_service.call_simple_model(title_prompt, temperature=0.3, max_tokens=20)
                generated_title = generated_title.strip().replace('"', '').replace("'", "").replace("“", "").replace("”", "")
                if generated_title:
                    session.title = generated_title
                    db.commit()
                    new_title = generated_title
                    logger.info(f"会话标题自动概括更新成功: {generated_title}")
        except Exception as te:
            logger.error(f"自动生成会话标题异常: {te}")

        # A. 更新用户消息的 intent 进 MySQL (如果是非无痕会话且 user_msg_id 存在)
        if not is_anonymous and user_msg_id:
            try:
                user_msg = db.query(ChatMessage).get(user_msg_id)
                if user_msg:
                    user_msg.intent = intent
                    db.commit()
            except Exception as dbe:
                db.rollback()
                logger.error(f"更新用户消息intent异常: {dbe}")

        # B. 记录安全事件日志 (触发 CRISIS 时)
        if intent == "CRISIS":
            try:
                log_entry = SecurityActivityLog(
                    user_id=current_user_id,
                    session_id=session_id,
                    trigger_content=user_input,
                    log_type=log_type or "high_risk",
                    matched_rule=matched_rule or "危机规则拦截"
                )
                db.add(log_entry)
                db.commit()
                logger.info(f"安全事件日志记录成功: {matched_rule}")
            except Exception as dbe:
                db.rollback()
                logger.error(f"写入安全事件日志异常: {dbe}")

        # C. 过滤无意义日常闲聊与语气词，判断是否需要嵌入该条聊天记录为语义召回
        # 仅针对登录用户 (current_user_id 存在)
        if intent != "CRISIS" and current_user_id:
            try:
                judge_messages = [
                    {"role": "system", "content": (
                        "你是一个心理咨询系统的特征分析网关。请分析以下用户的输入，判断其是否包含具体的心理感受、生活烦恼、人际困扰或具有心理学分析价值的信息。\n"
                        "如果是，请返回 JSON: {\"is_meaningful\": true}；\n"
                        "如果只是无意义的日常问候、单字回复、道谢或告别（例如：‘你好’、‘谢谢’、‘哦’、‘好吧’、‘拜拜’），请返回 JSON: {\"is_meaningful\": false}。\n"
                        "必须仅返回有效 JSON，不要包裹任何 Markdown 标记或文字。"
                    )},
                    {"role": "user", "content": user_input}
                ]
                is_meaningful = llm_service.judge_meaningful(judge_messages)
                
                if is_meaningful:
                    logger.info(f"经评估该用户输入具备心理特征分析价值，写入 ChromaDB 用户专属语义记忆库")
                    embedding_vector = llm_service.get_embedding(user_input)
                    collection = vector_db.get_collection("user_history_recall_kb")
                    
                    import uuid
                    collection.add(
                        embeddings=[embedding_vector],
                        documents=[user_input],
                        ids=[str(uuid.uuid4())],
                        metadatas=[{"user_id": current_user_id, "session_id": session_id}]
                    )
            except Exception as e:
                logger.error(f"评估并嵌入用户聊天记录异常: {e}")

        # D. 将元数据事件推入队列 (CRISIS 分支直接在此处推入)
        if intent == "CRISIS" and queue:
            await queue.put({
                "type": "metadata", 
                "data": {
                    "intent": intent, 
                    "reason": reason, 
                    "rag_cards": [],
                    "new_title": new_title or (session.title if session else None)
                }
            })

        # 初始化/同步当前会话消息列表
        history = list(state.get("history_messages", []))
        history.append({"sender": "user", "content": user_input})

        return {
            "intent": intent, 
            "intent_reason": reason,
            "history_messages": history
        }
    finally:
        db.close()


async def load_context_node(state: ChatWorkflowState, config: RunnableConfig) -> Dict[str, Any]:
    """
    上下文装载节点：统一装载 5 部分记忆
    """
    session_id = state["session_id"]
    current_user_id = state["current_user_id"]
    intent = state["intent"]
    user_input = state["user_input"]
    queue = config.get("configurable", {}).get("queue")

    db = SessionLocal()
    try:
        # 1. 组装短期六轮历史 (最近12条消息)
        history = list(state.get("history_messages", []))
        # 如果是重新加载(比如服务重启内存丢失)，且非无痕，则从 MySQL 加载
        if len(history) <= 1 and not state.get("is_anonymous", False):
            try:
                db_msgs = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session_id
                ).order_by(ChatMessage.created_at.desc()).limit(12).all()
                db_msgs.reverse()
                history = [{"sender": db_msg.sender, "content": db_msg.content} for db_msg in db_msgs]
            except Exception as e:
                logger.error(f"服务重启后加载 MySQL 历史失败: {e}")

        # 构建 recent_history 字符串
        recent_history = ""
        # 仅取倒数第二轮及之前的(排除掉刚被 filter_and_route 插入的当前轮 user_input)
        recent_to_show = history[:-1] if len(history) > 1 else []
        for m in recent_to_show[-12:]: # 限制最后12条
            role_name = "学生" if m["sender"] == 'user' else "AI"
            recent_history += f"- {role_name}: {m['content']}\n"

        # 2. 其余轮次的历史摘要 (无痕从内存读，常规从 mysql 读)
        if state.get("is_anonymous", False):
            previous_summary = anonymous_summaries_map.get(session_id, "无往期历史。")
        else:
            session = db.query(ChatSession).get(session_id)
            previous_summary = session.summary if session and session.summary else "无往期历史。"

        # 3. 历史人物画像 & 4. 历史会话召回线索 (利用 ChromaDB 检索 user_history_recall_kb 召回)
        user_profile = {}
        semantic_history_recall = "无"
        if current_user_id:
            profile = db.query(UserProfile).filter(UserProfile.user_id == current_user_id).first()
            if profile:
                user_profile = profile.to_dict()
                
            # 语义召回线索 (ChromaDB)
            try:
                query_vector = llm_service.get_embedding(user_input)
                collection = vector_db.get_collection("user_history_recall_kb")
                results = collection.query(
                    query_embeddings=[query_vector],
                    n_results=3,
                    where={"user_id": current_user_id}
                )
                if results and results.get("documents") and len(results["documents"][0]) > 0:
                    semantic_history_recall = " | ".join(results["documents"][0])
            except Exception as re:
                logger.error(f"历史语义检索召回失败: {re}")

        # 5. 专业 RAG 科普知识库检索
        rag_cards = []
        if intent == "KNOWLEDGE":
            rag_cards = rag_service.search_knowledge(db, user_input, limit=2)
            logger.info(f"RAG 科普知识检索召回，条数: {len(rag_cards)}")

        # 核心元数据（意图标签 + 知识卡片）打包装入 SSE 队列通知前端
        if queue:
            meta_event = {
                "intent": intent,
                "reason": state.get("intent_reason", "意图识别完成"),
                "rag_cards": rag_cards,
                "new_title": session.title if session else None
            }
            await queue.put({"type": "metadata", "data": meta_event})

        return {
            "recent_history": recent_history,
            "previous_summary": previous_summary,
            "user_profile": user_profile,
            "semantic_history_recall": semantic_history_recall,
            "rag_cards": rag_cards,
            "history_messages": history
        }
    finally:
        db.close()


async def crisis_handler_node(state: ChatWorkflowState, config: RunnableConfig) -> Dict[str, Any]:
    """
    危机干预处理节点
    """
    queue = config.get("configurable", {}).get("queue")
    crisis_reply = (
        "看到你写下这些，我非常担心你。请相信你不需要独自面对这些痛苦，我很在乎你的安全，我们一起找专业老师来帮帮我们。\n\n"
        "❤️ **校园 24小时心理危机干预热线**: 010-XXXX-XXXX (或拨打全国援助专线 800-810-1117)\n"
        "📍 **心理咨询中心地址**: 综合教学楼 302 室 (工作时间: 周一至周五 8:00 - 17:00)\n"
        "请允许我们陪伴在你身边，不要放弃希望！"
    )

    if queue:
        chunk_size = 5
        for i in range(0, len(crisis_reply), chunk_size):
            chunk = crisis_reply[i:i+chunk_size]
            await queue.put({"type": "content", "content": chunk})
            await asyncio.sleep(0.04)

    # 同步 AI 消息入 history_messages 缓存
    history = list(state.get("history_messages", []))
    history.append({"sender": "ai", "content": crisis_reply})

    return {
        "response_content": crisis_reply,
        "history_messages": history
    }


async def standard_chat_node(state: ChatWorkflowState, config: RunnableConfig) -> Dict[str, Any]:
    """
    常规对话生成节点：动态调整感理性比例，并流式输出 LLM 回复
    """
    intent = state["intent"]
    user_input = state["user_input"]
    queue = config.get("configurable", {}).get("queue")

    # 动态配比
    if intent == "KNOWLEDGE":
        style_constraints = (
            "当前用户正在进行科普问答。请使用【理智客观、条理清晰的直接回答（占比60%）】，结合适当的温和共情（占比40%）。"
            "必须结合下方提供的【专业知识库检索内容】进行科学解答，条理化整理并推荐可操练的自助小常识与小贴士，"
            "避免生硬诊断，用通俗易懂的口语表达。"
        )
    else:
        style_constraints = (
            "当前用户处于情绪宣泄或闲聊状态。请开启【高共情情绪容器模式（占比90%）】，理性的行动指导仅占10%。"
            "专注于同理心共鸣（‘我听到了...’、‘这真的很不容易...’）、情绪合理化与包容。不要给出枯燥的说教或硬性的科学条例，"
            "请以温和的口吻对用户进行适度提问和开放式引导，帮助其觉察内心状态。"
        )

    nickname = state["user_profile"].get("nickname", "同学")
    core_stressors = ", ".join(state["user_profile"].get("core_stressors", [])) or "未明确"
    effective_coping_methods = ", ".join(state["user_profile"].get("effective_coping_methods", [])) or "未明确"
    entity_relation_map = ", ".join([f"{k}:{v}" for k, v in state["user_profile"].get("entity_relation_map", {}).items()]) or "无"
    semantic_history_recall = state["semantic_history_recall"]
    previous_summary = state["previous_summary"]
    recent_history = state["recent_history"]

    rag_text = ""
    if state["rag_cards"]:
        for card in state["rag_cards"]:
            rag_text += f"- (来自 {card.get('file_name', '未知文件')}):\n{card['content']}\n\n"

    system_prompt = (
        "你是一个面向高校学生的 AI 心理委员，名字叫「小影」，角色定位是温柔、包容、非批判性的心理学长学姐。\n\n"
        f"【回复风格约束】\n{style_constraints}\n\n"
        "【长期记忆与用户画像】\n"
        f"- 用户昵称: {nickname}\n"
        f"- 核心压力源: {core_stressors}\n"
        f"- 历史有效技巧: {effective_coping_methods}\n"
        f"- 关键关系网: {entity_relation_map}\n"
        f"- 历史会话召回线索: {semantic_history_recall}\n\n"
        "【专业知识库检索内容（若有，请按需润色结合）】\n"
        f"{rag_text or '无相关知识卡片。'}\n\n"
        f"【会话历史记录（短期记忆）】\n"
        f"- 6轮以前的历史摘要: {previous_summary}\n"
        f"- 最近的对话历史:\n{recent_history or '无往期历史。'}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]

    full_reply = ""
    try:
        response_stream = llm_service.call_complex_model_stream(messages, temperature=0.7)
        for chunk in response_stream:
            full_reply += chunk
            if queue:
                await queue.put({"type": "content", "content": chunk})
            await asyncio.sleep(0.01)
    except Exception as e:
        logger.error(f"大模型流式输出发生异常: {e}")
        if queue:
            await queue.put({"type": "error", "message": f"流式输出异常: {str(e)}"})
        raise e

    # 同步 AI 消息入 history_messages 缓存
    history = list(state.get("history_messages", []))
    history.append({"sender": "ai", "content": full_reply})

    return {
        "response_content": full_reply,
        "history_messages": history
    }


async def update_profile_background(current_user_id: int, history_segment: List[Dict[str, str]]):
    """后台进行个人特征画像建模更新"""
    db = SessionLocal()
    try:
        logger.info(f"后台任务启动：开始为用户 {current_user_id} 进行个人特征建模画像更新...")
        profile = db.query(UserProfile).filter(UserProfile.user_id == current_user_id).first()
        if not profile:
            profile = UserProfile(user_id=current_user_id)
            db.add(profile)
            db.commit()
            db.refresh(profile)
        
        # 拼接最近这 20 条消息的对话内容
        recent_chat_text = ""
        for m in history_segment:
            role = "学生" if m["sender"] == 'user' else "AI"
            recent_chat_text += f"{role}: {m['content']}\n"
        
        current_profile_dict = {
            "nickname": profile.nickname,
            "core_stressors": profile.core_stressors or [],
            "effective_coping_methods": profile.effective_coping_methods or [],
            "entity_relation_map": profile.entity_relation_map or {}
        }
        
        profile_messages = [
            {"role": "system", "content": (
                "你是一个心理特征画像提取专家。请基于用户目前的心理画像和最近的对话记录，提取并更新用户的心理特征。\n"
                "请输出符合以下 JSON Schema 的结果，不要包裹 markdown 或其他文字：\n"
                "{\n"
                "  \"nickname\": \"用户昵称\",\n"
                "  \"core_stressors\": [\"压力源1\", \"压力源2\"],\n"
                "  \"effective_coping_methods\": [\"有效应对方法1\", \"有效应对方法2\"],\n"
                "  \"entity_relation_map\": {\"人名/角色\": \"关系描述\"}\n"
                "}\n"
                "【注意】不要遗失之前已有的重要画像内容，仅做合并与更新。不需要包含任何解释性文本或 Markdown 代码块。"
            )},
            {"role": "user", "content": f"【当前画像】:\n{json.dumps(current_profile_dict, ensure_ascii=False)}\n\n【最近对话】:\n{recent_chat_text}"}
        ]
        
        # 运行同步阻塞方法在大模型服务的线程池中，避免阻塞主事件循环
        profile_json = await asyncio.to_thread(llm_service.extract_profile, profile_messages)
        if profile_json:
            if "nickname" in profile_json and profile_json["nickname"]:
                profile.nickname = profile_json["nickname"]
            if "core_stressors" in profile_json:
                profile.core_stressors = profile_json["core_stressors"]
            if "effective_coping_methods" in profile_json:
                profile.effective_coping_methods = profile_json["effective_coping_methods"]
            if "entity_relation_map" in profile_json:
                profile.entity_relation_map = profile_json["entity_relation_map"]
            
            db.commit()
            logger.info(f"后台任务完成：个人心理画像更新建模成功！昵称: {profile.nickname}")
    except Exception as pe:
        db.rollback()
        logger.error(f"后台大模型结构化画像提取失败: {pe}")
    finally:
        db.close()


async def compress_summary_background(session_id: str, to_compress_segment: List[Dict[str, str]], is_anonymous: bool = False):
    """后台进行滚动上下文摘要生成与压缩"""
    db = SessionLocal()
    try:
        logger.info(f"后台任务启动：开始对会话 {session_id} 进行滚动会话摘要压缩...")
        # 拼接要压缩的对话内容
        compress_text = ""
        for m in to_compress_segment:
            role = "学生" if m["sender"] == 'user' else "AI"
            compress_text += f"{role}: {m['content']}\n"
        
        # 针对无痕和常规获取上一次的摘要以作大模型参考
        if is_anonymous:
            old_summary = anonymous_summaries_map.get(session_id, "无往期历史摘要。")
        else:
            session = db.query(ChatSession).get(session_id)
            if not session:
                logger.warning(f"后台会话摘要压缩失败，会话 {session_id} 不存在")
                return
            old_summary = session.summary if session.summary else "无往期历史摘要。"
        
        summary_messages = [
            {"role": "system", "content": (
                "你是一个会话摘要总结专家。请结合已有的旧摘要和最近新发生的对话段落，将这些较老的对话细节以精简的客观心理学总结合并记录。\n"
                "仅关注用户的压力源、情感转折以及心理变化，并保持总结简明扼要（300字以内）。不要输出任何额外的废话。"
            )},
            {"role": "user", "content": f"【往期历史摘要】:\n{old_summary}\n\n【最新已沉淀对话】:\n{compress_text}"}
        ]
        
        # 运行同步阻塞方法在大模型服务的线程池中，避免阻塞主事件循环
        new_summary = await asyncio.to_thread(llm_service.call_summary_model, summary_messages, temperature=0.3)
        
        if new_summary:
            if is_anonymous:
                # 匿名/无痕树洞会话，仅同步至内存 map 缓存，不同步至 MySQL
                anonymous_summaries_map[session_id] = new_summary
                logger.info(f"后台任务完成：无痕会话 {session_id} 滚动摘要压缩成功并已存入内存缓存")
            else:
                # 常规会话，同步至 MySQL
                session = db.query(ChatSession).get(session_id)
                if session:
                    session.summary = new_summary
                    db.commit()
                    logger.info(f"后台任务完成：常规会话 {session_id} 滚动摘要压缩成功并已同步至 MySQL")
    except Exception as se:
        db.rollback()
        logger.error(f"后台滚动上下文摘要压缩异常: {se}")
    finally:
        db.close()


async def save_message_node(state: ChatWorkflowState, config: RunnableConfig) -> Dict[str, Any]:
    """
    持久化消息节点：
    1. 保存 AI 回复进 MySQL (非无痕会话)。
    2. 每 10 轮 (20条消息) 后台异步进行一次用户画像更新建模。
    3. 超出 6 轮 (12条消息) 后台异步进行滚动上下文摘要生成与压缩。
    """
    session_id = state["session_id"]
    response_content = state["response_content"]
    intent = state["intent"]
    is_anonymous = state.get("is_anonymous", False)
    current_user_id = state.get("current_user_id")
    history = list(state.get("history_messages", []))

    db = SessionLocal()
    keep_window = None
    try:
        # A. 保存 AI 回复进 MySQL (非无痕会话)
        if not is_anonymous:
            try:
                ai_msg = ChatMessage(
                    session_id=session_id,
                    sender='ai',
                    content=response_content,
                    intent=intent
                )
                db.add(ai_msg)
                db.commit()
                logger.info(f"AI 回复已持久化至 MySQL")
            except Exception as e:
                db.rollback()
                logger.error(f"持久化 AI 回复异常: {e}")

        # B. 轮数检查：每10轮 (20条消息) 进行一次个人特征画像建模（后台异步）
        if current_user_id and len(history) >= 20 and len(history) % 20 == 0:
            logger.info(f"当前会话已达 {len(history)} 条消息，触发后台异步个人特征画像建模...")
            history_segment = list(history[-20:])
            asyncio.create_task(update_profile_background(current_user_id, history_segment))

        # C. 上下文压缩：当缓存中消息轮次超出 6 轮 (12 条消息)，触发滚动 Summary 压缩（后台异步）
        if len(history) > 12:
            to_compress = list(history[:-12])
            keep_window = list(history[-12:])
            logger.info(f"活跃会话已达 {len(history)} 条消息，裁剪状态窗口并触发后台滚动会话摘要压缩...")
            asyncio.create_task(compress_summary_background(session_id, to_compress, is_anonymous))

    finally:
        db.close()

    if keep_window is not None:
        return {"history_messages": keep_window}
    return {}
