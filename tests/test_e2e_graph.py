"""端到端：在真实沙盒里跑完整图，验证覆盖率提升与 bug 归因、人工审核续跑。"""
import os

import pytest

from langgraph.types import Command
from testgen_agent.graph import build_graph

EX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")


@pytest.mark.slow
def test_full_loop_catches_bug_and_improves_coverage():
    app = build_graph()
    cfg = {"configurable": {"thread_id": "t-e2e"}}
    init = {"source_path": os.path.join("examples", "src", "calc.py"),
            "test_path": os.path.join("examples", "tests", "test_calc.py"),
            "test_command": "pytest", "coverage_target": 80.0, "max_attempts": 3}
    # 从仓库根运行以匹配相对路径
    os.chdir(os.path.dirname(EX))
    result = app.invoke(init, cfg)

    saw_interrupt = False
    while "__interrupt__" in result:
        saw_interrupt = True
        payload = result["__interrupt__"][0].value
        assert payload["type"] == "suspected_source_bug"
        result = app.invoke(Command(resume="confirm_bug"), cfg)

    rep = result["report"]
    assert saw_interrupt, "应因内置 bug 触发人工审核"
    assert rep["coverage_after"] > rep["coverage_before"]
    assert len(rep["confirmed_bugs"]) == 1
    assert rep["mutation"]["total"] >= 1
