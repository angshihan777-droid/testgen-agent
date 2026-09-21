"""④ run_tests 节点：用 subprocess 跑真实 pytest，解析结构化事实。

"检测报错"不是模型能力，而是 pytest + coverage 这两个成熟工具跑出的结果：
退出码给出通过/失败，json 报告给出每条失败堆栈，coverage.json 给出覆盖率。
本节点只负责如实读取这些事实。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .state import RunResult


def _parse_coverage(root: Path) -> float:
    """读取 coverage.json，返回总覆盖率百分比。"""
    cov_file = root / "coverage.json"
    if not cov_file.exists():
        return 0.0
    data = json.loads(cov_file.read_text(encoding="utf-8"))
    return round(data["totals"]["percent_covered"], 2)


def _parse_report(root: Path) -> tuple[int, int, list[dict]]:
    """读取 pytest json 报告，返回 (passed, failed, failures)。"""
    rep = root / "report.json"
    if not rep.exists():
        return 0, 0, []
    data = json.loads(rep.read_text(encoding="utf-8"))
    passed = failed = 0
    failures: list[dict] = []
    for t in data.get("tests", []):
        if t.get("outcome") == "passed":
            passed += 1
        elif t.get("outcome") == "failed":
            failed += 1
            call = t.get("call", {}) or {}
            failures.append({
                "nodeid": t.get("nodeid"),
                "message": (call.get("crash", {}) or {}).get("message", ""),
                "traceback": (call.get("longrepr", "") or "")[:2000],
            })
    return passed, failed, failures


def run_pytest(root: Path, cov_pkg: str) -> RunResult:
    """在 root 目录运行 pytest（带 json 报告 + 覆盖率），解析为 RunResult。"""
    pkg = cov_pkg
    cmd = [
        sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider",
        f"--cov={pkg}", "--cov-report=json",
        "--json-report", "--json-report-file=report.json",
    ]
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=300)
    passed, failed, failures = _parse_report(root)
    return RunResult(
        returncode=proc.returncode,
        passed=passed,
        failed=failed,
        failures=failures,
        coverage=_parse_coverage(root),
    )
