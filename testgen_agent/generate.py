"""② generate 节点：根据源码 + 分支考纲 + 上一轮失败，产出/修正测试代码。

有真实模型时走 LLM；否则走确定性启发式生成器（冒烟 + 边界探针），保证闭环
在无密钥环境也能真实运行、真实提升覆盖率。生成逻辑与模型是否可用解耦。
"""
from __future__ import annotations

from pathlib import Path

from . import llm
from .state import AgentState


def _build_prompt(state: AgentState) -> str:
    """把源码、考纲、上轮失败拼成生成 prompt。"""
    parts = [
        "为下面的 Python 模块编写 pytest 测试，尽量覆盖每个分支与边界值。",
        "要求：断言具体返回值，不要用 assert True；覆盖闭区间上下界等边界。",
        f"\n# 源码({state['source_path']})\n```python\n{state['source_code']}```",
    ]
    hints = [f"- {f['name']}({', '.join(f['args'])}): {'; '.join(f['branch_hints']) or '无分支'}"
             for f in state.get("functions", [])]
    if hints:
        parts.append("\n# 需覆盖的函数与分支\n" + "\n".join(hints))
    last = state.get("last_run")
    if last and last.get("failures"):
        ftxt = "\n".join(f"- {x.get('nodeid')}: {x.get('message')}" for x in last["failures"])
        parts.append("\n# 上一轮失败（据此修正测试，若疑似源码 bug 请保留断言）\n" + ftxt)
    return "\n".join(parts)


def _module_import_path(state: AgentState) -> str:
    """推断沙盒内被测模块的 import 名。

    沙盒以 <root> 为根（含 <pkg>/ 与 tests/），故取 source_path 末两段：
    examples/src/calc.py -> src.calc。
    """
    p = Path(state["source_path"]).with_suffix("")
    parts = p.parts[-2:]
    return ".".join(parts)


def _heuristic_tests(state: AgentState) -> str:
    """无模型时的确定性生成：对每个函数做冒烟调用 + 数值边界探针。"""
    mod = _module_import_path(state)
    names = [f["name"] for f in state.get("functions", [])]
    lines = [
        "import sys, os",
        "sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))",
        f"from {mod} import {', '.join(names)}" if names else "",
        "",
    ]
    for f in state.get("functions", []):
        argc = len(f["args"])
        call = ", ".join(["1"] * argc)
        lines.append(f"def test_smoke_{f['name']}():")
        lines.append(f"    {f['name']}({call})")
        lines.append("")
        if any("compare" in h for h in f["branch_hints"]) and argc >= 3:
            lines.append(f"def test_bound_{f['name']}():")
            lines.append(f"    # 边界探针：闭区间上界应被包含")
            lines.append(f"    assert {f['name']}(10, 1, 10) is True")
            lines.append("")
    return "\n".join(lines)


def generate(state: AgentState) -> AgentState:
    """产出本轮测试代码，写回 generated_test_code，并把轮次 +1。"""
    if llm.llm_available():
        code = llm.generate_tests_llm(_build_prompt(state))
    else:
        code = _heuristic_tests(state)
    return {**state, "generated_test_code": code, "attempt": state.get("attempt", 0) + 1}
