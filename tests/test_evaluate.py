"""evaluate 节点决策逻辑的单元测试：纯函数，构造 state 直接断言决策。"""
from testgen_agent.evaluate import evaluate, _classify


def _base(**kw):
    s = {"attempt": 1, "max_attempts": 3, "coverage_target": 80.0,
         "last_run": {"returncode": 0, "passed": 3, "failed": 0,
                      "failures": [], "coverage": 90.0},
         "mutation": {"total": 4, "killed": 4, "survived": []},
         "source_tampered": False, "review_decisions": [], "suspected_bugs": []}
    s.update(kw)
    return s


def test_gate_pass_when_coverage_met():
    out = evaluate(_base())
    assert out["decision"] == "done"
    assert out["gate_passed"] is True


def test_tampered_source_forces_retry():
    out = evaluate(_base(source_tampered=True))
    assert out["decision"] == "retry"
    assert out["gate_passed"] is False


def test_low_coverage_retries():
    run = {"returncode": 0, "passed": 1, "failed": 0, "failures": [], "coverage": 50.0}
    out = evaluate(_base(last_run=run))
    assert out["decision"] == "retry"


def test_assertion_failure_with_surviving_mutant_flags_bug():
    run = {"returncode": 1, "passed": 2, "failed": 1, "coverage": 90.0,
           "failures": [{"nodeid": "t::x", "message": "assert False",
                         "traceback": "AssertionError"}]}
    mut = {"total": 4, "killed": 3, "survived": ["Lt->LtE @L3"]}
    out = evaluate(_base(last_run=run, mutation=mut))
    assert out["decision"] == "review"
    assert out["pending_review"]["nodeid"] == "t::x"


def test_test_error_is_discarded_not_flagged():
    run = {"returncode": 1, "passed": 1, "failed": 1, "coverage": 90.0,
           "failures": [{"nodeid": "t::y", "message": "boom",
                         "traceback": "ImportError: no module"}]}
    out = evaluate(_base(last_run=run))
    assert out["decision"] == "retry"
    assert out["discarded"] == 1
    assert out["suspected_bugs"] == []


def test_classify():
    assert _classify({"traceback": "SyntaxError: bad"}) == "test_error"
    assert _classify({"traceback": "AssertionError"}) == "assertion"
