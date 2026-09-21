"""analyze / mutate 的单元测试：确定性逻辑，不依赖模型或子进程。"""
import ast

from testgen_agent.analyze import analyze
from testgen_agent import mutate


def test_analyze_extracts_functions(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    f = src / "m.py"
    f.write_text("def add(a, b):\n    if a > b:\n        return a\n    return b\n",
                 encoding="utf-8")
    state = analyze({"source_path": str(f)})
    names = [x["name"] for x in state["functions"]]
    assert "add" in names
    assert state["source_hash"]
    assert any("compare" in h for x in state["functions"] for h in x["branch_hints"])


def test_mutate_swaps_operator():
    code = "def f(x):\n    return x < 10\n"
    assert mutate._count_mutation_points(code) == 1
    mutant, desc = mutate.make_mutant(code, 0)
    assert "<=" in mutant
    assert "Lt->LtE" in desc
