"""MCP 服务封装：把本 Agent 暴露为一个工具，供 Codex / Claude 等通用 Agent 调用。

定位：通用 Agent 会"写测试"，但不做变异验证与量化门禁；本工具补的正是"测试
是否真的有效 + 是否发现源码 bug"的可信度后端。人工审核的疑点通过返回值交回给
上层 Agent，由它在对话中转达用户，无需自建对话界面。

依赖 mcp 官方 SDK（pip install mcp）。未安装时给出明确提示，不静默降级。
"""
from __future__ import annotations

from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # 结构化失败，不伪装成功
    raise SystemExit(
        "未安装 MCP SDK，请先执行: pip install mcp\n"
        f"底层错误: {exc}"
    )

from langgraph.types import Command

from .graph import build_graph

mcp = FastMCP("testgen-agent")


@mcp.tool()
def generate_verified_tests(
    source_path: str,
    test_path: str,
    coverage_target: float = 80.0,
    max_attempts: int = 3,
    on_suspected_bug: str = "confirm_bug",
) -> dict[str, Any]:
    """为指定源文件生成并验证单元测试，返回覆盖率、变异与疑似 bug 的量化报告。

    参数:
        source_path: 被测源文件，形如 <root>/<pkg>/<file>.py。
        test_path: 种子测试文件路径。
        coverage_target: 覆盖率门禁（百分比）。
        max_attempts: 最大自我修正轮数。
        on_suspected_bug: 变异验证判定疑似源码 bug 时的处理，
            confirm_bug=标记为真实 bug 上报 / ignore=当作测试期望有误。

    返回:
        report 字典：覆盖率变化、采纳/丢弃数、迭代轮数、变异杀伤、确认的 bug、门禁结果。
    """
    app = build_graph()
    cfg = {"configurable": {"thread_id": f"mcp-{source_path}"}}
    init = {"source_path": source_path, "test_path": test_path,
            "test_command": "pytest", "coverage_target": coverage_target,
            "max_attempts": max_attempts}
    result = app.invoke(init, cfg)
    # 由上层 Agent 决定疑似 bug 的处理（此处按参数默认策略续跑）
    while "__interrupt__" in result:
        result = app.invoke(Command(resume=on_suspected_bug), cfg)
    return result["report"]


def main() -> None:
    """以 stdio 传输启动 MCP server。"""
    mcp.run()


if __name__ == "__main__":
    main()
