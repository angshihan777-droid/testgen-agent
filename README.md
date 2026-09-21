# testgen-agent

一个**自动写 / 修单元测试**的代码质量 Agent。它读代码、生成 pytest 测试、在沙盒里真实运行、根据结果自我修正，并用**变异测试**验证生成的测试是否真的有效、是否发现了源码里的真实 bug。

它不是"能写测试"的又一个套壳——市面上通用 Agent（Codex、Claude）都会写测试。它补的是通用 Agent **不做**的那一层：**测试有效性验证 + 量化质量门禁 + 源码 bug 归因**。因此它天然适合被包装成 **MCP 工具**，作为通用 Agent 的"测试质量后端"被调用。

## 它凭什么算 Agent，而不是自动化测试脚本

| | 自动化测试脚本 / CI | testgen-agent |
|---|---|---|
| 谁写测试 | 人写好，它只跑 | Agent 自己写 |
| 测试挂了 | 报错停下，等人改 | 读真实报错，自己修，再跑 |
| 何时停止 | 跑完一次即停 | 自己判断达标没有，没达标继续循环 |
| 有无决策 | 无，固定流程 | 有：`evaluate` 节点决定 retry / review / done |

核心区别在于闭环里有**感知结果 → 决策 → 再行动**的自主循环，且能在关键时刻（疑似源码 bug）主动暂停找人确认。

## 核心设计原则

- **报错不是模型"感觉"出来的**：由 `pytest` + `coverage` 这两个成熟工具跑出结构化事实（退出码、失败堆栈、覆盖率），Agent 只负责如实读取并据此决策。
- **"是不是 bug"不靠模型拍脑袋**：靠变异测试这一确定性信号——把源码做一处微小改动（如 `<` 改 `<=`），若某条测试因此从红转绿，说明它描述的是"改动后"的行为，即当前源码实现可能有误。
- **防作弊**：源码在沙盒里只读，运行前后做哈希校验，杜绝 Agent 偷改源码让测试变绿。
- **知道何时找人**：只有"疑似源码 bug"这类高价值疑点才触发人工审核，不逢事就打扰。

## 运作流程（LangGraph 6 节点自主循环）

```
                    +-----------------------------------------------+
                    |            State（全程共享的状态字典）          |
                    |  source_code / functions / source_hash        |
                    |  generated_test_code / last_run / mutation    |
                    |  coverage_before / coverage_after             |
                    |  attempt / suspected_bugs / review_decisions  |
                    +-----------------------------------------------+

  [START]
     |
     v
 +--------------+
 | (1) analyze  |  ast 解析源码：提取函数签名、分支提示、源码哈希
 +------+-------+
        |  产出"考纲"（该覆盖哪些分支）+ 防篡改用的 hash
        v
 +--------------+
 | (2) generate |  LLM 按源码+考纲+上轮失败 写/修测试         <----------+
 +------+-------+  （无 API key 时用内置确定性启发式生成器）             |
        |                                                                |
        v                                                                |
 +--------------+                                                        |
 | (3)(4)       |  sandbox：复刻项目、源码设只读、写入测试               |
 |   execute    |  run   ：subprocess 跑真实 pytest --cov，读退出码/覆盖率|
 |              |  mutate：逐个变异源码重跑，统计杀伤 + 收集 bug 证据    |
 +------+-------+                                                        |
        |  产出结构化事实：last_run / mutation / source_tampered         |
        v                                                                |
 +--------------+                                                        |
 | (5) evaluate |  防作弊校验 + 覆盖率门禁 + 失败归因                     |
 +------+-------+                                                        |
        |                                                                |
        v                                                                |
   < decision 路由 >                                                     |
    |-- retry  --> 回 (2) generate，带着失败堆栈重写 --------------------+
    |
    |-- review --> +--------------+   interrupt 暂停，把疑似 bug 交给人
    |              | (H) review   |   人选 confirm_bug / ignore 后
    |              +------+-------+   Command(resume=...) 从断点续跑
    |                     |          回到 (5) evaluate 复判
    |                     +--------> (5) evaluate
    |
    |-- done   --> +--------------+
                   | (6) report   |  汇总量化指标 + 生成报告
                   +------+-------+
                          |
                       [END]
```

条件边 `evaluate -> generate` 就是"循环"的来源，也是它作为 Agent 的本质。人工审核用 LangGraph 的 `interrupt` 实现，依赖 checkpointer 支持断点续跑。

## 每个节点做什么、为什么技术上成立

