"""用 LangGraph 组装 6 节点自主循环。

    analyze -> generate -> execute -> evaluate
                  ^            ^          |
                  |            |    decision 路由：
                  |            |      retry  -> generate（带上轮失败重写）
                  +------------+      review -> review -> evaluate（人工裁决后复判）
                                      done   -> report -> END

条件边由 evaluate 写入的 state["decision"] 驱动，是"自主循环"的来源，也是它作为
Agent 而非一次性脚本的本质。人工审核通过 interrupt 暂停，需配 checkpointer 续跑。
"""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .analyze import analyze
from .evaluate import evaluate
from .execute import execute
from .generate import generate
from .report import build_report
from .review import review
from .state import AgentState


def _route(state: AgentState) -> str:
    """根据 evaluate 的决策选择下一跳。"""
    return state.get("decision", "done")


def build_graph(checkpointer=None):
    """构建并编译 Agent 图。需人工审核时应传入 checkpointer 以支持断点续跑。"""
    g = StateGraph(AgentState)
    g.add_node("analyze", analyze)
    g.add_node("generate", generate)
    g.add_node("execute", execute)
    g.add_node("evaluate", evaluate)
    g.add_node("review", review)
    g.add_node("report", build_report)

    g.add_edge(START, "analyze")
    g.add_edge("analyze", "generate")
    g.add_edge("generate", "execute")
    g.add_edge("execute", "evaluate")
    g.add_conditional_edges(
        "evaluate", _route,
        {"retry": "generate", "review": "review", "done": "report"},
    )
    g.add_edge("review", "evaluate")
    g.add_edge("report", END)

    return g.compile(checkpointer=checkpointer or MemorySaver())
