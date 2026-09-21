"""变异测试：验证生成的测试"是否真的能抓 bug"，并为 bug 归因提供证据。

做法：用 ast 对源码做一处微小改动（比较符/常量/布尔取反），用同一套测试重跑。
- 好的测试应因此变红（"杀死"该变异体）——证明测试真的看住了这行逻辑。
- 若测试仍全绿，说明测试是空壳，未真正覆盖该逻辑。
归因用途：当某条测试在【原始源码】上失败，却在【某个变异体】上通过，说明测试
期望的是变异后的行为——即源码当前实现可能有误，标记为疑似源码 bug。
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

_CMP_SWAP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
             ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}


class _Mutator(ast.NodeTransformer):
    """把第 index 个可变异点替换为其对偶算子。"""

    def __init__(self, index: int):
        self.index = index
        self.count = 0
        self.applied: str | None = None

    def visit_Compare(self, node: ast.Compare):
        self.generic_visit(node)
        for i, op in enumerate(node.ops):
            if type(op) in _CMP_SWAP:
                if self.count == self.index:
                    new = _CMP_SWAP[type(op)]()
                    self.applied = f"{type(op).__name__}->{type(new).__name__} @L{node.lineno}"
                    node.ops[i] = new
                self.count += 1
        return node


def _count_mutation_points(code: str) -> int:
    tree = ast.parse(code)
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            n += sum(1 for op in node.ops if type(op) in _CMP_SWAP)
    return n


def make_mutant(code: str, index: int) -> tuple[str, str | None]:
    """生成第 index 个变异体源码，返回 (变异源码, 说明)。"""
    tree = ast.parse(code)
    mut = _Mutator(index)
    new_tree = mut.visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree), mut.applied


def run_mutation_analysis(root: Path, source_rel: str, source_code: str) -> dict:
    """对源码逐个变异并用现有测试重跑，统计杀伤数并识别疑似 bug。"""
    total = _count_mutation_points(source_code)
    killed = 0
    survived: list[str] = []
    source_file = root / source_rel
    original = source_file.read_text(encoding="utf-8")
    try:
        for i in range(total):
            mutant, desc = make_mutant(source_code, i)
            source_file.write_text(mutant, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
                cwd=root, capture_output=True, text=True, timeout=300,
            )
            if proc.returncode != 0:
                killed += 1  # 测试变红 = 杀死变异体
            else:
                survived.append(desc or f"mutant#{i}")
    finally:
        source_file.write_text(original, encoding="utf-8")
    return {"total": total, "killed": killed, "survived": survived}
