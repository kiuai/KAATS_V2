"""Gherkin (Cucumber) .feature exporter."""
from __future__ import annotations

import re

from app.exporters.base import BaseExporter, ExportContext, StepType, TestCase, TestStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _gherkin_keyword(step: TestStep, used_given: bool, used_when: bool) -> str:
    """Determine the appropriate Gherkin keyword for a step."""
    if step.step_type in (StepType.NAVIGATE, StepType.WAIT) and not used_given:
        return "Given"
    if step.step_type in (StepType.CLICK, StepType.INPUT, StepType.SELECT):
        if not used_when:
            return "When"
        return "And"
    if step.step_type == StepType.ASSERT:
        return "Then"
    if step.step_type == StepType.SCREENSHOT:
        return None  # omit screenshot steps from Gherkin
    # Navigator after given already used → And
    if step.step_type == StepType.NAVIGATE and used_given:
        return "And"
    return "And"


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------

class GherkinExporter(BaseExporter):
    """Generates Gherkin .feature files (Cucumber / SpecFlow compatible)."""

    def file_extension(self) -> str:
        return "feature"

    @property
    def media_type(self) -> str:
        return "text/plain"

    def export(self, test_cases: list[TestCase], context: ExportContext | None = None) -> str:
        system_name = context.system_name if context else "System"
        base_url = context.base_url if context else ""

        lines: list[str] = [
            f"Feature: {system_name}",
            f"  As a user of {system_name}",
            "  I want to verify the system behaves correctly",
            "  So that I can ensure quality and compliance",
            "",
        ]

        # Shared preconditions (present in every test case) → Background
        all_pres: list[list[str]] = [tc.preconditions for tc in test_cases if tc.preconditions]
        shared_pres: list[str] = []
        if all_pres and len(all_pres) == len(test_cases) and len(test_cases) > 1:
            shared_pres = sorted(
                set.intersection(*[set(p) for p in all_pres])  # type: ignore[arg-type]
            )

        if shared_pres:
            lines.append("  Background:")
            for pre in shared_pres:
                lines.append(f"    Given {pre}")
            if base_url:
                lines.append(f"    And the application is available at {base_url}")
            lines.append("")

        for tc in test_cases:
            # Data-driven test types → Scenario Outline
            input_steps = [s for s in tc.steps if s.input_value and s.step_type == StepType.INPUT]
            use_outline = tc.test_type in ("negative", "boundary") and len(input_steps) > 0

            if use_outline:
                lines.append(f"  Scenario Outline: {_clean(tc.title)}")
            else:
                lines.append(f"  Scenario: {_clean(tc.title)}")

            if tc.description:
                lines.append(f"    # {tc.description}")

            # Case-specific preconditions not already in Background
            unique_pres = [p for p in tc.preconditions if p not in shared_pres]
            for pre in unique_pres:
                lines.append(f"    Given {pre}")

            used_given = len(unique_pres) > 0
            used_when = False
            outline_params: dict[str, list[str]] = {}

            for step in tc.steps:
                kw = _gherkin_keyword(step, used_given, used_when)
                if kw is None:
                    continue

                if kw == "Given":
                    used_given = True
                elif kw == "When":
                    used_when = True

                step_text = _clean(step.action)

                if use_outline and step.step_type == StepType.INPUT and step.input_value:
                    param_key = re.sub(r"[^\w]", "_", step_text)[:20].strip("_")
                    step_text = f"{step_text} with <{param_key}>"
                    outline_params.setdefault(param_key, []).append(step.input_value)
                elif step.input_value:
                    step_text = f'{step_text} with value "{step.input_value}"'

                lines.append(f"    {kw} {step_text}")

            if tc.expected_outcome:
                lines.append(f"    Then {_clean(tc.expected_outcome)}")

            if use_outline and outline_params:
                lines.append("")
                lines.append("    Examples:")
                headers = list(outline_params.keys())
                lines.append("      | " + " | ".join(headers) + " |")
                max_rows = max(len(v) for v in outline_params.values())
                for i in range(max_rows):
                    row = [
                        outline_params[h][i] if i < len(outline_params[h]) else ""
                        for h in headers
                    ]
                    lines.append("      | " + " | ".join(row) + " |")

            lines.append("")

        return "\n".join(lines)

    def validate(self, content: str) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if not content.strip().startswith("Feature:"):
            errors.append("File must start with 'Feature:'")
        if "Scenario:" not in content and "Scenario Outline:" not in content:
            errors.append("No Scenario or Scenario Outline found")
        return len(errors) == 0, errors
