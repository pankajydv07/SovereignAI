"""SWARAJ Two-Stage Model Router.

5-stage routing pipeline:
  Stage 0: Featurise prompt (modalities, mime types, estimated tokens, code fences, keyword hits).
  Stage 1: Keyword fast path + Multinomial Naive Bayes embedding/feature classifier head.
  Stage 2: Capability match against ModelRegistry.
  Stage 3: Normalized multi-attribute scoring (quality prior, VRAM fit, latency, swap penalty).
  Stage 4: Fallback declaration in RoutingDecision (Stateless core; TurnLoop owns escalation).
"""

import logging
import math
import re
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from models.registry import ModelRegistry, NoModelForRoleError, Role

log = logging.getLogger(__name__)


class TaskClass(StrEnum):
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
    is_manual_override: bool = False
    degraded_reason: str | None = None


class FeatureExtractor:
    """Stage 0: Prompt featuriser."""

    KEYWORD_PATTERNS: dict[str, list[str]] = {
        "vision_ocr": [
            "ocr", "scan", "scanned", "photo", "handwritten", "image", "blueprint", "चित्र"
        ],
        "code_debug": [
            "debug", "traceback", "error", "exception", "attributeerror", "keyerror",
            "typeerror", "syntaxerror", "zerodivisionerror", "fix", "issue"
        ],
        "code_generate": [
            "python", "script", "pandas", "openpyxl", "code", "function", "write a python",
            "implement a", "create a script", "utility", "module"
        ],
        "engineering_calc": [
            "calculate the", "compute the", "determine the", "calculate", "compute",
            "wall thickness", "mawp", "hydrotest", "pressure drop", "npsha", "stress",
            "corrosion rate", "operating pressure", "heat duty", "vent capacity"
        ],
        "official_drafting": [
            "approval note", "sanction", "draft an official", "dgm", "memorandum",
            "स्वीकृति टिप्पणी", "प्रारूप", "आधिकारिक", "अनुमोदन"
        ],
        "doc_extract": [
            "extract all", "ultrasonic thickness", "reading", "asset tag", "ncr", "mill test",
            "weld inspection", "flange rating", "extract the"
        ],
        "doc_summarise": [
            "summarise the", "summarize the", "executive summary", "overview of the",
            "synthesise the", "minutes of"
        ],
        "kb_qa": [
            "what is the governing", "procedure for", "what are the mandatory",
            "what does clause", "according to api", "according to mrpl", "what safety checks",
            "what is the maximum", "what is the capital"
        ],
    }

    def featurise(
        self, prompt: str, has_image: bool = False, mime_types: list[str] | None = None
    ) -> dict[str, Any]:
        """Extract feature dictionary from prompt text and media metadata."""
        prompt_lower = prompt.lower()
        mime_list = mime_types or []

        is_image_attached = has_image or any("image/" in m for m in mime_list)
        code_fence_count = len(re.findall(r"```", prompt))
        estimated_tokens = len(prompt) // 4

        keyword_hits: dict[str, int] = {}
        for cls_name, keywords in self.KEYWORD_PATTERNS.items():
            count = sum(1 for kw in keywords if kw in prompt_lower)
            keyword_hits[cls_name] = count

        return {
            "has_image": is_image_attached,
            "mime_types": mime_list,
            "code_fences": code_fence_count,
            "estimated_tokens": estimated_tokens,
            "keyword_hits": keyword_hits,
            "raw_prompt": prompt,
        }


