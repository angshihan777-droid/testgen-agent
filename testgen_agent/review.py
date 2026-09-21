"""人工审核节点：仅在出现"疑似源码 bug"时暂停，把决定权交回给人。

用 LangGraph 的 interrupt 暂停图执行，抛出疑点上下文；调用方（CLI / MCP / Codex）
拿到后由人给出 "confirm_bug" 或 "ignore"，再以 Command(resume=...) 从断点续跑。
不是每条失败都打扰人——只有变异验证判定的高价值疑点才触发，体现 Agent 知道
何时值得找人。
"""
from __future__ import annotations

from langgraph.types import interrupt

from .state import AgentState


def review(state: AgentState) -> AgentState:
    """就 pending_review 里的疑似 bug 请求人工裁决，记录决定后回到 evaluate。"""
    bug = state["pending_review"]
    decision = interrupt({
        "type": "suspected_source_bug",
        "nodeid": bug.get("nodeid"),
        "message": bug.get("message"),
        "evidence": bug.get("evidence"),
        "options": ["confirm_bug", "ignore"],
        "hint": "confirm_bug=确认源码有误(标红上报) / ignore=当作测试期望有误(丢弃)",
    })
    decisions = list(state.get("review_decisions", []))
    decisions.append({"bug": bug, "decision": decision})
    return {**state, "review_decisions": decisions, "pending_review": None}
