"""LLM 调用封装。

优先使用 OpenAI（设置 OPENAI_API_KEY 时）。未配置密钥时降级为一个确定性的
启发式生成器，保证项目在离线/无密钥环境下也能完整跑通闭环并被测试覆盖。
降级是结构化、可观察的，不把"未就绪"伪装为真实模型输出。
"""
from __future__ import annotations

import os
import re
from typing import Optional


class LLMUnavailable(RuntimeError):
    """真实模型不可用且未允许降级时抛出。"""


def _extract_code(text: str) -> str:
    """从模型回复中取出 python 代码块；无围栏时原样返回。"""
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def generate_tests_llm(prompt: str, model: Optional[str] = None) -> str:
    """调用 OpenAI 生成测试代码，返回纯 python 文本。"""
    from openai import OpenAI

    client = OpenAI()
    model = model or os.getenv("TESTGEN_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是资深测试工程师，只输出 pytest 测试代码。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return _extract_code(resp.choices[0].message.content or "")


def llm_available() -> bool:
    """是否配置了可用的真实模型。"""
    return bool(os.getenv("OPENAI_API_KEY"))
