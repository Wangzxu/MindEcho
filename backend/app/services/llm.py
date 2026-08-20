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

class MeaningfulResponse(BaseModel):
    is_meaningful: bool = Field(description="是否包含具体心理感受、生活烦恼、人际困扰或具有心理学分析价值的信息")

class UserProfileResponse(BaseModel):
    nickname: str = Field(description="用户昵称")
    core_stressors: List[str] = Field(description="核心压力源列表")
    effective_coping_methods: List[str] = Field(description="历史有效应对方法列表")
    entity_relation_map: Dict[str, str] = Field(description="关键人际关系网络字典")

class StructuredMemory(BaseModel):
    is_valuable: bool = Field(description=(
        "该输入是否包含【具体的、有长期存储和后续追踪价值的个人背景、生活细节、生活事件、人际关系或应对行为特征】。"
        "如果仅是泛泛的、没有具体事件/细节的日常闲聊或情绪宣泄发泄（例如‘我好烦’、‘太难受了’、‘开心’、‘你好’、‘谢谢’），"
        "必须设为 false。"
    ))
    recalled_text: str = Field(description=(
        "适合用于历史回忆的标准化客观结构陈述，必须使用固定模板生成："
        "‘涉及主体核心事心理感受组成一句话，比如：用户喜欢看书’"
    ))

