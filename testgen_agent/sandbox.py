"""③ sandbox 节点：隔离运行环境并做防篡改准备。

把被测项目复制进临时工作目录、写入本轮生成的测试，并在运行前后用哈希校验源码
未被改动——防止 Agent 通过偷改源码让测试变绿（作弊）。所有用户路径都在临时
目录这一 owning filesystem boundary 内校验，不与宿主路径混用。

约定：source_path 形如 <root>/<pkg>/<file>.py（相对调用时的工作目录），
<root> 是同时包含被测包与 tests/ 的项目根，<pkg> 是覆盖率统计的顶层包名。
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path

from .state import AgentState


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve(state: AgentState) -> tuple[Path, Path, str]:
    """返回 (项目根绝对路径, 源码相对根的路径, 覆盖率顶层包名)。"""
    src_rel = Path(state["source_path"])
    if len(src_rel.parts) < 2:
        raise ValueError("source_path 需形如 <root>/<pkg>/<file>.py")
    root = src_rel.resolve().parents[len(src_rel.parts) - 2]
    rel_to_root = Path(*src_rel.parts[-2:])  # <pkg>/<file>.py
    cov_pkg = src_rel.parts[-2]
    return root, rel_to_root, cov_pkg


def prepare_workspace(state: AgentState) -> dict:
    """在临时目录复刻项目并写入生成测试，返回运行所需路径与元信息。"""
    root, rel_to_root, cov_pkg = _resolve(state)
    workdir = Path(tempfile.mkdtemp(prefix="testgen_"))
    dst_root = workdir / "proj"
    shutil.copytree(root, dst_root)

    gen_dir = dst_root / "tests"
    gen_dir.mkdir(exist_ok=True)
    (gen_dir / "test_generated.py").write_text(
        state["generated_test_code"], encoding="utf-8")

    return {
        "workdir": workdir,
        "root": dst_root,
        "source_rel": str(rel_to_root).replace("\\", "/"),
        "cov_pkg": cov_pkg,
        "source_in_sandbox": dst_root / rel_to_root,
        "source_hash": state["source_hash"],
    }


def prepare_baseline(state: AgentState) -> dict:
    """只复刻项目、不写入生成测试，用于测量基线覆盖率。"""
    root, rel_to_root, cov_pkg = _resolve(state)
    workdir = Path(tempfile.mkdtemp(prefix="testgen_base_"))
    dst_root = workdir / "proj"
    shutil.copytree(root, dst_root)
    return {"workdir": workdir, "root": dst_root,
            "source_rel": str(rel_to_root).replace("\\", "/"), "cov_pkg": cov_pkg}


def verify_source_untouched(sandbox: dict) -> bool:
    """运行后校验源码哈希未变，返回 True 表示未被篡改。"""
    current = _hash(Path(sandbox["source_in_sandbox"]).read_text(encoding="utf-8"))
    return current == sandbox["source_hash"]


def cleanup(sandbox: dict) -> None:
    """删除临时工作目录。"""
    shutil.rmtree(sandbox["workdir"], ignore_errors=True)
