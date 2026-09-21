"""Agent 全程共享的状态定义。

State 是一个 TypedDict，在 LangGraph 各节点之间流转。每个节点读取需要的
字段、写回新的字段，条件边据此决定是继续循环还是收敛产出报告。
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class FunctionInfo(TypedDict):
    """analyze 节点从源码中提取的单个函数信息。"""

    name: str
    args: list[str]
    lineno: int
    branch_hints: list[str]


class RunResult(TypedDict):
    """run_tests 节点解析 pytest 后的结构化事实。"""

    returncode: int
    passed: int
    failed: int
    failures: list[dict[str, Any]]
    coverage: float


class AgentState(TypedDict, total=False):
    """在 6 个节点之间流转的共享状态。

    total=False 允许节点按需写入部分字段，未写入的字段保持缺省。
    """

    # 输入
    source_path: str
    test_path: str
    test_command: str
    coverage_target: float
    max_attempts: int

    # analyze 产出
    source_code: str
    source_hash: str
    functions: list[FunctionInfo]
    uncovered_baseline: float

    # 循环状态
    attempt: int
    generated_test_code: str
    last_run: Optional[RunResult]
    coverage_before: float
    coverage_after: float

    # evaluate 产出
    adopted: int
    discarded: int
    suspected_bugs: list[dict[str, Any]]
    mutation: dict[str, Any]
    source_tampered: bool
    mutants_total: int
    mutants_killed: int
    gate_passed: bool
    decision: str  # "retry" | "done"

    # 人工审核
    pending_review: Optional[dict[str, Any]]
    review_decisions: list[dict[str, Any]]

    # 产出
    report: dict[str, Any]
    report_path: str