class DuplicateCheckResponse(BaseModel):
    is_duplicate: bool = Field(description="新提炼的记忆内容是否与已有的任意一条历史记忆在语义上重复、相似或被其完全覆盖。如果是，返回 true，否则返回 false")
    reason: str = Field(description="简短的查重理由说明")

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
        self.meaningful_judge = None
        self.profile_extractor = None
        self.memory_extractor = None
        self.duplicate_checker = None
        
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
            self.meaningful_judge = None
            self.profile_extractor = None
            self.memory_extractor = None
            self.duplicate_checker = None
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
                self.meaningful_judge = None
                self.profile_extractor = None
                self.memory_extractor = None
                self.duplicate_checker = None

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

    def judge_meaningful(self, messages) -> bool:
        """判断消息是否有心理学分析价值"""
        if not self.simple_chat_client:
            return True
            
        try:
            parser = PydanticOutputParser(pydantic_object=MeaningfulResponse)
            format_instructions = (
                "请返回一个 JSON 对象，必须包含 \"is_meaningful\" 字段。请直接输出合法的 JSON 代码，不要包含 JSON Schema 定义或格式说明。数字/布尔值请遵循相应类型。示例如下：\n"
                "{\n"
                "  \"is_meaningful\": true 或 false\n"
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
            return bool(parsed_res.is_meaningful)
        except Exception as e:
            logger.error(f"结构化特征评估调用失败: {str(e)}")
            return False

    def extract_profile(self, messages) -> dict:
        """提取/合并用户画像特征"""
        if not self.simple_chat_client:
            return {
                "nickname": "同学",
                "core_stressors": ["学业压力"],
                "effective_coping_methods": ["情绪宣泄"],
                "entity_relation_map": {}
            }
            
        try:
            parser = PydanticOutputParser(pydantic_object=UserProfileResponse)
            format_instructions = (
                "请返回一个 JSON 对象，必须包含 \"nickname\"、\"core_stressors\"、\"effective_coping_methods\" 和 \"entity_relation_map\" 字段。请直接输出合法的 JSON 代码，不要包含 JSON Schema 定义或格式说明。数字/布尔值请遵循相应类型。示例如下：\n"
                "{\n"
                "  \"nickname\": \"用户昵称\",\n"
                "  \"core_stressors\": [\"压力源\"],\n"
                "  \"effective_coping_methods\": [\"应对方法\"],\n"
                "  \"entity_relation_map\": {\"人名/关系名\": \"具体亲疏或互动关系\"}\n"
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
                "nickname": parsed_res.nickname,
                "core_stressors": parsed_res.core_stressors,
                "effective_coping_methods": parsed_res.effective_coping_methods,
                "entity_relation_map": parsed_res.entity_relation_map
            }
        except Exception as e:
            logger.error(f"结构化画像提取调用失败: {str(e)}")
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

    def extract_structured_memory(self, messages) -> dict:
        """从用户发言中提取结构化记忆特征"""
        if not self.simple_chat_client:
            logger.info("模型加载失败，直接跳过")
            return {"is_valuable":False, "recalled_text":""}
            
        try:
            # 1. 强依赖 Pydantic 自身的格式生成器，确保标准 Schema
            # parser = PydanticOutputParser(pydantic_object=StructuredMemory)
            # pydantic_instructions = parser.get_format_instructions()
            
            # 2. 精简、明确的 Few-Shot 提示词（直接针对 9B 模型做特化）
            system_rules = (
                "请返回一个 JSON 对象，必须包含 \"is_valuable\" 和 \"recalled_text\" 字段。\n"
                "is_valuable: 你的唯一任务是从对话中提炼出需要长期沉淀的【个人背景、兴趣喜好、客观事实与核心状态】，拒绝无事实背景的纯情绪发泄。有就为true，反之为false\n"
                "recalled_text: 当is_valuable为true时填入内容摘要，反之可以为空\n"
                "请直接输出合法的 JSON 代码，不要包含 JSON Schema 定义或格式说明。数字/布尔值请遵循相应类型。示例如下：\n"
                "{\n"
                "  \"is_valuable\": \"false\" 或 \"true\",\n"
                "  \"recalled_text\": \"当is_valuable为true时填入内容摘要，反之可以为空\"\n"
                "}"
            )
            
            # 3. 安全健壮地注入 System Prompt
            modified_messages = []
            has_system = False
            for msg in messages:
                if msg.get("role") == "system":
                    modified_messages.append({
                        "role": "system",
                        "content": f"{msg.get('content', '')}\n\n{system_rules}"
                    })
                    has_system = True
                else:
                    modified_messages.append(msg)
                    
            # 如果传入的上下文中没有 System 消息，务必手动在队头补上
            if not has_system:
                modified_messages.insert(0, {"role": "system", "content": system_rules})
                    
            # 4. 调用模型
            lc_msgs = self._convert_to_lc_messages(modified_messages)
            llm = self.simple_chat_client.with_structured_output(StructuredMemory)
            response = llm.invoke(lc_msgs)
            return response
        except Exception as e:
            logger.error(f"提取结构化记忆特征面临严重崩溃: {str(e)}")
            return {"is_valuable":False, "recalled_text":""}

    def check_memory_duplicate(self, new_memory: str, existing_memories: List[str]) -> bool:
        """使用大模型判断新记忆是否与已有记忆重复"""
        if not self.simple_chat_client:
            logger.warning("运行于 Mock 查重模式。")
            return False
            
        try:
            parser = PydanticOutputParser(pydantic_object=DuplicateCheckResponse)
            format_instructions = (
                "请返回一个 JSON 对象，必须包含 \"is_duplicate\" 和 \"reason\" 字段。请直接输出合法的 JSON 代码，不要包含 JSON Schema 定义或格式说明。数字/布尔值请遵循相应类型。示例如下：\n"
                "{\n"
                "  \"is_duplicate\": true 或 false,\n"
                "  \"reason\": \"判定理由\"\n"
                "}"
            )
            
            prompt = [
                {"role": "system", "content": (
                    "你是一个心理咨询记忆系统的语义查重专家。你需要比对一条【新提炼的记忆】与一组【已有的历史记忆】，"
                    "判断新记忆是否在语义上与历史记忆中的某一条重复、高度相似，或者已被其完全覆盖（例如，只是措辞微调，但反映的事件、情绪和关系完全一致）。\n"
                    f"【格式规范】\n{format_instructions}"
                )},
                {"role": "user", "content": (
                    f"【已有的历史记忆】:\n" + "\n".join([f"- {m}" for m in existing_memories]) + f"\n\n"
                    f"【新提炼的记忆】:\n{new_memory}"
                )}
            ]
            lc_msgs = self._convert_to_lc_messages(prompt)
            response = self.simple_chat_client.invoke(lc_msgs)
            parsed_res = parser.parse(response.content)
            logger.info(f"大模型语义查重判定: 重复={parsed_res.is_duplicate}, 原因={parsed_res.reason}")
            return parsed_res.is_duplicate
        except Exception as e:
            logger.error(f"语义查重调用失败: {str(e)}")
            return False
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

    def call_summary_model(self, messages, temperature=0.3, max_tokens=1024):
        """利用 LangChain ChatOpenAI 唤起推理大模型进行总结"""
        if not self.summary_chat_client:
            logger.warning("运行于 Mock 总结模型模式。")
            return "【模拟总结】用户本次主要倾诉了期末备考引发的学业焦虑。画像中已同步此压力源。"

        try:
            lc_msgs = self._convert_to_lc_messages(messages)
            response = self.summary_chat_client.invoke(
                input=lc_msgs,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.content.strip()
        except Exception as e:
            logger.error(f"总结模型调用失败 ({self.summary_model}): {str(e)}")
            raise e

# 导出单例
llm_service = SiliconFlowService()
