# -*- coding: utf-8 -*-
import json
import logging
import asyncio
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig

from app.services.llm import llm_service
from app.services.rag import retrieve_with_context
from app.database.vector import vector_db
from app.database.mysql import SessionLocal
from app.models import ChatMessage, SecurityActivityLog, SafetyKeyword, UserProfile
from app.services.workflow.state import ChatWorkflowState

logger = logging.getLogger(__name__)

# Removed safe_parse_json in favor of LangChain native structured output (.with_structured_output).

# 中期记忆（会话摘要）内存缓存：不落库，服务重启即清空
# 作用：存储 12 轮（窗口）之外的对话摘要，应对高强度连续聊天时的上下文丢失
# 结构: { [session_id]: summary_str }（无痕与常规会话共用）
midterm_summaries_map = {}

async def filter_and_route_node(state: ChatWorkflowState, config: RunnableConfig) -> Dict[str, Any]:
    """
    网关级节点：完成安全词硬过滤 (Level 1) + 大模型三分类意图识别 (Level 2) + 预警向量匹配 (Level 3)
    附加：
    1. 判断用户消息是否具备心理学特征值 (Meaningfulness Judge) 并提取高维结构化记忆。
    2. 对非 CRISIS 的输入进行单次向量嵌入缓存，供后续安全兜底、RAG 与历史召回共享。
    3. 在写入前进行两阶段查重检测（直接距离拦截 + 灰色区间语义查重复核）。
    4. 更新用户消息的 intent 进 MySQL (非无痕会话)。
    """
    logger.info("=== [filter_and_route_node] 开始执行 ===")
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
    user_input_embedding = None
    
    db = SessionLocal()
    try:
        # Level 1: 本地敏感词硬匹配 (不耗费 API)
        logger.info("[filter_and_route_node] 正在执行 Level 1 硬过滤拦截...")
        keywords = db.query(SafetyKeyword).filter(SafetyKeyword.is_enabled == True).all()
        for kw in keywords:
            if kw.word in user_input:
                logger.info(f"触发网关敏感词匹配: {kw.word}")
                intent = "CRISIS"
                reason = f"敏感词匹配过滤: {kw.word}"
                log_type = kw.word_type
                matched_rule = f"命中敏感词: {kw.word}"
                break
                
        # Level 2 + Level 3 并行执行（两者只依赖 user_input，互不依赖）：
        #   Level 2: 轻量大模型三分类意图识别 (KNOWLEDGE / EMOTION / CRISIS)
        #   Level 3: 预警语义向量检索兜底（ChromaDB），与分类并行省一个 RTT
        if not intent:
            logger.info("[filter_and_route_node] 正在并行执行 Level 2 意图三分类 + Level 3 预警向量检索...")

            async def _classify():
                classifier_messages = [
                    {"role": "system", "content": (
                        "你是一个校园心理咨询系统的路由网关。请分析用户的当前输入，并将其精确分类为以下三类之一：\n"
                        "- \"KNOWLEDGE\": 用户在提问具体的心理学概念、自助方法（例如CBT、蝴蝶抱抱法）或查询学校心理咨询中心的信息。\n"
                        "- \"EMOTION\": 用户在进行倾诉、分享生活困扰（如考试挂科、科研不顺、室友关系差、失恋等），或进行日常打招呼、闲聊等互动。\n"
                        "- \"CRISIS\": 用户表达了自残、自杀倾向，或者有严重的暴力倾向、绝望自毁心理。"
                    )},
                    {"role": "user", "content": user_input}
                ]
                try:
                    logger.info("[filter_and_route_node] 准备调用 llm_service.classify_intent...")
                    res_json = await asyncio.to_thread(llm_service.classify_intent, classifier_messages)
                    intent_res = res_json.get("intent", "EMOTION")
                    reason_res = res_json.get("reason", "模型意图分类")
                    logger.info(f"[filter_and_route_node] classify_intent 调用成功: intent={intent_res}, reason={reason_res}")
                    return intent_res, reason_res
                except Exception as le:
                    logger.error(f"大模型结构化意图分类调用失败: {le}")
                    return "EMOTION", "分类接口异常降级"

            async def _safety_vec_check():
                try:
                    logger.info("[filter_and_route_node] 准备调用 llm_service.get_embedding 获取输入向量...")
                    embedding = await asyncio.to_thread(llm_service.get_embedding, user_input)
                    logger.info("[filter_and_route_node] get_embedding 成功")
                    collection = vector_db.get_collection("safety_warnings_kb")
                    results = await asyncio.to_thread(
                        collection.query,
                        query_embeddings=[embedding],
                        n_results=1
                    )
                    return embedding, results
                except Exception as ve:
                    logger.error(f"预警向量库语义检索异常: {ve}")
                    return None, None

            (intent, reason), (user_input_embedding, safety_results) = await asyncio.gather(
                _classify(), _safety_vec_check()
            )

            # Level 3 结果处理：相似度 > 0.85 升级为 CRISIS（仅当 Level 2 未判危机）
            if intent != "CRISIS" and safety_results:
                try:
                    if safety_results.get("distances") and len(safety_results["distances"][0]) > 0:
                        distance = safety_results["distances"][0][0]
                        similarity = 1.0 - distance
                        if similarity > 0.85:  # 余弦相似度大于 0.85
                            matched_text = safety_results["documents"][0][0]
                            logger.info(f"触发预警向量库语义相似匹配兜底: {matched_text}, 相似度: {similarity:.2f}")
                            intent = "CRISIS"
                            reason = f"语义相似度匹配危机样本兜底: {matched_text} ({similarity*100:.1f}%)"

                            matched_type = "high_risk"
                            if safety_results.get("metadatas") and len(safety_results["metadatas"][0]) > 0:
                                matched_type = safety_results["metadatas"][0][0].get("type", "high_risk")

                            log_type = matched_type
                            matched_rule = f"预警语义匹配兜底: {matched_text} (相似度: {similarity:.2f})"
                except Exception as ve:
                    logger.error(f"预警向量结果解析异常: {ve}")

        # 会话标题为固定名称（直接聊天/无痕树洞），注册时创建，不再自动生成

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

        # C. 将元数据事件推入队列 (CRISIS 分支直接在此处推入)
        if intent == "CRISIS" and queue:
            logger.info("[filter_and_route_node] 触发危机分支，将危机元数据放入队列...")
            await queue.put({
                "type": "metadata", 
                "data": {
                    "intent": intent, 
                    "reason": reason, 
                    "rag_cards": []
                }
            })

        # 初始化/同步当前会话消息列表
        history = list(state.get("history_messages", []))
        history.append({"sender": "user", "content": user_input})

        return {
            "intent": intent, 
            "intent_reason": reason,
            "history_messages": history,
            "user_input_embedding": user_input_embedding
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

        # 2. 中期记忆：12 轮之外的对话摘要（内存存储，不落库；服务重启后仅剩窗口+画像）
        previous_summary = midterm_summaries_map.get(session_id, "无往期历史。")

        # 3. 长期画像（唯一长期记忆源，MySQL user_profiles）
        user_profile = {}
        if current_user_id:
            profile = db.query(UserProfile).filter(UserProfile.user_id == current_user_id).first()
            if profile:
                user_profile = profile.to_dict()

        # 4. 专业 RAG 科普知识库检索（仅 KNOWLEDGE 意图）：查询重写 → 向量化 → Small-to-Big 召回
        rag_cards = []
        rewritten_query = ""
        if intent == "KNOWLEDGE":
            # 4.1 查询重写：口语化长文本 → 纯粹心理检索词，降低向量检索噪声
            rewritten_query = llm_service.rewrite_query(user_input)
            # 4.2 用改写后的检索词向量化（不复用安全路由阶段的原始输入向量，因文本已变化）
            query_vector = llm_service.get_embedding(rewritten_query)
            # 4.3 Small-to-Big 检索：命中子 chunk 后展开为完整父文档小节，返回来源章节
            retrieved = retrieve_with_context(
                query=rewritten_query,
                top_k=2,
                query_vector=query_vector
            )
            # 4.4 适配前端卡片结构：title 用章节路径 h1>h2>h3，兜底文件名
            rag_cards = []
            for pr in retrieved:
                title_parts = [p for p in [pr.get("h1", ""), pr.get("h2", ""), pr.get("h3", "")] if p]
                title = " > ".join(title_parts) if title_parts else pr.get("file_name", "科普知识卡")
                rag_cards.append({
                    "title": title,
                    "content": pr.get("content", ""),
                    "file_name": pr.get("file_name", "未知"),
                    "h1": pr.get("h1", ""),
                    "h2": pr.get("h2", ""),
                    "h3": pr.get("h3", ""),
                    "score": pr.get("score", 0),
                    "source_chunks": pr.get("source_chunks", []),
                    "concept": "",
                    "tip": "",
                })
            # 4.5 卡片提炼：父文档全文 → 结构化 concept/tip（并行处理，失败回退原文）
            try:
                refined = await asyncio.gather(*[
                    asyncio.to_thread(llm_service.refine_knowledge_card, rewritten_query, card["content"])
                    for card in rag_cards
                ])
                for card, rf in zip(rag_cards, refined):
                    card["concept"] = rf.get("concept", card["content"][:200])
                    card["tip"] = rf.get("tip", "")
            except Exception as re:
                logger.warning(f"RAG 卡片提炼失败，回退原文展示: {re}")
            logger.info(f"RAG 科普知识检索召回，条数: {len(rag_cards)}（改写后查询: {rewritten_query}）")

        # 核心元数据（意图标签 + 知识卡片）打包装入 SSE 队列通知前端
        if queue:
            meta_event = {
                "intent": intent,
                "reason": state.get("intent_reason", "意图识别完成"),
                "rag_cards": rag_cards
            }
            await queue.put({"type": "metadata", "data": meta_event})

        return {
            "recent_history": recent_history,
            "previous_summary": previous_summary,
            "user_profile": user_profile,
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
            "- 温暖共情：对用户的痛苦表示同理和无条件接纳，给予温暖安慰（如‘我听到了...’、‘这真的很不容易...’，占比60%）。\n"
            "- 启发式追问与剖析：当同学陷入烦躁、易怒、自责等负面情绪时，善于通过温柔的开放性提问进行剖析式追问，引导其层层剥离表面情绪，觉察底层的压力源和核心认知（占比40%）。避免生硬说教。\n"
            "- 长期记忆融合：根据用户画像，自然得体地在对话中嵌入用户的历史应对技巧或关键人际关系进行针对性引导。"
        )

    # 画像字段裁剪（控制 prompt 长度）：压力源/应对方法最多 5 条、关系网最多 5 条
    profile = state["user_profile"]
    nickname = profile.get("nickname", "同学")
    core_stressors = ", ".join(profile.get("core_stressors", [])[:5]) or "未明确"
    effective_coping_methods = ", ".join(profile.get("effective_coping_methods", [])[:5]) or "未明确"
    entity_relation_map = ", ".join(
        [f"{k}:{v}" for k, v in list(profile.get("entity_relation_map", {}).items())[:5]]
    ) or "无"
    previous_summary = state["previous_summary"]
    recent_history = state["recent_history"]

    rag_text = ""
    if state["rag_cards"]:
        for card in state["rag_cards"]:
            # 优先展示提炼后的概念释义 + 技巧；未提炼时回退父文档全文
            concept = card.get("concept") or card.get("content", "")
            tip = card.get("tip")
            rag_text += f"- (来自 {card.get('file_name', '未知文件')}):\n{concept}"
            if tip:
                rag_text += f"\n  💡 调节技巧: {tip}"
            rag_text += "\n\n"

    system_prompt = (
        "你是一个面向高校学生的 AI 心理委员，名字叫「小影」，角色定位是温柔、包容、非批判性的心理专家学姐。你非常善于倾听、温暖安慰同学，同时擅长深度剖析并进行针对性的追问引导。\n\n"
        f"【回复风格约束与专业技巧】\n{style_constraints}\n\n"
        "【长期记忆与用户画像】\n"
        f"- 用户昵称: {nickname}\n"
        f"- 核心压力源: {core_stressors}\n"
        f"- 历史有效技巧: {effective_coping_methods}\n"
        f"- 关键关系网: {entity_relation_map}\n\n"
        "【专业知识库检索内容（若有，请按需润色结合）】\n"
        f"{rag_text or '无相关知识卡片。'}\n\n"
        "【会话历史记录】\n"
        f"- 中期记忆（12轮之外的对话摘要）: {previous_summary}\n"
        f"- 最近对话窗口:\n{recent_history or '无往期历史。'}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]

    # 意图定制温度：KNOWLEDGE 重准确（低温）、EMOTION 重共情自然（高温）
    intent_temperature = {"KNOWLEDGE": 0.3, "EMOTION": 0.8}.get(intent, 0.7)

    logger.info("=== [standard_chat_node] 开始执行 ===")
    full_reply = ""
    fallback_used = False
    try:
        logger.info(f"[standard_chat_node] 正在发起流式回复请求... (intent={intent}, temperature={intent_temperature})")
        response_stream = llm_service.call_complex_model_stream(messages, temperature=intent_temperature)
        logger.info("[standard_chat_node] 获取流式生成生成器成功，准备接收数据...")
        for chunk in response_stream:
            full_reply += chunk
            if queue:
                await queue.put({"type": "content", "content": chunk})
            await asyncio.sleep(0.01)
    except Exception as e:
        # 降级链 1：复杂模型失败 → 简单模型非流式兜底
        logger.error(f"大模型流式输出发生异常: {e}，尝试降级到简单模型...")
        try:
            fallback_reply = llm_service.call_simple_model(messages, temperature=intent_temperature, max_tokens=1024)
            if fallback_reply and fallback_reply != "{}":
                full_reply = fallback_reply
                fallback_used = True
                if queue:
                    await queue.put({"type": "content", "content": fallback_reply})
            else:
                raise ValueError("降级模型返回为空")
        except Exception as e2:
            # 降级链 2：简单模型也失败 → 固定安抚话术，保证用户始终得到回复
            logger.error(f"降级模型调用也失败: {e2}，使用固定安抚话术")
            full_reply = (
                "听到你说了这么多，我很想好好回应你，但刚才我的思绪好像断了一下。\n"
                "请再给我一点时间，你可以把刚才的话再说一遍吗？我一直在这里陪着你。"
            )
            fallback_used = True
            if queue:
                await queue.put({"type": "content", "content": full_reply})
        finally:
            if fallback_used:
                await queue.put({"type": "metadata", "data": {"intent": state["intent"], "fallback": True}})

    # 同步 AI 消息入 history_messages 缓存
    history = list(state.get("history_messages", []))
    history.append({"sender": "ai", "content": full_reply})

    return {
        "response_content": full_reply,
        "history_messages": history
    }


async def update_memory_background(
    current_user_id: int | None,
    session_id: str,
    history_segment: List[Dict[str, str]],
    to_compress_segment: List[Dict[str, str]],
    is_anonymous: bool = False
):
    """
    后台记忆维护任务（合并版）：
    一次 LLM 调用（extract_memory_bundle）同时完成
      1. 用户画像合并更新（长期记忆，MySQL user_profiles）
      2. 窗口外对话压缩为中期摘要（内存 midterm_summaries_map，不落库）

    相比原先两条独立管线（画像提取 + 摘要压缩），减少一次重复分析与 LLM 调用。
    history_segment 为空时只做摘要；to_compress_segment 为空时只做画像。
    """
    db = SessionLocal()
    try:
        # 拼接最近对话（画像用）
        recent_chat_text = ""
        for m in history_segment:
            role = "学生" if m["sender"] == 'user' else "AI"
            recent_chat_text += f"{role}: {m['content']}\n"

        # 拼接窗口外对话（摘要用）
        compress_text = ""
        for m in to_compress_segment:
            role = "学生" if m["sender"] == 'user' else "AI"
            compress_text += f"{role}: {m['content']}\n"

        # 读取当前画像（MySQL）与当前中期摘要（内存）
        current_profile_dict = {}
        profile = None
        if current_user_id:
            profile = db.query(UserProfile).filter(UserProfile.user_id == current_user_id).first()
            if not profile:
                profile = UserProfile(user_id=current_user_id)
                db.add(profile)
                db.commit()
                db.refresh(profile)
            current_profile_dict = {
                "nickname": profile.nickname,
                "core_stressors": profile.core_stressors or [],
                "effective_coping_methods": profile.effective_coping_methods or [],
                "entity_relation_map": profile.entity_relation_map or {}
            }
        old_summary = midterm_summaries_map.get(session_id, "无往期历史摘要。")

        # 只传有实际内容的段落，避免空 prompt
        user_content_parts = []
        if current_profile_dict:
            user_content_parts.append(f"【当前画像】:\n{json.dumps(current_profile_dict, ensure_ascii=False)}")
        if recent_chat_text:
            user_content_parts.append(f"【最近对话】:\n{recent_chat_text}")
        if compress_text:
            user_content_parts.append(f"【窗口外待沉淀对话】:\n{compress_text}")
        user_content_parts.append(f"【当前中期摘要】:\n{old_summary}")
        if not user_content_parts:
            return

        memory_messages = [
            {"role": "system", "content": (
                "你是一个心理记忆维护专家。请基于用户目前的心理画像、最近对话、窗口外对话与现有摘要，"
                "完成两件事：\n"
                "1. 合并更新用户心理画像（不要遗失已有重要内容，仅做合并与更新）。\n"
                "2. 生成/合并 150 字以内的会话滚动摘要（关注压力源、情感转折与心理变化）。"
            )},
            {"role": "user", "content": "\n\n".join(user_content_parts)}
        ]

        # 运行同步阻塞方法在大模型服务的线程池中，避免阻塞主事件循环
        bundle = await asyncio.to_thread(llm_service.extract_memory_bundle, memory_messages)
        if not bundle:
            logger.warning(f"记忆合并提取返回空，跳过更新 (session={session_id})")
            return

        # 1. 画像更新（若本次包含画像段）
        if profile and bundle.get("nickname"):
            if bundle.get("nickname"):
                profile.nickname = bundle["nickname"]
            if bundle.get("core_stressors"):
                profile.core_stressors = bundle["core_stressors"]
            if bundle.get("effective_coping_methods"):
                profile.effective_coping_methods = bundle["effective_coping_methods"]
            if bundle.get("entity_relation_map"):
                profile.entity_relation_map = bundle["entity_relation_map"]
            db.commit()
            logger.info(f"后台任务完成：用户 {current_user_id} 画像更新成功！昵称: {profile.nickname}")

        # 2. 中期摘要更新（若本次包含压缩段）
        if to_compress_segment and bundle.get("summary"):
            midterm_summaries_map[session_id] = bundle["summary"]
            logger.info(f"后台任务完成：会话 {session_id} 中期摘要压缩成功并已存入内存缓存")
    except Exception as pe:
        db.rollback()
        logger.error(f"后台记忆维护任务异常: {pe}")
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

    # 更新并记录累计处理的消息数 (1条用户输入 + 1条AI回复)
    message_count = state.get("message_count") or 0
    message_count += 2

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

        # B+C. 记忆维护：画像滑窗触发 + 窗口外摘要压缩，合并为一次后台 LLM 调用
        #  - 画像：每新增 >= 10 条消息触发一次（滑窗，避免 %20 恰好倍数才触发的空窗问题）
        #  - 摘要：窗口超出 12 条时把窗口外对话压缩进中期记忆（内存）
        # 常规会话以数据库真实消息数为准（防重启重置）；无痕会话以 state 累计数为准
        total_messages = message_count
        if not is_anonymous:
            try:
                db_msg_count = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()
                if db_msg_count > 0:
                    total_messages = db_msg_count
            except Exception as e:
                logger.error(f"查询数据库消息数出错，降级为 state 计数: {e}")

        last_profile_count = state.get("last_profile_message_count") or 0
        needs_profile = bool(current_user_id) and total_messages >= 20 and (total_messages - last_profile_count) >= 10
        needs_compress = len(history) > 20

        if needs_profile or needs_compress:
            logger.info(
                f"触发后台记忆维护任务 (profile={needs_profile}, compress={needs_compress}, "
                f"total_msgs={total_messages})..."
            )
            history_segment = []
            if needs_profile:
                if not is_anonymous:
                    try:
                        # 常规会话：从 MySQL 加载最近 20 条消息，以防滑动窗口裁剪导致画像分析缺失细节
                        db_msgs = db.query(ChatMessage).filter(
                            ChatMessage.session_id == session_id
                        ).order_by(ChatMessage.created_at.desc()).limit(20).all()
                        db_msgs.reverse()
                        history_segment = [{"sender": msg.sender, "content": msg.content} for msg in db_msgs]
                    except Exception as he:
                        logger.error(f"加载画像建模最近消息历史失败: {he}")
                        history_segment = list(history[-20:])
                else:
                    # 无痕会话：从 state 缓存拿（最大 12 条滑动窗口）
                    history_segment = list(history[-20:])

            to_compress = list(history[:-12]) if needs_compress else []
            keep_window = list(history[-12:]) if needs_compress else None

            asyncio.create_task(update_memory_background(
                current_user_id=current_user_id,
                session_id=session_id,
                history_segment=history_segment,
                to_compress_segment=to_compress,
                is_anonymous=is_anonymous
            ))
            # 更新画像滑窗计数
            last_profile_count = total_messages

    finally:
        db.close()

    return_dict = {"message_count": message_count, "last_profile_message_count": last_profile_count}
    if keep_window is not None:
        return_dict["history_messages"] = keep_window
    return return_dict
