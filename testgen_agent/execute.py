"""③④ execute 节点：沙盒隔离 + 运行 pytest + 变异分析，产出确定性事实。

把"生成的测试"落进临时沙盒（源码只读、哈希留证），运行真实 pytest 得到通过/
失败与覆盖率，再做变异分析。只把结构化事实写回 state，随后 evaluate 据此决策。
沙盒在本节点内创建并清理，不跨节点持有，以便 evaluate 可在人工审核后纯粹重入。
"""
from __future__ import annotations

from pathlib import Path

from . import mutate
from .runner import run_pytest
from .sandbox import cleanup, prepare_baseline, prepare_workspace, verify_source_untouched
from .state import AgentState


def execute(state: AgentState) -> AgentState:
    """在沙盒中运行测试与变异分析，写回 last_run / mutation / source_tampered。"""
    sandbox = prepare_workspace(state)
    try:
        run = run_pytest(Path(sandbox["root"]), sandbox["cov_pkg"])
        tampered = not verify_source_untouched(sandbox)
        mut = mutate.run_mutation_analysis(
            Path(sandbox["root"]), sandbox["source_rel"], state["source_code"])
    finally:
        cleanup(sandbox)

    cov_before = state.get("coverage_before")
    if cov_before is None:
        base_sb = prepare_baseline(state)
        try:
            base_run = run_pytest(Path(base_sb["root"]), base_sb["cov_pkg"])
            cov_before = base_run["coverage"]
        finally:
            cleanup(base_sb)
    return {**state, "last_run": run, "mutation": mut,
            "source_tampered": tampered, "coverage_before": cov_before}
