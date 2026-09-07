"""SWARAJ Embedding-Centroid Model Router."""

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import time
from typing import Any

import numpy as np

from kb.embedder import ChunkEmbedder, EmbeddingModelUnavailable
from models.registry import ModelRegistry, NoModelForRoleError, Role

log = logging.getLogger(__name__)

REAL_TASK_CLASSES: tuple[str, ...] = (
    "code_generate",
    "code_debug",
    "doc_summarise",
    "doc_extract",
    "engineering_calc",
    "official_drafting",
    "vision_ocr",
    "kb_qa",
)


class ClassifierNotInitialisedError(RuntimeError):
    """Raised when centroid classifier dataset is missing, corrupt, or uninitialised."""


class TaskClass:
    """The 9 SWARAJ task classes."""

    CODE_GENERATE = "code_generate"
    CODE_DEBUG = "code_debug"
    DOC_SUMMARISE = "doc_summarise"
    DOC_EXTRACT = "doc_extract"
    ENGINEERING_CALC = "engineering_calc"
    OFFICIAL_DRAFTING = "official_drafting"
    VISION_OCR = "vision_ocr"
    KB_QA = "kb_qa"
    OTHER = "other"


@dataclass
class CandidateScore:
    """Detailed score breakdown for a model candidate."""

    model_tag: str
    quality_prior: float
    vram_fit: float
    latency_score: float
    swap_penalty: float
    total_score: float
    is_winner: bool
    rejection_reason: str | None = None


@dataclass
class RoutingDecision:
    """Dataclass encapsulating full routing decision and breakdown."""

    task_class: str
    selected_model_tag: str
    fallback_model_tag: str
    confidence: float
    routing_latency_ms: float
    feature_vector: dict[str, Any]
    candidates: list[CandidateScore]
    scoring_breakdown: dict[str, dict[str, float]]
    prompt_embedding: list[float] | None = None
    is_manual_override: bool = False
    degraded_reason: str | None = None