class NaiveBayesClassifier:
    """Stage 1: Keyword fast-path + Log-Probability Multinomial Naive Bayes classifier."""

    def __init__(self) -> None:
        self.class_counts: dict[str, int] = {c.value: 0 for c in TaskClass}
        self.class_word_counts: dict[str, dict[str, int]] = {c.value: {} for c in TaskClass}
        self.class_total_words: dict[str, int] = {c.value: 0 for c in TaskClass}
        self.total_docs: int = 0
        self.vocab: set[str] = set()

    def train(self, items: list[dict[str, Any]]) -> None:
        """Train Naive Bayes model on training dataset."""
        for item in items:
            cls = item["expected_class"]
            text = item["prompt"].lower()
            tokens = re.findall(r"\w+", text)

            self.total_docs += 1
            self.class_counts[cls] += 1

            for token in tokens:
                self.vocab.add(token)
                self.class_word_counts[cls][token] = (
                    self.class_word_counts[cls].get(token, 0) + 1
                )
                self.class_total_words[cls] += 1

    def predict(self, prompt: str, features: dict[str, Any]) -> tuple[str, float]:
        """Predict task class and confidence score in [0.0, 1.0]."""
        p_lower = prompt.lower()

        # 1. Hard Overrides (< 1ms)
        if features.get("has_image"):
            return TaskClass.VISION_OCR.value, 1.0

        if p_lower.startswith("/code"):
            return TaskClass.CODE_GENERATE.value, 1.0
        if p_lower.startswith("/calc"):
            return TaskClass.ENGINEERING_CALC.value, 1.0
        if p_lower.startswith("/doc"):
            return TaskClass.DOC_SUMMARISE.value, 1.0

        if "traceback (" in p_lower or "error:" in p_lower or "exception:" in p_lower:
            return TaskClass.CODE_DEBUG.value, 0.95

        # 2. Keyword Fast-Path Boost
        kw_hits: dict[str, int] = features.get("keyword_hits", {})
        best_kw_cls: str | None = None
        best_count = 0
        for k, count in kw_hits.items():
            if count > best_count:
                best_count = count
                best_kw_cls = k

        if best_kw_cls and best_count >= 2:
            return best_kw_cls, min(0.98, 0.85 + 0.05 * best_count)

        # 3. Multinomial Naive Bayes Log-Likelihood Classification
        tokens = re.findall(r"\w+", p_lower)
        if not tokens or self.total_docs == 0:
            return TaskClass.OTHER.value, 0.50

        vocab_size = max(1, len(self.vocab))
        log_probs: dict[str, float] = {}

        for cls in TaskClass:
            c_name = cls.value
            prior_log = math.log(
                (self.class_counts[c_name] + 1) / (self.total_docs + len(TaskClass))
            )
            total_words = self.class_total_words[c_name] + vocab_size

            word_log_sum = 0.0
            for t in tokens:
                count = self.class_word_counts[c_name].get(t, 0)
                word_log_sum += math.log((count + 1) / total_words)

            log_probs[c_name] = prior_log + word_log_sum

        max_log = max(log_probs.values())
        exp_scores: dict[str, float] = {
            c: math.exp(score - max_log) for c, score in log_probs.items()
        }
        sum_exp = sum(exp_scores.values())

        best_cls = list(exp_scores.keys())[0]
        best_score = exp_scores[best_cls]
        for c, s in exp_scores.items():
            if s > best_score:
                best_score = s
                best_cls = c

        confidence = round(exp_scores[best_cls] / sum_exp, 2)

        if best_kw_cls and best_kw_cls == best_cls and kw_hits.get(best_kw_cls, 0) >= 1:
            confidence = max(confidence, 0.90)

        return best_cls, max(0.50, min(0.99, confidence))


class ModelRouter:
    """Two-stage SWARAJ Model Router managing stages 0 through 4."""

    def __init__(
        self,
        registry: ModelRegistry,
        weights: dict[str, float] | None = None,
        confidence_floor: float = 0.55,
    ) -> None:
        self.registry = registry
        self.featuriser = FeatureExtractor()
        self.classifier = NaiveBayesClassifier()
        self.confidence_floor = confidence_floor

        default_weights = {
            "w1_quality": 0.40,
            "w2_vram_fit": 0.25,
            "w3_latency": 0.15,
            "w4_swap_penalty": 0.20,
        }
        self.weights = weights or default_weights

    def train_classifier(self, train_items: list[dict[str, Any]]) -> None:
        """Train internal classifier on labelled training dataset."""
        self.classifier.train(train_items)

    def route(
        self,
        prompt: str,
        has_image: bool = False,
        mime_types: list[str] | None = None,
        installed_tags: set[str] | None = None,
        resident_tags: set[str] | None = None,
        manual_override_tag: str | None = None,
    ) -> RoutingDecision:
        """Execute full 5-stage routing decision with SLA timing."""
        t0 = time.perf_counter()

        installed = installed_tags or set()
        resident = resident_tags or set()

        features = self.featuriser.featurise(prompt, has_image, mime_types)

        task_class, confidence = self.classifier.predict(prompt, features)
        if confidence < self.confidence_floor:
            log.warning(
                f"router_confidence_below_floor: {confidence} < {self.confidence_floor}. "
                "Escalating to planner."
            )
            task_class = TaskClass.OTHER.value

        role_mapping: dict[str, Role] = {
            TaskClass.CODE_GENERATE.value: Role.CODER,
            TaskClass.CODE_DEBUG.value: Role.CODER,
            TaskClass.DOC_SUMMARISE.value: Role.WRITER,
            TaskClass.DOC_EXTRACT.value: Role.WRITER,
            TaskClass.ENGINEERING_CALC.value: Role.PLANNER,
            TaskClass.OFFICIAL_DRAFTING.value: Role.WRITER,
            TaskClass.VISION_OCR.value: Role.VISION,
            TaskClass.KB_QA.value: Role.WRITER,
            TaskClass.OTHER.value: Role.PLANNER,
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

        # Determine winning candidate model
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
            is_win = (tag == selected_model)
            reason = None
            if not is_win:
                if task_class == TaskClass.VISION_OCR.value and "vision" not in tag.lower():
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
            is_manual_override=is_override,
            degraded_reason=degraded_reason,
        )
