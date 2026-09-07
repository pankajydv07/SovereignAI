"""Unit and Accuracy Tests for SWARAJ Embedding-Centroid Model Router."""

import json
from pathlib import Path
import time
from unittest.mock import AsyncMock

import numpy as np
import pytest

from kb.embedder import ChunkEmbedder, EmbeddingModelUnavailable
from models.registry import ModelRegistry, NoAvailableModelForRole
from models.router import (
    ClassifierNotInitialisedError,
    EmbeddingCentroidClassifier,
    ModelRouter,
    REAL_TASK_CLASSES,
    TaskClass,
)


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


def load_test_embeddings() -> dict[str, list[float]]:
    """Load cached nomic-embed-text embeddings from test fixture."""
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "router_test_embeddings.json"
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


def create_fixture_embedder(embeddings: dict[str, list[float]]) -> AsyncMock:
    """Create a mock ChunkEmbedder backed by real cached nomic-embed-text embeddings."""
    mock = AsyncMock(spec=ChunkEmbedder)
    mock.model = "nomic-embed-text:latest"
    mock.ollama_url = "http://127.0.0.1:11434"

    async def _embed_single(text: str) -> np.ndarray:
        if text in embeddings:
            return np.array(embeddings[text], dtype=np.float32)
        # Fallback to first vector if prompt unknown in mock test
        first_vec = next(iter(embeddings.values()))
        return np.array(first_vec, dtype=np.float32)

    mock.embed_single_text.side_effect = _embed_single
    return mock


@pytest.mark.asyncio
async def test_zero_keyword_paraphrase_routing():
    """Verify router accuracy on zero-keyword paraphrases using nomic-embed-text centroids."""
    registry = ModelRegistry()
    fixture_embeds = load_test_embeddings()
    mock_embedder = create_fixture_embedder(fixture_embeds)
    router = ModelRouter(registry, embedder=mock_embedder)

    paraphrase_cases = [
        ("create an executive brief", TaskClass.DOC_SUMMARISE),
        ("boil this down into a one-pager", TaskClass.DOC_SUMMARISE),
        ("generate a concise memo of the findings", TaskClass.DOC_SUMMARISE),
        ("give me a high-level walkthrough of the audit", TaskClass.DOC_SUMMARISE),
        ("write a python script to parse csv", TaskClass.CODE_GENERATE),
        ("why did this fail with NullPointerException", TaskClass.CODE_DEBUG),
        ("determine the pipe wall thickness under 50 bar", TaskClass.ENGINEERING_CALC),
        ("draft a formal sanction note for the CGM", TaskClass.OFFICIAL_DRAFTING),
        ("create a management review deck", TaskClass.OFFICIAL_DRAFTING),
        ("make slides from this report", TaskClass.OFFICIAL_DRAFTING),
        ("generate a PPTX presentation", TaskClass.OFFICIAL_DRAFTING),
        ("pull out all flange ratings from table 4", TaskClass.DOC_EXTRACT),
        ("what is the mandatory safety clearance under OISD 118", TaskClass.KB_QA),
    ]

    for prompt, expected_class in paraphrase_cases:
        decision = await router.route(prompt)
        assert decision.task_class == expected_class, (
            f"Expected {expected_class} for '{prompt}', got {decision.task_class} (conf={decision.confidence:.3f})"
        )
        assert decision.confidence_band in ("CONFIDENT", "UNCERTAIN")


@pytest.mark.asyncio
async def test_uninitialised_classifier_raises(tmp_path):
    """Verify ClassifierNotInitialisedError is raised for missing or corrupt centroids file."""
    registry = ModelRegistry()

    # 1. Non-existent file
    missing_file = tmp_path / "does_not_exist.json"
    with pytest.raises(ClassifierNotInitialisedError, match="not found"):
        ModelRouter(registry, centroids_path=missing_file)

    # 2. Corrupt JSON
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("NOT_VALID_JSON{[[", encoding="utf-8")
    with pytest.raises(ClassifierNotInitialisedError, match="corrupt or unreadable"):
        ModelRouter(registry, centroids_path=corrupt_file)

    # 3. Missing a required real task class
    incomplete_file = tmp_path / "incomplete.json"
    incomplete_data = {
        "centroids": {
            "code_generate": [0.1] * 768,
            # Missing other 7 classes
        }
    }
    incomplete_file.write_text(json.dumps(incomplete_data), encoding="utf-8")
    with pytest.raises(ClassifierNotInitialisedError, match="Centroid missing for required task class"):
        ModelRouter(registry, centroids_path=incomplete_file)


@pytest.mark.asyncio
async def test_startup_self_test_distinguishes_errors(tmp_path):
    """Startup self-test distinguishes missing centroids from unreachable Ollama."""
    registry = ModelRegistry()

    # Case A: Ollama connection failure raises EmbeddingModelUnavailable
    mock_failing_embedder = AsyncMock(spec=ChunkEmbedder)
    mock_failing_embedder.model = "nomic-embed-text:latest"
    mock_failing_embedder.ollama_url = "http://127.0.0.1:11434"
    mock_failing_embedder.embed_single_text.side_effect = EmbeddingModelUnavailable(
        model="nomic-embed-text:latest",
        endpoint="http://127.0.0.1:11434/api/embed",
        details="Connection refused",
    )

    router_failing_ollama = ModelRouter(registry, embedder=mock_failing_embedder)
    with pytest.raises(EmbeddingModelUnavailable, match="Connection refused"):
        await router_failing_ollama.self_test()

    # Case B: Working router self-test passes
    working_router = ModelRouter(registry)
    await working_router.self_test()


