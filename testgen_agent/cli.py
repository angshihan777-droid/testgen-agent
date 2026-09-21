"""命令行入口：驱动 Agent 图，处理人工审核暂停，打印量化报告。

用法：
    python -m testgen_agent.cli run --source examples/src/calc.py \
        --test examples/tests/test_calc.py --target 80

无 OPENAI_API_KEY 时自动使用内置启发式生成器，闭环照常运行。
"""
from __future__ import annotations

import argparse
import sys

from langgraph.types import Command

from .graph import build_graph


def _print_report(rep: dict) -> None:
    line = "-" * 52
    print(line)
    print(f" 源文件      {rep['source']}")
    print(f" 覆盖率      {rep['coverage_before']}%  ->  {rep['coverage_after']}%  "
          f"({rep['coverage_delta']:+})")
    print(f" 采纳/丢弃   {rep['adopted_tests']}  /  {rep['discarded_tests']}")
    print(f" 迭代轮数    {rep['attempts']}")
    print(f" 变异杀伤    {rep['mutation']['killed']}/{rep['mutation']['total']}")
    print(f" 确认真bug   {len(rep['confirmed_bugs'])}")
    for b in rep["confirmed_bugs"]:
        print(f"    - {b['nodeid']}: {b['message']}")
    print(f" 门禁        {'PASS' if rep['gate_passed'] else 'FAIL'}")
    print(line)


def _ask_human(payload: dict) -> str:
    """在终端就疑似 bug 询问用户，返回 confirm_bug / ignore。"""
    print("\n[human-in-loop] 发现疑似源码 bug，暂停等待确认")
    print(f"  用例   {payload.get('nodeid')}")
    print(f"  信息   {payload.get('message')}")
    print(f"  证据   {payload.get('evidence')}")
    ans = input("  [k] 确认是bug  [i] 忽略  > ").strip().lower()
    return "confirm_bug" if ans == "k" else "ignore"


def run(args: argparse.Namespace) -> int:
    """执行一次完整的测试生成 + 验证流程。"""
    app = build_graph()
    config = {"configurable": {"thread_id": "cli-run"}}
    init = {
        "source_path": args.source,
        "test_path": args.test,
        "test_command": args.cmd,
        "coverage_target": args.target,
        "max_attempts": args.max_attempts,
    }
    auto = args.assume  # 非交互模式下对疑似 bug 的默认处理

    result = app.invoke(init, config=config)
    # 处理可能的多次人工审核暂停
    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        decision = auto if auto else _ask_human(payload)
        result = app.invoke(Command(resume=decision), config=config)

    _print_report(result["report"])
    return 0 if result["report"]["gate_passed"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="testgen-agent")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="生成并验证单元测试")
    r.add_argument("--source", required=True, help="被测源文件路径")
    r.add_argument("--test", required=True, help="种子测试文件路径")
    r.add_argument("--cmd", default="pytest", help="测试命令（记录用）")
    r.add_argument("--target", type=float, default=80.0, help="覆盖率门禁(%)")
    r.add_argument("--max-attempts", dest="max_attempts", type=int, default=3)
    r.add_argument("--assume", choices=["confirm_bug", "ignore"], default=None,
                   help="非交互模式下对疑似 bug 的默认处理")
    args = parser.parse_args(argv)
    if args.command == "run":
        return run(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