class EmbeddingCentroidClassifier:
    """Stage 1: Nomic-Embed-Text Class Centroid Classifier using Top-1/Top-2 Margin."""

    EXPECTED_DIM: int = 768

    def __init__(self, centroids_path: Path | str | None = None) -> None:
        self.centroids_path = (
            Path(centroids_path) if centroids_path else Path(__file__).parent / "task_centroids.json"
        )
        self.centroids: dict[str, np.ndarray] = {}
        self._load_centroids()

    def _load_centroids(self) -> None:
        if not self.centroids_path.exists():
            raise ClassifierNotInitialisedError(
                f"Task centroids file not found at {self.centroids_path}. "
                "Run centroid generation to initialise."
            )
        try:
            with open(self.centroids_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            raise ClassifierNotInitialisedError(
                f"Task centroids file at {self.centroids_path} is corrupt or unreadable: {exc}"
            ) from exc

        centroids_dict = data.get("centroids")
        if not isinstance(centroids_dict, dict):
            raise ClassifierNotInitialisedError(
                f"Invalid centroids file structure at {self.centroids_path}: 'centroids' dict missing."
            )

        for cls_name in REAL_TASK_CLASSES:
            if cls_name not in centroids_dict:
                raise ClassifierNotInitialisedError(
                    f"Centroid missing for required task class '{cls_name}' in {self.centroids_path}."
                )
            vec = np.array(centroids_dict[cls_name], dtype=np.float32)
            if len(vec) != self.EXPECTED_DIM:
                raise ClassifierNotInitialisedError(
                    f"Centroid dimension mismatch for '{cls_name}': expected {self.EXPECTED_DIM}, got {len(vec)}."
                )
            norm = float(np.linalg.norm(vec))
            if norm == 0.0:
                raise ClassifierNotInitialisedError(f"Centroid for '{cls_name}' has zero norm.")
            self.centroids[cls_name] = vec / norm

    def predict(
        self,
        embedding: list[float],
        margin_floor: float = 0.015,
        min_cosine_floor: float = 0.45,
    ) -> tuple[str, float]:
        """Predict task class and margin confidence from a normalized embedding vector."""
        if not embedding or len(embedding) != self.EXPECTED_DIM:
            return TaskClass.OTHER, 0.0

        q = np.array(embedding, dtype=np.float32)
        q_norm = float(np.linalg.norm(q))
        if q_norm == 0.0:
            return TaskClass.OTHER, 0.0
        q = q / q_norm

        scores: list[tuple[str, float]] = []
        for cls_name, c_vec in self.centroids.items():
            sim = float(np.dot(q, c_vec))
            scores.append((cls_name, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        top1_cls, top1_sim = scores[0]
        top2_cls, top2_sim = scores[1]
        margin = max(0.0, top1_sim - top2_sim)

        if top1_sim < min_cosine_floor or margin < margin_floor:
            log.info(
                f"router_margin_fallback_to_other: top1={top1_cls} (sim={top1_sim:.4f}), "
                f"top2={top2_cls} (sim={top2_sim:.4f}), margin={margin:.4f}"
            )
            return TaskClass.OTHER, round(margin, 4)

        return top1_cls, round(margin, 4)


class ModelRouter:
    """Two-stage SWARAJ Model Router with Hard Overrides and Embedding Centroids."""

    def __init__(
        self,
        registry: ModelRegistry,
        embedder: ChunkEmbedder | None = None,
        centroids_path: Path | str | None = None,
        weights: dict[str, float] | None = None,
        confidence_floor: float = 0.015,
    ) -> None:
        self.registry = registry
        self.embedder = embedder or ChunkEmbedder(model_registry=registry)
        self.classifier = EmbeddingCentroidClassifier(centroids_path=centroids_path)
        self.confidence_floor = confidence_floor

        default_weights = {
            "w1_quality": 0.40,
            "w2_vram_fit": 0.25,
            "w3_latency": 0.15,
            "w4_swap_penalty": 0.20,
        }
        self.weights = weights or default_weights

    async def self_test(self) -> None:
        """Startup self-test distinguishing missing centroids from unreachable Ollama."""
        if len(self.classifier.centroids) != len(REAL_TASK_CLASSES):
            raise ClassifierNotInitialisedError("Classifier is missing required real task classes.")

        canary_vec = await self.embedder.embed_single_text("SWARAJ router startup self-test canary probe")
        if not canary_vec or len(canary_vec) != self.classifier.EXPECTED_DIM:
            raise EmbeddingModelUnavailable(
                model=self.embedder.model,
                endpoint=self.embedder.ollama_url,
                details=f"Canary probe returned invalid vector length: {len(canary_vec)}",
            )

        task_cls, _conf = self.classifier.predict(canary_vec)
        if not task_cls:
            raise ClassifierNotInitialisedError("Centroid prediction pipeline failed on canary embedding.")

    async def route(
        self,
        prompt: str,
        has_image: bool = False,
        mime_types: list[str] | None = None,
        installed_tags: set[str] | None = None,
        resident_tags: set[str] | None = None,
        manual_override_tag: str | None = None,
    ) -> RoutingDecision:
        """Execute routing decision with hard overrides evaluated before embedding."""
        t0 = time.perf_counter()

        installed = installed_tags or set()
        resident = resident_tags or set()
        p_lower = prompt.lower().strip()
        features = {
            "has_image": has_image or any("image/" in (m or "") for m in (mime_types or [])),
            "mime_types": mime_types or [],
            "raw_prompt": prompt,
        }

        task_class: str
        confidence: float
        prompt_embedding: list[float] | None = None

        # Hard Overrides (< 1ms, no embedding round-trip)
        if features["has_image"]:
            task_class, confidence = TaskClass.VISION_OCR, 1.0
        elif p_lower.startswith("/code"):
            task_class, confidence = TaskClass.CODE_GENERATE, 1.0
        elif p_lower.startswith("/calc"):
            task_class, confidence = TaskClass.ENGINEERING_CALC, 1.0
        elif p_lower.startswith("/doc"):
            task_class, confidence = TaskClass.DOC_SUMMARISE, 1.0
        elif "traceback (" in p_lower or "error:" in p_lower or "exception:" in p_lower:
            task_class, confidence = TaskClass.CODE_DEBUG, 0.95
        else:
            # Stage 1: Embed prompt once via ChunkEmbedder
            prompt_embedding = await self.embedder.embed_single_text(prompt)
            task_class, confidence = self.classifier.predict(
                prompt_embedding, margin_floor=self.confidence_floor
            )

        role_mapping: dict[str, Role] = {
            TaskClass.CODE_GENERATE: Role.CODER,
            TaskClass.CODE_DEBUG: Role.CODER,
            TaskClass.DOC_SUMMARISE: Role.WRITER,
            TaskClass.DOC_EXTRACT: Role.WRITER,
            TaskClass.ENGINEERING_CALC: Role.PLANNER,
            TaskClass.OFFICIAL_DRAFTING: Role.WRITER,
            TaskClass.VISION_OCR: Role.VISION,
            TaskClass.KB_QA: Role.WRITER,
            TaskClass.OTHER: Role.PLANNER,
        }
        target_role = role_mapping.get(task_class, Role.PLANNER)

        candidate_tags = self.registry._roles.get(target_role.value, [])
        degraded_reason = None

        if not candidate_tags:
            try:
                candidate_tags = [self.registry.resolve(Role.PLANNER)]
            except NoModelForRoleError:
                candidate_tags = ["qwen3:30b"]

        primary_tag = candidate_tags[0] if candidate_tags else "qwen3:30b"
        if primary_tag not in installed and installed:
            degraded_reason = (
                f"Role '{target_role.value}' model '{primary_tag}' is not installed. "
                f"Run: ollama pull {primary_tag}"
            )

        w1 = self.weights.get("w1_quality", 0.40)
        w2 = self.weights.get("w2_vram_fit", 0.25)
        w3 = self.weights.get("w3_latency", 0.15)
        w4 = self.weights.get("w4_swap_penalty", 0.20)

        candidate_objects: list[CandidateScore] = []
        scoring_breakdown: dict[str, dict[str, float]] = {}

        best_score = -999.0
        best_candidate_tag = primary_tag

        for tag in candidate_tags:
            measured_map = getattr(self.registry, "_priors", {}).get(tag, {})
            if isinstance(measured_map, dict) and task_class in measured_map:
                quality_prior = float(measured_map[task_class])
            else:
                priors_override = self.registry.get_overrides(tag).get("quality_prior", 0.85)
                quality_prior = float(priors_override)
            is_resident = tag in resident
            vram_fit = 1.0 if is_resident or not resident else 0.8
            est_latency_s = 2.0
            latency_score = max(0.0, 1.0 - min(1.0, est_latency_s / 10.0))
            swap_penalty = 0.0 if is_resident else 1.0

            total_score = round(
                w1 * quality_prior + w2 * vram_fit + w3 * latency_score - w4 * swap_penalty, 4
            )

            scoring_breakdown[tag] = {
                "quality_prior": quality_prior,
                "vram_fit": vram_fit,
                "latency_score": latency_score,
                "swap_penalty": swap_penalty,
                "total_score": total_score,
            }

            if total_score > best_score:
                best_score = total_score
                best_candidate_tag = tag

        is_override = manual_override_tag is not None
        selected_model = manual_override_tag or best_candidate_tag

        for tag in candidate_tags:
            is_win = tag == selected_model
            reason = None
            if not is_win:
                if task_class == TaskClass.VISION_OCR and "vision" not in tag.lower():
                    reason = "capability missing: vision"
                elif tag not in resident and resident:
                    reason = "not resident, swap cost 6.1s"
                else:
                    reason = "lower quality prior score"

            cand_score = CandidateScore(
                model_tag=tag,
                quality_prior=scoring_breakdown[tag]["quality_prior"],
                vram_fit=scoring_breakdown[tag]["vram_fit"],
                latency_score=scoring_breakdown[tag]["latency_score"],
                swap_penalty=scoring_breakdown[tag]["swap_penalty"],
                total_score=scoring_breakdown[tag]["total_score"],
                is_winner=is_win,
                rejection_reason=reason,
            )
            candidate_objects.append(cand_score)

        fallback_model = primary_tag
        if len(candidate_tags) > 1:
            fallback_model = candidate_tags[1]
        else:
            try:
                fallback_model = self.registry.resolve(Role.PLANNER)
            except NoModelForRoleError:
                fallback_model = primary_tag

        latency_ms = (time.perf_counter() - t0) * 1000.0

        return RoutingDecision(
            task_class=task_class,
            selected_model_tag=selected_model,
            fallback_model_tag=fallback_model,
            confidence=confidence,
            routing_latency_ms=round(latency_ms, 2),
            feature_vector=features,
            candidates=candidate_objects,
            scoring_breakdown=scoring_breakdown,
            prompt_embedding=prompt_embedding,
            is_manual_override=is_override,
            degraded_reason=degraded_reason,
        )
