"""Tests for SWARAJ Benchmark Harness."""

import yaml  # type: ignore[import-untyped]
from eval.bench import evaluate_task_response, run_benchmark

from models.registry import ModelRegistry


def test_evaluate_task_response_evaluators():
    """Test programmatic graders for code_exec, keyword_match, etc."""
    # 1. code_exec evaluator
    task_code = {
        "id": "t1",
        "evaluator": "code_exec",
        "test_code": "assert add(2, 3) == 5",
    }
    resp_pass = "Here is Python code:\n```python\ndef add(a, b):\n    return a + b\n```"
    resp_fail = "Here is Python code:\n```python\ndef add(a, b):\n    return a - b\n```"
    assert evaluate_task_response(task_code, resp_pass) is True
    assert evaluate_task_response(task_code, resp_fail) is False

    # 2. keyword_match evaluator
    task_kw = {
        "id": "t2",
        "evaluator": "keyword_match",
        "required_keywords": ["oisd-118", "hydrotested"],
    }
    assert evaluate_task_response(task_kw, "Unit was hydrotested per OISD-118 standard.") is True
    assert evaluate_task_response(task_kw, "Unit was hydrotested.") is False

    # 3. numeric_tolerance evaluator
    task_num = {
        "id": "t3",
        "evaluator": "numeric_tolerance",
        "expected_value": 12.5,
        "tolerance": 0.05,
    }
    assert evaluate_task_response(task_num, "The calculated wall thickness is 12.48 mm.") is True
    assert evaluate_task_response(task_num, "The calculated wall thickness is 5.0 mm.") is False

    # 4. section_check evaluator
    task_sec = {
        "id": "t4",
        "evaluator": "section_check",
        "required_sections": ["subject", "recommendation"],
    }
    approval_text = "SUBJECT: Procurement\nRECOMMENDATION: Approve."
    assert evaluate_task_response(task_sec, approval_text) is True
    assert evaluate_task_response(task_sec, "SUBJECT: Procurement") is False


def test_run_benchmark_dry_run():
    """Test running benchmark suite in dry run mode."""
    res = run_benchmark("qwen3-coder:30b", dry_run=True)

    assert "priors" in res
    assert "metadata" in res
    assert res["metadata"]["suite"] == "eval suite v1"
    assert res["priors"]["code_generate"] >= 0.80


def test_models_yaml_priors_update(tmp_path):
    """Test updating priors and metadata in models.yaml."""
    yaml_file = tmp_path / "models.yaml"
    yaml_file.write_text("roles:\n  coder: ['qwen3-coder:30b']\noverrides: {}\n", encoding="utf-8")

    priors = {"code_generate": 0.94, "code_debug": 0.98}
    metadata = {"gpu": "NVIDIA RTX 4090", "date": "2026-09-06", "suite": "eval suite v1"}

    with open(yaml_file, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    data["priors"] = {"qwen3-coder:30b": priors}
    data["bench_metadata"] = metadata

    with open(yaml_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f)

    registry = ModelRegistry(yaml_file)
    assert registry._priors["qwen3-coder:30b"]["code_generate"] == 0.94
