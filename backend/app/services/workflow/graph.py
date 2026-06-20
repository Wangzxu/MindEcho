# -*- coding: utf-8 -*-
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.workflow.state import ChatWorkflowState
from app.services.workflow.nodes import (
    filter_and_route_node,
    load_context_node,
    crisis_handler_node,
    standard_chat_node,
    save_message_node
)

def route_after_intent(state: ChatWorkflowState) -> str:
    """
    意图条件路由边缘判定
    """
    if state["intent"] == "CRISIS":
        return "crisis"
    else:
        return "load_context"

def build_workflow():
    workflow = StateGraph(ChatWorkflowState)
    
    # 注册节点
    workflow.add_node("filter_and_route", filter_and_route_node)
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("crisis_handler", crisis_handler_node)
    workflow.add_node("standard_chat", standard_chat_node)
    workflow.add_node("save_message", save_message_node)
    
    # 设置入口
    workflow.set_entry_point("filter_and_route")
    
    # 注册条件边 (安全网关判定)
    workflow.add_conditional_edges(
        "filter_and_route",
        route_after_intent,
        {
            "crisis": "crisis_handler",
            "load_context": "load_context"
        }
    )
    
    # 普通会话流程
    workflow.add_edge("load_context", "standard_chat")
    workflow.add_edge("standard_chat", "save_message")
    
    # 危机熔断流程
    workflow.add_edge("crisis_handler", "save_message")
    
    # 汇流至终点
    workflow.add_edge("save_message", END)
    
    # 编译并引入 MemorySaver 作为持久化 checkpointer 保证多轮 state 的存储与恢复
    return workflow.compile(checkpointer=MemorySaver())

# 导出单例编译后的图实例
workflow_agent = build_workflow()
