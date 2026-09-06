"""SWARAJ Model Capability Auto-Discovery and GGUF Metadata Inspector."""

import logging
from dataclasses import dataclass
from typing import Any

from models.ollama import OllamaClient

log = logging.getLogger(__name__)


@dataclass
class DiscoveredModelInfo:
    """Discovered capability metadata for an installed model."""

    tag: str
    digest: str
    parameter_size: str
    quantization_level: str
    context_length: int
    supports_vision: bool
    supports_thinking: bool
    supports_tools: bool
    family: str


class ModelDiscoverer:
    """Auto-discovers installed models, inspects GGUF metadata, and caches capabilities."""

    DEFAULT_CONTEXT_LENGTH: int = 4096

    def __init__(self, ollama_client: OllamaClient) -> None:
        self.ollama = ollama_client
        # Cache keyed by (tag, digest)
        self._cache: dict[tuple[str, str], DiscoveredModelInfo] = {}

    def parse_capabilities(
        self, tag: str, digest: str, show_data: dict[str, Any]
    ) -> DiscoveredModelInfo:
        """Extract authoritative GGUF capabilities from POST /api/show response.

        Prefers authoritative GGUF metadata (`capabilities`, `model_info`, `template`).
        Falls back to heuristics with explicit warning logging.
        """
        details = show_data.get("details", {})
        model_info = show_data.get("model_info", {})
        template = show_data.get("template", "")
        capabilities_list = show_data.get("capabilities", details.get("capabilities", []))

        parameter_size = details.get("parameter_size", "Unknown")
        quantization_level = details.get("quantization_level", "Unknown")
        family = details.get("family", "")

        # 1. Context Length Extraction
        discovered_ctx = None
        for k, v in model_info.items():
            if k.endswith(".context_length") and isinstance(v, int):
                discovered_ctx = v
                break

        if discovered_ctx is None:
            log.warning(
                f"context_length_absent: Model '{tag}' model_info lacks *.context_length. "
                f"Defaulting to {self.DEFAULT_CONTEXT_LENGTH}."
            )
            discovered_ctx = self.DEFAULT_CONTEXT_LENGTH

        # 2. Vision Capability Detection
        supports_vision = False
        if "vision" in capabilities_list or any(
            "vision" in k or "clip" in k for k in model_info
        ):
            supports_vision = True
        elif "vl" in tag.lower() or "vision" in tag.lower() or "vision" in family.lower():
            log.warning(
                f"capability_heuristic_fallback: 'vision' capability for '{tag}' "
                "detected via tag/family heuristic."
            )
            supports_vision = True

        # 3. Thinking Capability Detection
        supports_thinking = False
        if "thinking" in capabilities_list or "<think>" in template:
            supports_thinking = True
        elif "think" in tag.lower() or "deepseek" in tag.lower():
            log.warning(
                f"capability_heuristic_fallback: 'thinking' capability for '{tag}' "
                "detected via tag heuristic."
            )
            supports_thinking = True

        # 4. Tool Calling Capability Detection
        supports_tools = False
        if "tools" in capabilities_list or ".Tools" in template or "[AVAILABLE_TOOLS]" in template:
            supports_tools = True
        elif "tools" in template.lower() or "tool" in tag.lower() or "coder" in tag.lower():
            log.warning(
                f"capability_heuristic_fallback: 'tools' capability for '{tag}' "
                "detected via template/tag heuristic."
            )
            supports_tools = True

        return DiscoveredModelInfo(
            tag=tag,
            digest=digest,
            parameter_size=parameter_size,
            quantization_level=quantization_level,
            context_length=discovered_ctx,
            supports_vision=supports_vision,
            supports_thinking=supports_thinking,
            supports_tools=supports_tools,
            family=family,
        )

    async def discover_all(self) -> list[DiscoveredModelInfo]:
        """Query installed models via GET /api/tags and inspect details via POST /api/show."""
        models_data = await self.ollama.get_installed_models_full()
        discovered: list[DiscoveredModelInfo] = []

        for m in models_data:
            tag = m.get("name") or m.get("model")
            digest = m.get("digest", "")
            if not tag:
                continue

            cache_key = (tag, digest)
            if cache_key in self._cache:
                discovered.append(self._cache[cache_key])
                continue

            try:
                show_data = await self.ollama.show_model(tag)
                info = self.parse_capabilities(tag, digest, show_data)
                self._cache[cache_key] = info
                discovered.append(info)
            except Exception as exc:
                log.warning(f"failed_to_inspect_model_capabilities: '{tag}': {exc}")

        return discovered
