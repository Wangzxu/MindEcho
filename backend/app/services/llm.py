# -*- coding: utf-8 -*-
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from config import Config
import logging

logger = logging.getLogger(__name__)

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
        else:
            try:
                # 初始化 LangChain 向量嵌入客户端
                self.embeddings_client = OpenAIEmbeddings(
                    model=self.embedding_model,
                    api_key=self.api_key,
                    base_url=self.base_url
                )
                
                # 初始化轻量级分类大模型
                self.simple_chat_client = ChatOpenAI(
                    model=self.simple_model,
                    api_key=self.api_key,
                    base_url=self.base_url,
                    temperature=0.0,
                    max_tokens=60
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
        """
        利用 LangChain OpenAIEmbeddings 获取文本向量 (Embedding)
        """
        if not self.embeddings_client:
            logger.warning(f"运行于 Mock 向量模型模式，返回 1024 维全零向量 (输入文本: {text[:20]}...)")
            logger.info("成功完成向量数据库嵌入提醒 (Mock 模式)！")
            return [0.0] * 1024

        try:
            # embed_query 接收单个字符串并生成它的 Embedding
            embedding = self.embeddings_client.embed_query(text)
            logger.info(f"成功完成向量数据库嵌入提醒！模型: {self.embedding_model}，输入长度: {len(text)}，向量维度: {len(embedding)}")
            return embedding
        except Exception as e:
            logger.error(f"获取向量失败 ({self.embedding_model}): {str(e)}")
            return [0.0] * 1024

    def call_simple_model(self, messages, temperature=0.0, max_tokens=100):
        """
        利用 LangChain ChatOpenAI 唤起轻量分类模型进行意图路由。
        """
        if not self.simple_chat_client:
            logger.warning("运行于 Mock 简单模型模式。")
            last_msg = messages[-1]["content"] if messages else ""
            if any(word in last_msg for word in ["死", "自杀", "跳楼", "吞药"]):
                return '{"intent": "CRISIS", "reason": "模拟检测：匹配到危机敏感词"}'
            elif any(word in last_msg for word in ["什么是", "科普", "技巧", "怎么"]):
                return '{"intent": "KNOWLEDGE", "reason": "模拟检测：提问心理概念"}'
            else:
                return '{"intent": "EMOTION", "reason": "模拟检测：日常情感倾诉"}'

        try:
            lc_msgs = self._convert_to_lc_messages(messages)
            # 使用 LangChain 的 invoke 方法直接调用
            response = self.simple_chat_client.invoke(
                input=lc_msgs,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.content.strip()
        except Exception as e:
            logger.error(f"简单模型调用失败 ({self.simple_model}): {str(e)}")
            raise e

    def call_complex_model_stream(self, messages, temperature=0.7, max_tokens=1024):
        """
        利用 LangChain ChatOpenAI.stream 唤起生成回复大模型，输出流式迭代生成器。
        """
        if not self.complex_chat_client:
            logger.warning("运行于 Mock 复杂模型流式模式。")
            mock_reply = "【模拟回复】你好！听到你分享你的感受，我在这里陪着你。这是一个没有配置 SiliconFlow API 密钥的模拟回复，如果需要真实对话，请在 .env 中配置有效的秘钥和模型。"
            def mock_generator():
                for char in mock_reply:
                    yield char
            return mock_generator()

        try:
            lc_msgs = self._convert_to_lc_messages(messages)
            # 使用 LangChain 的 stream 方法，迭代返回 Chunk 内容
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
        """
        利用 LangChain ChatOpenAI 唤起推理大模型进行总结。
        """
        if not self.summary_chat_client:
            logger.warning("运行于 Mock 总结模型模式。")
            return "【模拟总结】用户本次主要倾诉了期末备考引发的学业焦虑。有效的方法是“蝴蝶抱抱法”。画像中已同步此压力源。"

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
