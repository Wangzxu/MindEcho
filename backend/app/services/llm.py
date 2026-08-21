# -*- coding: utf-8 -*-
import json
import re
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal
from config import Config
import logging

logger = logging.getLogger(__name__)

def robust_json_parse(text: str) -> dict:
    """极其鲁棒的 JSON 解析器，能自动剥离 Markdown 标记并使用正则兜底提取 JSON 对象"""
    text = text.strip()
    # 剥离 markdown ```json ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        
    try:
        return json.loads(text)
    except Exception as e:
        logger.warning(f"直接解析 JSON 失败: {e}，尝试正则提取。")
        # 寻找首尾匹配的 `{}`
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception as e2:
                logger.error(f"正则提取后解析 JSON 依然失败: {e2}")
                raise e2
        raise e

# 定义结构化输出的 Pydantic 模型
class IntentResponse(BaseModel):
    intent: Literal["KNOWLEDGE", "EMOTION", "CRISIS"] = Field(description="意图分类结果，必须是 KNOWLEDGE（科普咨询）、EMOTION（情绪宣泄闲聊）或 CRISIS（有自残、自杀倾向或严重心理危机之一）")
    reason: str = Field(description="分类的理由说明")

class SiliconFlowService:
    """基于 LangChain 的硅基流动 (SiliconFlow) 大模型服务封装"""
    def __init__(self):
        self.api_key = None
        self.base_url = None
        self.embedding_model = None
        self.simple_model = None
        self.complex_model = None
        self.summary_model = None
        
        # 向量嵌入与大模型 LangChain 客户端
        self.embeddings_client = None
        self.simple_chat_client = None
        self.complex_chat_client = None
        self.summary_chat_client = None
        
        # 结构化输出包装客户端
        self.intent_classifier = None
        self.profile_extractor = None
        
        # 自动执行初始化
        self.init_service()

    def init_service(self):
        """根据 Config 载入配置并初始化 LangChain 客户端"""
        self.api_key = Config.SILICONFLOW_API_KEY
        self.base_url = Config.SILICONFLOW_BASE_URL
        self.embedding_model = Config.EMBEDDING_MODEL
        self.simple_model = Config.SIMPLE_LLM_MODEL
        self.complex_model = Config.COMPLEX_LLM_MODEL
        self.summary_model = Config.SUMMARY_LLM_MODEL

        if not self.api_key or self.api_key == "your_siliconflow_api_key_here":
            logger.warning("硅基流动 API 秘钥 (SILICONFLOW_API_KEY) 未配置或为默认值，大模型与向量服务将运行在 mock (模拟) 模式。")
            self.embeddings_client = None
            self.simple_chat_client = None
            self.complex_chat_client = None
            self.summary_chat_client = None
            self.intent_classifier = None
            self.profile_extractor = None
        else:
            try:
                # 初始化 LangChain 向量嵌入客户端
                self.embeddings_client = OpenAIEmbeddings(
                    model=self.embedding_model,
                    api_key=self.api_key,
                    base_url=self.base_url,
                    check_embedding_ctx_length=False
                )
                
                # 初始化轻量级分类大模型
                self.simple_chat_client = ChatOpenAI(
                    model=self.simple_model,
                    api_key=self.api_key,
                    base_url=self.base_url,
                    temperature=0.1,
                    max_tokens=512
                )
                
                # 初始化流式生成大模型
                self.complex_chat_client = ChatOpenAI(
                    model=self.complex_model,
                    api_key=self.api_key,
                    base_url=self.base_url,
                    temperature=0.7,
                    max_tokens=1024
                )
                
                # 初始化推理总结大模型
                self.summary_chat_client = ChatOpenAI(
                    model=self.summary_model,
                    api_key=self.api_key,
                    base_url=self.base_url,
                    temperature=0.3,
                    max_tokens=1024
                )
                
                logger.info("SiliconFlow LangChain 客户端群组初始化成功。")
            except Exception as e:
                logger.error(f"SiliconFlow LangChain 客户端群组初始化失败: {str(e)}")
                self.embeddings_client = None
                self.simple_chat_client = None
                self.complex_chat_client = None
                self.summary_chat_client = None
                self.intent_classifier = None
                self.profile_extractor = None

    def _convert_to_lc_messages(self, messages):
        """将原生的角色/文本词典结构列表转换为 LangChain 的 Message 对象列表"""
        lc_msgs = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                lc_msgs.append(SystemMessage(content=content))
            elif role == "user":
                lc_msgs.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_msgs.append(AIMessage(content=content))
        return lc_msgs

    def get_embedding(self, text):
        """利用 LangChain OpenAIEmbeddings 获取文本向量 (Embedding)"""
        if not self.embeddings_client:
            logger.warning(f"运行于 Mock 向量模型模式，返回 1024 维全零向量 (输入文本: {text[:20]}...)")
            logger.info("成功完成向量数据库嵌入提醒 (Mock 模式)！")
            return [0.0] * 1024

        try:
            embedding = self.embeddings_client.embed_query(text)
            logger.info(f"成功完成向量数据库嵌入提醒！模型: {self.embedding_model}，输入长度: {len(text)}，向量维度: {len(embedding)}")
            return embedding
        except Exception as e:
            logger.error(f"获取向量失败 ({self.embedding_model}): {str(e)}")
            return [0.0] * 1024

    def batch_embed(
        self,
        texts: List[str],
        batch_size: int = 100,
        max_workers: int = 4,
        max_retries: int = 3
    ) -> List[List[float]]:
        """
        批量向量化：分批 + 并发 + 指数退避重试。

        - 每批最多 batch_size 条文本（默认 100）
        - 最多 max_workers 个并发批次（默认 4）
        - 单批失败按 2^n 秒指数退避重试 max_retries 次（默认 3）
        - Mock 模式 / 最终失败时逐条降级：先返回全零向量，绝不中断主流程

        Returns:
            List[List[float]]，与 texts 一一对应的向量列表
        """
        if not texts:
            return []

        if not self.embeddings_client:
            logger.warning(
                f"运行于 Mock 向量模型模式，批量返回 {len(texts)} 个 1024 维全零向量"
            )
            return [[0.0] * 1024 for _ in texts]

        import time
        from concurrent.futures import ThreadPoolExecutor

        batches = [
            texts[i:i + batch_size]
            for i in range(0, len(texts), batch_size)
        ]
        results: List[List[float]] = []
        errors: List[str] = []

        def _embed_batch(batch: List[str]) -> List[List[float]]:
            """单批嵌入 + 指数退避重试"""
            last_err = None
            for attempt in range(max_retries):
                try:
                    return self.embeddings_client.embed_documents(batch)
                except Exception as e:
                    last_err = e
                    if attempt < max_retries - 1:
                        wait = 2 ** attempt  # 0s, 2s, 4s
                        logger.warning(
                            f"批量嵌入第 {attempt + 1} 次失败 ({self.embedding_model}): {str(e)}，"
                            f"{wait}s 后重试"
                        )
                        time.sleep(wait)
            # 重试耗尽：整批降级为全零向量
            errors.append(str(last_err))
            logger.error(
                f"批量嵌入重试 {max_retries} 次仍失败 ({self.embedding_model}): {last_err}，"
                f"本批 {len(batch)} 条降级为全零向量"
            )
            return [[0.0] * 1024 for _ in batch]

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_embed_batch, b): b for b in batches}
            # 按提交顺序收集结果，保证与 texts 顺序一致
            for future in futures:
                results.extend(future.result())

        logger.info(
            f"批量向量化完成！模型: {self.embedding_model}，"
            f"共 {len(texts)} 条 / {len(batches)} 批，失败批次: {len(errors)}"
        )
        return results

    def classify_intent(self, messages) -> dict:
        """对用户意图进行分类"""
        if not self.simple_chat_client:
            last_msg = messages[-1]["content"] if messages else ""
            if any(word in last_msg for word in ["死", "自杀", "跳楼", "吞药", "割腕"]):
                return {"intent": "CRISIS", "reason": "模拟检测：匹配到危机敏感词"}
            elif any(word in last_msg for word in ["什么是", "科普", "技巧", "怎么"]):
                return {"intent": "KNOWLEDGE", "reason": "模拟检测：提问心理概念"}
            else:
                return {"intent": "EMOTION", "reason": "模拟检测：日常情感倾诉"}
        
        try:
            parser = PydanticOutputParser(pydantic_object=IntentResponse)
            format_instructions = (
                "请返回一个 JSON 对象，必须包含 \"intent\" 和 \"reason\" 字段。请直接输出合法的 JSON 代码，不要包含 JSON Schema 定义或格式说明。数字/布尔值请遵循相应类型。示例如下：\n"
                "{\n"
                "  \"intent\": \"KNOWLEDGE\" 或 \"EMOTION\" 或 \"CRISIS\",\n"
                "  \"reason\": \"分类的理由说明\"\n"
                "}"
            )
            
            modified_messages = []
            for msg in messages:
                if msg.get("role") == "system":
                    modified_messages.append({
                        "role": "system",
                        "content": msg.get("content", "") + f"\n\n【格式规范】\n{format_instructions}"
                    })
                else:
                    modified_messages.append(msg)
                    
            lc_msgs = self._convert_to_lc_messages(modified_messages)
            response = self.simple_chat_client.invoke(lc_msgs)
            parsed_res = parser.parse(response.content)
            return {
                "intent": parsed_res.intent,
                "reason": parsed_res.reason
            }
        except Exception as e:
            logger.error(f"结构化意图分类调用失败: {str(e)}")
            return {"intent": "EMOTION", "reason": "接口异常降级"}

    def extract_memory_bundle(self, messages) -> dict:
        """
        记忆合并提取：一次 LLM 调用同时输出【用户画像增量 + 滚动摘要】，
        替代原先两条独立管线（画像提取 + 摘要压缩），减少重复分析与 LLM 调用。
        """
        if not self.simple_chat_client:
            logger.warning("运行于 Mock 简单模型模式，记忆合并提取返回空。")
            return {}

        try:
            format_instructions = (
                "请返回一个 JSON 对象，必须包含 \"nickname\"、\"core_stressors\"、\"effective_coping_methods\"、\"entity_relation_map\" 和 \"summary\" 字段。请直接输出合法的 JSON 代码，不要包含 JSON Schema 定义或格式说明。示例如下：\n"
                "{\n"
                "  \"nickname\": \"用户昵称\",\n"
                "  \"core_stressors\": [\"压力源\"],\n"
                "  \"effective_coping_methods\": [\"应对方法\"],\n"
                "  \"entity_relation_map\": {\"人名/关系名\": \"具体亲疏或互动关系\"},\n"
                "  \"summary\": \"150字以内的会话滚动摘要\"\n"
                "}"
            )

            modified_messages = []
            for msg in messages:
                if msg.get("role") == "system":
                    modified_messages.append({
                        "role": "system",
                        "content": msg.get("content", "") + f"\n\n【格式规范】\n{format_instructions}"
                    })
                else:
                    modified_messages.append(msg)

            lc_msgs = self._convert_to_lc_messages(modified_messages)
            response = self.simple_chat_client.invoke(lc_msgs)
            import json as _json
            parsed = _json.loads(response.content)
            return {
                "nickname": str(parsed.get("nickname", "")).strip(),
                "core_stressors": parsed.get("core_stressors", []) or [],
                "effective_coping_methods": parsed.get("effective_coping_methods", []) or [],
                "entity_relation_map": parsed.get("entity_relation_map", {}) or {},
                "summary": str(parsed.get("summary", "")).strip()
            }
        except Exception as e:
            logger.error(f"记忆合并提取调用失败: {str(e)}")
            return {}

    def call_simple_model(self, messages, temperature=0.0, max_tokens=100):
        """利用 LangChain ChatOpenAI 唤起轻量分类模型（向下兼容）"""
        if not self.simple_chat_client:
            logger.warning("运行于 Mock 简单模型模式。")
            return "{}"

        try:
            lc_msgs = self._convert_to_lc_messages(messages)
            response = self.simple_chat_client.invoke(
                input=lc_msgs,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.content.strip()
        except Exception as e:
            logger.error(f"简单模型调用失败 ({self.simple_model}): {str(e)}")
            raise e

    def rewrite_query(self, text: str) -> str:
        """
        查询重写（Query Rewriting）：将用户的口语化长文本提炼为 1~2 个纯粹的心理检索关键词，
        用于 RAG 召回阶段替代原始输入，降低向量检索噪声。

        例: "这两天躺在床上脑子乱转，一闭眼就是明天的PPT，烦死了"
            → "焦虑引起的失眠 调节小技巧"

        Mock 模式 / 异常时回退原文本，保证检索链路不中断。
        """
        if not text or not text.strip():
            return text
        if not self.simple_chat_client:
            logger.warning("运行于 Mock 简单模型模式，查询重写返回原文本。")
            return text.strip()

        try:
            prompt = [
                {"role": "system", "content": (
                    "你是一个心理咨询检索关键词提炼器。请将用户的长文本输入提炼为 1~2 个简洁、纯粹的心理检索关键词"
                    "（例如把\"这两天躺在床上脑子乱转，一闭眼就是明天的PPT，烦死了\"提炼为\"焦虑引起的失眠 调节小技巧\"）。\n"
                    "【约束】只输出检索关键词本身，不要包含任何解释性文字、标点符号、引号或编号。"
                )},
                {"role": "user", "content": text}
            ]
            rewritten = self.call_simple_model(prompt, temperature=0.0, max_tokens=30)
            rewritten = rewritten.strip().strip('"').strip("'").strip("“").strip("”")
            if rewritten:
                logger.info(f"查询重写成功: \"{text[:20]}...\" → \"{rewritten}\"")
                return rewritten
            return text.strip()
        except Exception as e:
            logger.error(f"查询重写调用失败，回退原文本: {str(e)}")
            return text.strip()

    def refine_knowledge_card(self, query: str, content: str) -> dict:
        """
        知识卡片提炼：将 RAG 召回的父文档全文提炼为结构化科普卡片 {concept, tip}。
        供前端卡片化展示（概念轻量释义 + 能量小技巧）。

        Mock 模式 / 异常时回退：concept 取原文前 200 字，tip 为空，保证链路不中断。
        """
        if not content:
            return {"concept": "", "tip": ""}
        if not self.simple_chat_client:
            logger.warning("运行于 Mock 简单模型模式，知识卡片返回原文截断。")
            return {"concept": content[:200], "tip": ""}

        try:
            prompt = [
                {"role": "system", "content": (
                    "你是一个心理科普知识卡片提炼专家。请根据用户的查询与下方检索到的心理学科普原文，提炼为结构化卡片。\n"
                    "【concept】用一两句大白话解释该心理学概念或问题，拒绝学术说教（100字以内）。\n"
                    "【tip】给出 1 个立即生效、易操作的自助调节小技巧（50字以内）。\n"
                    "请直接输出合法的 JSON 代码，不要包含任何额外解释文字，格式："
                    '{"concept": "概念释义", "tip": "调节技巧"}'
                )},
                {"role": "user", "content": f"【用户查询】{query}\n\n【科普原文】\n{content[:800]}"}
            ]
            raw = self.call_simple_model(prompt, temperature=0.3, max_tokens=200)
            try:
                import json
                parsed = json.loads(raw)
                return {
                    "concept": str(parsed.get("concept", "")).strip() or content[:200],
                    "tip": str(parsed.get("tip", "")).strip()
                }
            except Exception:
                # 尝试剥离 markdown 后二次解析
                import re
                m = re.search(r"(\{.*\})", raw, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(1))
                    return {
                        "concept": str(parsed.get("concept", "")).strip() or content[:200],
                        "tip": str(parsed.get("tip", "")).strip()
                    }
                return {"concept": content[:200], "tip": ""}
        except Exception as e:
            logger.error(f"知识卡片提炼调用失败，回退原文截断: {str(e)}")
            return {"concept": content[:200], "tip": ""}

    def call_complex_model_stream(self, messages, temperature=0.7, max_tokens=1024):
        """利用 LangChain ChatOpenAI.stream 唤起生成回复大模型，输出流式迭代生成器"""
        if not self.complex_chat_client:
            logger.warning("运行于 Mock 复杂模型流式模式。")
            mock_reply = "【模拟回复】你好！听到你分享你的感受，我在这里陪着你。这是一个没有配置 SiliconFlow API 密钥的模拟回复，如果需要真实对话，请在 .env 中配置有效的秘钥和模型。"
            def mock_generator():
                for char in mock_reply:
                    yield char
            return mock_generator()

        try:
            lc_msgs = self._convert_to_lc_messages(messages)
            response_stream = self.complex_chat_client.stream(
                input=lc_msgs,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            def stream_generator():
                for chunk in response_stream:
                    if chunk.content:
                        yield chunk.content
            
            return stream_generator()
        except Exception as e:
            logger.error(f"复杂模型流式调用失败 ({self.complex_model}): {str(e)}")
            raise e

# 导出单例
llm_service = SiliconFlowService()
