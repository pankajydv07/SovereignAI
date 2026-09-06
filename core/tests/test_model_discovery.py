"""Tests for SWARAJ Model Capability Auto-Discovery and Role Fulfilment."""

from unittest.mock import AsyncMock

import pytest

from models.discovery import ModelDiscoverer
from models.ollama import OllamaClient, OllamaUnreachableError
from models.registry import ModelNotInstalledError, ModelRegistry, Role


@pytest.mark.asyncio
async def test_parse_capabilities_authoritative_gguf():
    """Test parse_capabilities using authoritative GGUF metadata fields."""
    mock_ollama = AsyncMock(spec=OllamaClient)
    discoverer = ModelDiscoverer(mock_ollama)

    show_data = {
        "details": {
            "parameter_size": "32B",
            "quantization_level": "Q4_K_M",
            "family": "qwen2",
        },
        "capabilities": ["vision", "thinking", "tools"],
        "model_info": {
            "qwen2.context_length": 32768,
            "vision.block_count": 32,
        },
        "template": "{{ .System }}\n<think>\n{{ .Prompt }}\n</think>",
    }

    info = discoverer.parse_capabilities("qwen2.5-coder:32b", "sha256:abc12345", show_data)

    assert info.tag == "qwen2.5-coder:32b"
    assert info.digest == "sha256:abc12345"
    assert info.parameter_size == "32B"
    assert info.quantization_level == "Q4_K_M"
    assert info.context_length == 32768
    assert info.supports_vision is True
    assert info.supports_thinking is True
    assert info.supports_tools is True
    assert info.family == "qwen2"


@pytest.mark.asyncio
async def test_parse_capabilities_heuristic_fallback_logging(caplog):
    """Test that falling back to heuristics logs warning messages."""
    mock_ollama = AsyncMock(spec=OllamaClient)
    discoverer = ModelDiscoverer(mock_ollama)

    # Show data with NO capabilities list or explicit model_info capabilities
    show_data = {
        "details": {
            "parameter_size": "7B",
            "quantization_level": "Q4_K_M",
            "family": "llama",
        },
        "model_info": {},
        "template": "Hello {{ .Prompt }}",
    }

    with caplog.at_level("WARNING"):
        info = discoverer.parse_capabilities("deepseek-r1-vl:latest", "sha256:def678", show_data)

    assert info.context_length == 4096  # Default fallback
    assert info.supports_vision is True  # From 'vl' in tag
    assert info.supports_thinking is True  # From 'deepseek' in tag

    # Verify log warnings were generated
    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("context_length_absent" in r.message for r in warning_records)
    assert any("capability_heuristic_fallback" in r.message for r in warning_records)


@pytest.mark.asyncio
async def test_discover_all_caching():
    """Test that ModelDiscoverer caches results by (tag, digest)."""
    mock_ollama = AsyncMock(spec=OllamaClient)
    mock_ollama.get_installed_models_full.return_value = [
        {"name": "qwen2.5-coder:32b", "digest": "sha256:abc"},
    ]
    mock_ollama.show_model.return_value = {
        "details": {"parameter_size": "32B", "quantization_level": "Q4_K_M"},
        "capabilities": ["tools"],
        "model_info": {"coder.context_length": 16384},
    }

    discoverer = ModelDiscoverer(mock_ollama)

    # First call - fetches show_model
    res1 = await discoverer.discover_all()
    assert len(res1) == 1
    assert res1[0].context_length == 16384
    assert mock_ollama.show_model.call_count == 1

    # Second call - same tag and digest - uses cache
    res2 = await discoverer.discover_all()
    assert len(res2) == 1
    assert res2[0].context_length == 16384
    assert mock_ollama.show_model.call_count == 1  # Not incremented


@pytest.mark.asyncio
async def test_model_not_installed_error(tmp_path):
    """Test that validating missing model tags raises ModelNotInstalledError."""
    config_file = tmp_path / "models.yaml"
    config_file.write_text(
        "roles:\n  coder: ['qwen2.5-coder:300b']\noverrides: {}\n", encoding="utf-8"
    )

    registry = ModelRegistry(config_file)
    installed_tags = {"qwen2.5-coder:32b", "llama3:latest"}

    # Resolving role returns configured candidate tag
    tag = registry.resolve(Role.CODER)
    assert tag == "qwen2.5-coder:300b"

    # Pre-flight validation fails loud with ModelNotInstalledError
    with pytest.raises(ModelNotInstalledError) as exc_info:
        registry.validate_models(installed_tags)

    assert exc_info.value.role == "coder"
    assert exc_info.value.tag == "qwen2.5-coder:300b"
    assert "ollama pull qwen2.5-coder:300b" in str(exc_info.value)


def test_num_ctx_clamping(tmp_path):
    """Test num_ctx calculation = min(discovered_max, yaml_override)."""
    config_file = tmp_path / "models.yaml"
    yaml_content = (
        "roles:\n  coder: ['qwen2.5-coder:32b']\n"
        "overrides:\n  qwen2.5-coder:32b:\n    num_ctx: 16384\n"
    )
    config_file.write_text(yaml_content, encoding="utf-8")

    registry = ModelRegistry(config_file)

    # When discovered_max (32768) > yaml_ctx (16384), take 16384
    assert registry.get_num_ctx("qwen2.5-coder:32b", discovered_max=32768) == 16384

    # When discovered_max (8192) < yaml_ctx (16384), take 8192
    assert registry.get_num_ctx("qwen2.5-coder:32b", discovered_max=8192) == 8192

    # When discovered_max is None, use yaml_ctx
    assert registry.get_num_ctx("qwen2.5-coder:32b", discovered_max=None) == 16384


def test_role_fulfilment_status_vram_and_ram(tmp_path):
    """Test get_role_fulfilment_status separates VRAM and distinguishes missing/resident states."""
    config_file = tmp_path / "models.yaml"
    config_file.write_text(
        "roles:\n"
        "  coder: ['qwen2.5-coder:32b']\n"
        "  planner: ['qwen2.5:32b']\n"
        "  vision: ['missing-vision-model:latest']\n",
        encoding="utf-8",
    )

    registry = ModelRegistry(config_file)
    installed_tags = {"qwen2.5-coder:32b", "qwen2.5:32b"}
    running_models = [
        {
            "name": "qwen2.5-coder:32b",
            "size": 20 * 1024 * 1024 * 1024,  # 20 GB total RAM
            "size_vram": 18 * 1024 * 1024 * 1024,  # 18 GB VRAM
        }
    ]

    status = registry.get_role_fulfilment_status(installed_tags, running_models)

    status_map = {item["role"]: item for item in status}

    # Coder is installed and resident
    assert status_map["coder"]["satisfied"] is True
    assert status_map["coder"]["residency"] == "RESIDENT"
    assert status_map["coder"]["vramUsage"] == "18432.0 MB"

    # Planner is installed but not resident (unloaded)
    assert status_map["planner"]["satisfied"] is True
    assert status_map["planner"]["residency"] == "UNLOADED"
    assert status_map["planner"]["vramUsage"] == "0 MB"

    # Vision is not installed (missing)
    assert status_map["vision"]["satisfied"] is False
    assert status_map["vision"]["residency"] == "MISSING"
    assert "ollama pull missing-vision-model:latest" in status_map["vision"]["consequence"]


@pytest.mark.asyncio
async def test_ollama_unreachable_error():
    """Test that connection failure in OllamaClient raises OllamaUnreachableError."""
    client = OllamaClient(base_url="http://127.0.0.1:1")  # Invalid port

    with pytest.raises(OllamaUnreachableError):
        await client.get_installed_tags()
