"""testgen-agent: 自动写/修单测并验证其有效性的代码质量 Agent。

以 LangGraph 编排一个自主循环：分析源码 -> 生成测试 -> 沙盒隔离 ->
运行 pytest -> 评估与变异归因 -> (必要时人工确认) -> 循环或产出报告。
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
