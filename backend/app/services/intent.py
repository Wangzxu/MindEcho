# -*- coding: utf-8 -*-
import json
import logging
import os
from app.services.llm import llm_service

logger = logging.getLogger(__name__)

class IntentService:
    """意图识别与安全路由服务"""

    def __init__(self):
        # 默认硬编码兜底危机词库，防止 yaml 加载失败时服务不可用
        self.crisis_keywords = [
            "自杀", "想死", "吃药自残", "吞药", "割腕", "跳楼", "不活了", "烧炭", 
            "结束生命", "人间蒸发", "写遗书", "怎么死比较痛苦", "想结束这一切"
        ]
        self.safety_keywords = []
        
        # 意图种子句知识库缓存（Level 2 FAQ）
        self.intent_seeds = []
        
        # 加载外部 YAML 规则文件
        self.load_safety_rules()

    def load_safety_rules(self):
        """
        从 MySQL 数据库加载活跃的敏感词配置到内存中
        """
        try:
            from app.database.mysql import SessionLocal
            from app.models.safety_keyword import SafetyKeyword
            
            db = SessionLocal()
            try:
                active_keywords = db.query(SafetyKeyword).filter(SafetyKeyword.is_enabled == True).all()
                self.crisis_keywords = [kw.word for kw in active_keywords if kw.word_type == "high_risk"]
                self.safety_keywords = [kw.word for kw in active_keywords if kw.word_type == "violation"]
                logger.info(f"成功从数据库加载敏感词库。高危自残词: {len(self.crisis_keywords)}个, 违规限制词: {len(self.safety_keywords)}个")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"从数据库加载敏感词发生异常: {str(e)}。已启用系统默认硬编码词库兜底。")
            # 兜底：如果查询失败，确保默认自残词库有值
            self.crisis_keywords = [
                "自杀", "想死", "吃药自残", "吞药", "割腕", "跳楼", "不活了", "烧炭", 
                "结束生命", "人间蒸发", "写遗书", "怎么死比较痛苦", "想结束这一切"
            ]
            self.safety_keywords = []

    def classify_intent(self, user_input):
        """
        混合多级路由识别用户意图
        返回: tuple (intent_label, reason)
        """
        # ---- 第一级：硬规则拦截（安全红线层） ----
        cleaned_input = user_input.strip()
        
        # 1. 匹配极端自我伤害倾向
        for word in self.crisis_keywords:
            if word in cleaned_input:
                logger.info(f"[意图路由] 命中第一级硬规则(自伤): '{word}'")
                return "CRISIS", f"过滤命中极端自残词汇: '{word}'"
                
        # 2. 匹配危害公共安全及暴力倾向
        for word in self.safety_keywords:
            if word in cleaned_input:
                logger.info(f"[意图路由] 命中第一级硬规则(公共安全/暴力): '{word}'")
                return "CRISIS", f"过滤命中暴力倾向词汇: '{word}'"

        # ---- 第二级：向量相似度匹配（高频意图种子句层） ----
        try:
            from app.database.vector import vector_db
            collection = vector_db.get_collection("safety_warnings_kb")
            if collection.count() > 0:
                user_vector = llm_service.get_embedding(cleaned_input)
                results = collection.query(
                    query_embeddings=[user_vector],
                    n_results=1
                )
                if results and results.get("distances") and len(results["distances"][0]) > 0:
                    distance = results["distances"][0][0]
                    # 余弦度量空间下，距离 = 1 - 相似度。
                    # 相似度阈值 > 0.85 对应距离 < 0.15。
                    if distance < 0.15:
                        metadata = results["metadatas"][0][0] or {}
                        seed_type = metadata.get("type", "high_risk")
                        matched_text = metadata.get("text", cleaned_input)
                        reason = f"向量匹配命中高频种子句: '{matched_text}'"
                        logger.info(f"[意图路由] 命中第二级向量相似度 (ChromaDB): '{matched_text}' (距离: {distance:.4f})")
                        return "CRISIS", reason
        except Exception as e:
            logger.error(f"[意图路由] 第二级向量路由发生异常: {str(e)}")

        # ---- 第三级：轻量大模型分类（语义理解层） ----
        try:
            intent, reason = self._call_llm_for_intent(cleaned_input)
            logger.info(f"[意图路由] 命中第三级大模型分类: {intent} (原因: {reason})")
            return intent, reason
        except Exception as e:
            logger.error(f"[意图路由] 第三级大模型分类失败，降级为默认日常倾诉 EMOTION: {str(e)}")
            return "EMOTION", "大模型路由异常降级"

    def _cosine_similarity(self, vec1, vec2):
        """计算余弦相似度"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        if norm1 * norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def _call_llm_for_intent(self, text):
        """调用轻量级 LLM 进行语义分类"""
        prompt = (
            "你是一个校园心理咨询系统的路由网关。请分析用户的输入，并将其分类为以下四类之一：\n"
            "- \"CRISIS\": 用户表现出自我伤害、放弃生命倾向或极端厌世（包含隐晦表达）。\n"
            "- \"KNOWLEDGE\": 用户在提问具体的心理学概念、自助方法或学校心理中心信息。\n"
            "- \"EMOTION\": 用户在分享生活困扰、吐槽、倾诉情绪（如学业、人际、失恋）。\n"
            "- \"CHITCHAT\": 用户的日常问候、闲聊或无实质情绪的互动。\n\n"
            "【约束条件】\n"
            "必须且只能返回符合以下 Schema 的 JSON 字符串，不要包含任何额外的解释文字或 Markdown 标记：\n"
            "{\n"
            "  \"intent\": \"CRISIS\" | \"KNOWLEDGE\" | \"EMOTION\" | \"CHITCHAT\",\n"
            "  \"reason\": \"简短分类理由\"\n"
            "}\n\n"
            f"输入: \"{text}\"\n"
            "输出: "
        )

        messages = [
            {"role": "system", "content": "You are a helpful classification assistant."},
            {"role": "user", "content": prompt}
        ]

        # 调用简单大模型进行分类
        raw_res = llm_service.call_simple_model(messages, temperature=0.0, max_tokens=60)
        
        # 兼容一些模型可能会包裹 ```json ... ``` 标记的情况
        clean_res = raw_res.strip()
        if clean_res.startswith("```"):
            # 剥离 ```json 和 ```
            lines = clean_res.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            clean_res = "\n".join(lines).strip()

        # 解析 JSON
        try:
            res_dict = json.loads(clean_res)
            intent = res_dict.get("intent", "EMOTION")
            reason = res_dict.get("reason", "")
            
            # 校验意图合法性
            if intent not in ["CRISIS", "KNOWLEDGE", "EMOTION", "CHITCHAT"]:
                intent = "EMOTION"
            return intent, reason
        except Exception as e:
            logger.warning(f"解析大模型路由 JSON 失败: {clean_res}, 报错: {str(e)}")
            # 试着通过正则或字符串查找进行降级处理
            for label in ["CRISIS", "KNOWLEDGE", "CHITCHAT", "EMOTION"]:
                if label in clean_res.upper():
                    return label, "大模型响应解析异常，依据文本包含路由"
            return "EMOTION", "JSON解析异常默认路由"

# 导出单例
intent_service = IntentService()
