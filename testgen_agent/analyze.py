"""① analyze 节点：用标准库 ast 对源码做确定性静态分析。

不依赖任何模型或算法：ast.parse 把源码变成语法树，遍历即可拿到函数签名、
分支提示与函数指纹。产出用于给 generate 节点当"考纲"，并记录源码哈希以便
sandbox 节点做防篡改校验。
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from .state import AgentState, FunctionInfo


def _branch_hints(node: ast.FunctionDef) -> list[str]:
    """收集函数体内的分支/比较提示，提示 generate 需要覆盖哪些路径。"""
    hints: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.If):
            hints.append(f"if @L{sub.lineno}")
        elif isinstance(sub, ast.Compare):
            ops = [type(op).__name__ for op in sub.ops]
            hints.append(f"compare({','.join(ops)}) @L{sub.lineno}")
        elif isinstance(sub, (ast.For, ast.While)):
            hints.append(f"loop @L{sub.lineno}")
    return hints


def analyze(state: AgentState) -> AgentState:
    """读取源码，提取函数信息与源码哈希，写回 state。"""
    source_path = Path(state["source_path"])
    code = source_path.read_text(encoding="utf-8")
    tree = ast.parse(code)

    functions: list[FunctionInfo] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            functions.append(
                FunctionInfo(
                    name=node.name,
                    args=[a.arg for a in node.args.args],
                    lineno=node.lineno,
                    branch_hints=_branch_hints(node),
                )
            )

    return {
        **state,
        "source_code": code,
        "source_hash": hashlib.sha256(code.encode("utf-8")).hexdigest(),
        "functions": functions,
        "attempt": 0,
        "adopted": 0,
        "discarded": 0,
        "suspected_bugs": [],
        "review_decisions": [],
        "mutants_total": 0,
        "mutants_killed": 0,
    }