| 节点 | 输入 | 做的事 | 为什么能实现 |
|---|---|---|---|
| **① analyze** | 源文件 | `ast.parse` 提取函数签名、if/循环/比较分支，算源码哈希 | `ast` 是标准库，语法树遍历是确定性的，无需模型 |
| **② generate** | 源码 + 分支考纲 + 上轮失败堆栈 | 调 LLM 写/修测试；无密钥时用启发式生成器 | tool-calling；报错来自真实运行，模型据此修正而非猜 |
| **③ sandbox** | 源码 + 生成的测试 | 临时目录复刻项目，源码只读，运行前后哈希校验 | 文件系统隔离 + `hashlib` 防止偷改源码作弊 |
| **④ run_tests** | 沙盒目录 | `subprocess` 跑 `pytest --cov`，解析退出码/失败堆栈/覆盖率 | pytest + coverage 产出结构化事实，程序读事实 |
| **⑤ evaluate** | 运行结果 + 变异结果 | 门禁判定 + 失败归因（测试写错 vs 源码 bug） | 变异测试给确定性信号，判定是纯 `if` 逻辑 |
| **⑥ report** | 全程指标 | 汇总覆盖率变化/采纳丢弃/变异杀伤/确认 bug | 指标全部来自真实运行，非估算 |

## 快速开始

```bash
pip install -r requirements.txt
pip install -e .

# 对内置示例（含一个真实 bug）跑一遍，非交互模式自动确认疑似 bug
python -m testgen_agent.cli run \
    --source examples/src/calc.py \
    --test examples/tests/test_calc.py \
    --target 80 --assume confirm_bug
```

> 设置 `OPENAI_API_KEY` 后自动改用真实模型生成测试；未设置时使用内置确定性启发式生成器，闭环照常运行、可复现。

### 运行示例输出

```text
----------------------------------------------------
 源文件      examples/src/calc.py
 覆盖率      66.67%  ->  88.89%  (+22.22)
 采纳/丢弃   3  /  0
 迭代轮数    1
 变异杀伤    3/4
 确认真bug   1
    - tests/test_generated.py::test_bound_in_range: assert False is True (in_range(10,1,10) 上界漏判)
 门禁        PASS
----------------------------------------------------
```

## 人工审核（human-in-the-loop）

只有当变异验证判定"疑似源码 bug"时，图才会通过 `interrupt` 暂停，把疑点交给人：

```text
[human-in-loop] 发现疑似源码 bug，暂停等待确认
  用例   tests/test_generated.py::test_bound_in_range
  信息   assert False is True (in_range(10,1,10))
  证据   断言失败且变异验证显示测试描述了正确行为
  [k] 确认是bug  [i] 忽略  >
```

- 选 `k`（confirm_bug）：标记为真实 bug 上报，保留该测试。
- 选 `i`（ignore）：当作测试期望有误，丢弃。

普通失败（如测试自身 `ImportError`/`SyntaxError`）不会打扰人，直接丢弃重写。

## 作为 MCP 工具供 Codex / Claude 调用

```bash
pip install mcp
python -m testgen_agent.mcp_server
```

暴露的工具 `generate_verified_tests(source_path, test_path, coverage_target, ...)` 返回同一份量化报告。定位是通用 Agent 的**测试质量后端**：通用 Agent 负责"决定测哪个文件"，本工具负责"把测试写对、验证有效、抓出 bug"。疑似 bug 的疑点通过返回值交回上层 Agent，由它在对话中转达用户——无需自建对话界面。

## 项目结构

```
testgen_agent/
  analyze.py     ① ast 静态分析
  generate.py    ② 生成/修正测试（LLM 或启发式）
  sandbox.py     ③ 沙盒隔离 + 防篡改哈希校验
  runner.py      ④ 跑 pytest，解析结构化结果
  mutate.py      变异测试：验证测试有效性 + bug 归因证据
  execute.py     ③④ 组合节点：沙盒→运行→变异
  evaluate.py    ⑤ 门禁判定 + 失败归因（纯函数，可在审核后重入）
  review.py      人工审核（interrupt）
  report.py      ⑥ 汇总量化报告
  graph.py       LangGraph 组装 6 节点自主循环
  cli.py         命令行入口
  mcp_server.py  MCP 工具封装
examples/        含一个内置真实 bug 的示例项目
tests/           本项目自身的单元与端到端测试
```

## 测试

```bash
pytest tests -q            # 全部（含端到端）
pytest tests -m "not slow" # 仅快速单元测试
```

## 设计边界与后续

当前 MVP 聚焦单文件、Python、比较类变异算子，命令行运行。已规划但未纳入 MVP：多语言、Docker 级沙盒、更多变异算子、Web 可视化报告。这些不影响核心闭环的可量化与可复现。

## License

MIT
