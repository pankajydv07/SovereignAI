"""SWARAJ Structured Planner and Plan Dependency Validation."""

import json

from pydantic import BaseModel, Field

from models.ollama import OllamaClient


from protocol.models import ProtocolBaseModel


class PlanStep(ProtocolBaseModel):
    """Individual plan step model matching ACP meta specifications."""

    step_index: int = Field(alias="stepIndex", description="1-indexed step order number")
    description: str = Field(description="Clear text description of the planned action")
    tool: str = Field(description="Name of the tool to be invoked")
    side_effect: str = Field(
        default="read", alias="sideEffect", description="Side effect classification: read, write, or exec"
    )
    requires_approval: bool = Field(
        default=False,
        alias="requiresApproval",
        description="True if side effect requires permission approval",
    )
    idempotent: bool = Field(
        default=True, description="True if step execution can be safely retried"
    )
    dependencies: list[int] = Field(
        default_factory=list,
        description="List of step_indexes that must complete before this step runs",
    )


class PlanPayload(ProtocolBaseModel):
    """Top-level plan payload emitted via structured JSON Schema output."""

    steps: list[PlanStep]


class Planner:
    """Generates structured execution plans and validates client step dependency edits."""

    def __init__(self, ollama_client: OllamaClient) -> None:
        self.ollama = ollama_client

    async def generate_plan(
        self, prompt: str, model_tag: str, task_class: str = "planner"
    ) -> list[PlanStep]:
        """Generate a structured plan using Ollama format JSON Schema at temperature 0.0."""
        schema_obj = PlanPayload.model_json_schema()
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a structured planner for industrial confidential tasks. "
                    "Analyze prompt and output step-by-step execution plan."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        full_content = ""
        async for chunk in self.ollama.stream_chat(
            model=model_tag,
            messages=messages,
            format=schema_obj,
            options={"temperature": 0.0},
        ):
            full_content += chunk.get("message", {}).get("content", "")

        try:
            data = json.loads(full_content)
            plan_payload = PlanPayload.model_validate(data)
            return plan_payload.steps
        except Exception:
            # Fallback default single step if model emits unparseable plan
            return [
                PlanStep(
                    step_index=1,
                    description=f"Execute prompt task: {prompt[:80]}",
                    tool="fs_read",
                    side_effect="read",
                    requires_approval=False,
                    idempotent=True,
                    dependencies=[],
                )
            ]

    def validate_plan_edits(
        self, original_steps: list[PlanStep], edited_steps: list[PlanStep]
    ) -> list[str]:
        """Validate client plan edits to ensure step dependencies remain valid."""
        warnings: list[str] = []
        edited_indices = {s.step_index for s in edited_steps}

        for step in edited_steps:
            for dep in step.dependencies:
                if dep not in edited_indices:
                    warnings.append(
                        f"Step {step.step_index} ('{step.description[:30]}...') depends on "
                        f"Step {dep} which was deleted."
                    )

        return warnings
