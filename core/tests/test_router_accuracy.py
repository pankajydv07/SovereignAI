"""Unit and Accuracy Tests for SWARAJ Two-Stage Model Router."""

import json
import time
from pathlib import Path

import pytest

from models.registry import ModelRegistry
from models.router import ModelRouter, TaskClass


def load_dataset(filename: str) -> list[dict]:
    """Load JSONL dataset from eval directory."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    file_path = root_dir / "eval" / filename
    if not file_path.exists():
        pytest.fail(f"Dataset file not found at {file_path}")

    items = []
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items


def test_heldout_accuracy_and_confusion_matrix():
    """Test accuracy strictly on non-overlapping held-out dataset and print confusion matrix."""
    train_items = load_dataset("routing_trainset.jsonl")
    test_items = load_dataset("routing_testset.jsonl")

    registry = ModelRegistry()
    router = ModelRouter(registry)
    router.train_classifier(train_items)

    correct_count = 0
    total_count = len(test_items)

    classes = [c.value for c in TaskClass]
    matrix: dict[str, dict[str, int]] = {
        actual: {pred: 0 for pred in classes} for actual in classes
    }

    for item in test_items:
        prompt = item["prompt"]
        has_image = item.get("has_image", False)
        mime_types = item.get("mime_types", [])
        expected = item["expected_class"]

        decision = router.route(prompt, has_image=has_image, mime_types=mime_types)
        predicted = decision.task_class

        matrix[expected][predicted] += 1
        if predicted == expected:
            correct_count += 1

    overall_accuracy = correct_count / total_count

    print("\n=======================================================")
    print(f"ROUTER ACCURACY ON HELDOUT TESTSET ({total_count} items): {overall_accuracy:.4f}")
    print("=======================================================")

    # Per-Class Precision, Recall, F1
    print("\nPER-CLASS METRICS:")
    print(f"{'Task Class':<20} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10}")
    print("-" * 60)

    for cls in classes:
        tp = matrix[cls][cls]
        fp = sum(matrix[other][cls] for other in classes if other != cls)
        fn = sum(matrix[cls][other] for other in classes if other != cls)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        print(f"{cls:<20} | {precision:<10.4f} | {recall:<10.4f} | {f1:<10.4f}")

    print("\nCONFUSION MATRIX (Rows: Actual, Cols: Predicted):")
    print(f"{'Actual \\ Pred':<18} | " + " | ".join(f"{c[:4]:<4}" for c in classes))
    print("-" * 75)
    for actual in classes:
        row_str = " | ".join(f"{matrix[actual][pred]:<4}" for pred in classes)
        print(f"{actual:<18} | {row_str}")

    assert overall_accuracy >= 0.95, (
        f"Router accuracy {overall_accuracy:.4f} is below SLA target of 0.95"
    )


def test_full_routing_latency_sla():
    """Test full 5-stage routing latency assertion p95 < 50ms across 1000 calls."""
    train_items = load_dataset("routing_trainset.jsonl")
    registry = ModelRegistry()
    router = ModelRouter(registry)
    router.train_classifier(train_items)

    sample_prompts = [
        "Calculate minimum required wall thickness for 10-inch pipe at 35 bar per ASME B31.3.",
        "Debug KeyError: 'vram_usage' in telemetry logger script.",
        "Draft an approval note for DGM Mech seeking sanction for INR 4.5 Lakhs.",
        "Run OCR on this scanned handwritten inspection report photo.",
        "Summarise the quarterly maintenance report for crude distillation unit.",
    ]

    latencies_ms: list[float] = []

    # Benchmark 1000 routing calls
    for i in range(1000):
        prompt = sample_prompts[i % len(sample_prompts)]
        has_img = "ocr" in prompt.lower()

        t0 = time.perf_counter()
        _decision = router.route(prompt, has_image=has_img)
        t_elapsed = (time.perf_counter() - t0) * 1000.0

        latencies_ms.append(t_elapsed)

    latencies_ms.sort()
    p95_latency = latencies_ms[int(0.95 * len(latencies_ms))]
    p99_latency = latencies_ms[int(0.99 * len(latencies_ms))]
    mean_latency = sum(latencies_ms) / len(latencies_ms)

    print("\nROUTER LATENCY SLA BENCHMARK (1000 calls):")
    print(f"Mean: {mean_latency:.2f} ms | p95: {p95_latency:.2f} ms | p99: {p99_latency:.2f} ms")

    assert p95_latency < 50.0, (
        f"Router p95 latency {p95_latency:.2f}ms exceeds SLA limit of 50.0ms"
    )


def test_normalized_scoring_superior_cold_model_wins(tmp_path):
    """Test that a non-resident high-quality model can win over a resident low-quality model."""
    config_file = tmp_path / "models.yaml"
    config_file.write_text(
        "roles:\n"
        "  coder:\n"
        "    - low-quality-resident:7b\n"
        "    - high-quality-cold:30b\n"
        "overrides:\n"
        "  low-quality-resident:7b:\n"
        "    quality_prior: 0.30\n"
        "  high-quality-cold:30b:\n"
        "    quality_prior: 0.95\n"
        "routing:\n"
        "  weights:\n"
        "    w1_quality: 0.60\n"
        "    w2_vram_fit: 0.10\n"
        "    w3_latency: 0.10\n"
        "    w4_swap_penalty: 0.20\n",
        encoding="utf-8",
    )

    registry = ModelRegistry(config_file)
    router = ModelRouter(registry, weights=registry.get_overrides("routing").get("weights"))

    # Resident model set contains low-quality-resident:7b
    resident_tags = {"low-quality-resident:7b"}

    decision = router.route(
        "/code write a python script",
        resident_tags=resident_tags,
    )

    # High quality model (0.95) wins over resident low quality (0.30)
    high_score = decision.scoring_breakdown["high-quality-cold:30b"]["total_score"]
    low_score = decision.scoring_breakdown["low-quality-resident:7b"]["total_score"]

    assert decision.selected_model_tag == "high-quality-cold:30b"
    assert high_score > low_score


def test_missing_capability_degraded_status(tmp_path):
    """Test routing when required model capability is missing per PRD FR-2.8."""
    config_file = tmp_path / "models.yaml"
    config_file.write_text(
        "roles:\n  vision: ['missing-vision-tag:latest']\noverrides: {}\n", encoding="utf-8"
    )

    registry = ModelRegistry(config_file)
    router = ModelRouter(registry)

    # Only coder model is installed, vision model is missing
    installed_tags = {"qwen2.5-coder:32b"}

    decision = router.route(
        "Run OCR on this scanned inspection photo",
        has_image=True,
        installed_tags=installed_tags,
    )

    assert decision.task_class == TaskClass.VISION_OCR.value
    assert decision.degraded_reason is not None
    assert "ollama pull missing-vision-tag:latest" in decision.degraded_reason