@pytest.mark.asyncio
async def test_single_embedding_reuse():
    """Verify route() returns prompt_embedding and hard overrides skip embedding."""
    registry = ModelRegistry()
    router = ModelRouter(registry)

    # Hard override: no embedding generated
    decision_override = await router.route("/calc MAWP for 12 inch pipe")
    assert decision_override.task_class == TaskClass.ENGINEERING_CALC
    assert decision_override.prompt_embedding is None
    assert decision_override.confidence == 1.0

    # Natural language prompt: prompt_embedding generated and returned
    decision_embed = await router.route("What are the mandatory OISD safety clearances?")
    assert decision_embed.prompt_embedding is not None
    assert len(decision_embed.prompt_embedding) == 768
    assert decision_embed.task_class == TaskClass.KB_QA


@pytest.mark.asyncio
async def test_full_routing_latency_sla():
    """Test routing latency SLA for hard overrides and warm embeddings."""
    registry = ModelRegistry()
    router = ModelRouter(registry)

    sample_prompts = [
        "/calc Calculate minimum required wall thickness for 10-inch pipe.",
        "Debug KeyError: 'vram_usage' in telemetry logger script.",
        "/doc Draft an approval note for DGM Mech.",
        "Run OCR on this scanned handwritten inspection report photo.",
        "/code write a python script to parse CSV data",
    ]

    latencies_ms: list[float] = []

    for i in range(100):
        prompt = sample_prompts[i % len(sample_prompts)]
        has_img = "ocr" in prompt.lower()

        t0 = time.perf_counter()
        _decision = await router.route(prompt, has_image=has_img)
        t_elapsed = (time.perf_counter() - t0) * 1000.0

        latencies_ms.append(t_elapsed)

    latencies_ms.sort()
    p95_latency = latencies_ms[int(0.95 * len(latencies_ms))]
    p99_latency = latencies_ms[int(0.99 * len(latencies_ms))]
    mean_latency = sum(latencies_ms) / len(latencies_ms)

    print("\nROUTER HARD-OVERRIDE LATENCY BENCHMARK (100 calls):")
    print(f"Mean: {mean_latency:.2f} ms | p95: {p95_latency:.2f} ms | p99: {p99_latency:.2f} ms")

    assert p95_latency < 50.0, (
        f"Router p95 latency {p95_latency:.2f}ms exceeds SLA limit of 50.0ms"
    )


@pytest.mark.asyncio
async def test_normalized_scoring_superior_cold_model_wins(tmp_path):
    """Test that a non-resident high-quality model can win over a resident low-quality model."""
    config_file = tmp_path / "models.yaml"
    config_file.write_text(
        "roles:\n"
        "  embedder:\n"
        "    - nomic-embed-text:latest\n"
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

    resident_tags = {"low-quality-resident:7b"}

    decision = await router.route(
        "/code write a python script",
        resident_tags=resident_tags,
    )

    high_score = decision.scoring_breakdown["high-quality-cold:30b"]["total_score"]
    low_score = decision.scoring_breakdown["low-quality-resident:7b"]["total_score"]

    assert decision.selected_model_tag == "high-quality-cold:30b"
    assert high_score > low_score


@pytest.mark.asyncio
async def test_missing_capability_degraded_status(tmp_path):
    """Test routing when required model capability is missing per PRD FR-2.8."""
    config_file = tmp_path / "models.yaml"
    config_file.write_text(
        "roles:\n"
        "  embedder:\n"
        "    - nomic-embed-text:latest\n"
        "  vision:\n"
        "    - missing-vision-tag:latest\n"
        "overrides: {}\n",
        encoding="utf-8",
    )

    registry = ModelRegistry(config_file)
    router = ModelRouter(registry)

    installed_tags = {"qwen2.5-coder:32b"}

    decision = await router.route(
        "Run OCR on this scanned inspection photo",
        has_image=True,
        installed_tags=installed_tags,
    )

    assert decision.task_class == TaskClass.VISION_OCR
    assert decision.degraded_reason is not None
    assert "ollama pull missing-vision-tag:latest" in decision.degraded_reason


def test_no_available_model_for_role_raises(tmp_path):
    """Assert NoAvailableModelForRole is raised when role has no candidate and no silent substitution occurs."""
    config_file = tmp_path / "models.yaml"
    config_file.write_text(
        "roles:\n"
        "  embedder:\n"
        "    - nomic-embed-text:latest\n"
        "overrides: {}\n",
        encoding="utf-8",
    )
    registry = ModelRegistry(config_file)
    with pytest.raises(NoAvailableModelForRole) as exc_info:
        registry.get_primary("vision")

    assert exc_info.value.role == "vision"
    assert "No model available for role 'vision'" in str(exc_info.value)
    # Ensure nothing was silently substituted and resolve also fails loudly
    with pytest.raises(NoAvailableModelForRole):
        registry.resolve("vision")

