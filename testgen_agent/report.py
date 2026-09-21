"""⑥ report 节点：汇总量化指标，产出报告字典与可选 JSON 文件。

指标全部来自真实运行与变异分析，不含估算：覆盖率变化、采纳/丢弃数、迭代轮数、
变异杀伤、经人工确认的真实 bug 列表。
"""
from __future__ import annotations

import json
from pathlib import Path

from .state import AgentState


def build_report(state: AgentState) -> AgentState:
    """收敛所有指标为 report 字典，若给定 report_path 则写盘。"""
    confirmed = [d["bug"] for d in state.get("review_decisions", [])
                 if d.get("decision") == "confirm_bug"]
    report = {
        "source": state["source_path"],
        "coverage_before": state.get("coverage_before", 0.0),
        "coverage_after": state.get("coverage_after", 0.0),
        "coverage_delta": round(state.get("coverage_after", 0.0)
                                - state.get("coverage_before", 0.0), 2),
        "adopted_tests": state.get("adopted", 0),
        "discarded_tests": state.get("discarded", 0),
        "attempts": state.get("attempt", 0),
        "mutation": {"total": state.get("mutants_total", 0),
                     "killed": state.get("mutants_killed", 0)},
        "confirmed_bugs": confirmed,
        "gate_passed": state.get("gate_passed", False),
        "generated_tests": state.get("generated_test_code", ""),
    }
    out = {**state, "report": report}
    rp = state.get("report_path")
    if rp:
        Path(rp).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        out["report_path"] = rp
    return out
