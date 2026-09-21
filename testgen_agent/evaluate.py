"""⑤ evaluate 节点：门禁判定 + 失败归因。纯函数，只读 execute 产出的事实。

因为要在人工审核（interrupt）后被重新进入，本节点不持有任何沙盒/子进程状态，
只消费 state 中 execute 节点写入的确定性事实：last_run、mutation、source_tampered。
"""
from __future__ import annotations

from .state import AgentState


def _classify(failure: dict) -> str:
    """按堆栈把失败分为 'test_error'（测试自身坏）或 'assertion'（值不符）。"""
    tb = (failure.get("traceback", "") or "") + (failure.get("message", "") or "")
    if any(k in tb for k in ("SyntaxError", "ImportError", "ModuleNotFoundError",
                             "NameError", "IndentationError")):
        return "test_error"
    return "assertion"


def evaluate(state: AgentState) -> AgentState:
    """结合运行结果与变异分析给出决策，写回 state。"""
    run = state["last_run"]
    mut = state.get("mutation", {"total": 0, "killed": 0, "survived": []})

    # 1. 防作弊：源码被改则判非法，强制重试
    if state.get("source_tampered"):
        return {**state, "gate_passed": False, "decision": "retry",
                "discarded": state.get("discarded", 0) + 1, "pending_review": None}

    # 2. 归因
    suspected = list(state.get("suspected_bugs", []))
    test_errors = 0
    for f in run["failures"]:
        if _classify(f) == "test_error":
            test_errors += 1
        elif mut["survived"] or mut["killed"] < mut["total"]:
            bug = {"nodeid": f["nodeid"], "message": f["message"],
                   "evidence": "断言失败且变异验证显示测试描述了正确行为"}
            if bug not in suspected:
                suspected.append(bug)

    reviewed = [d["bug"] for d in state.get("review_decisions", [])]
    new_bugs = [b for b in suspected if b not in reviewed]

    cov_ok = run["coverage"] >= state.get("coverage_target", 80.0)
    unresolved = test_errors > 0

    result = {**state,
              "coverage_after": run["coverage"],
              "adopted": run["passed"],
              "discarded": state.get("discarded", 0) + test_errors,
              "suspected_bugs": suspected,
              "mutants_total": mut["total"],
              "mutants_killed": mut["killed"],
              "gate_passed": cov_ok and not unresolved and not new_bugs}

    # 3. 决策
    if new_bugs:
        result["pending_review"] = new_bugs[0]
        result["decision"] = "review"
    elif result["gate_passed"] or state["attempt"] >= state.get("max_attempts", 3):
        result["decision"] = "done"
        result["pending_review"] = None
    else:
        result["decision"] = "retry"
        result["pending_review"] = None
    return result
