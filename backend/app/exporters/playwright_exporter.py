"""Playwright TypeScript exporter — generates @playwright/test .ts files."""

from __future__ import annotations

import re

from app.exporters.base import BaseExporter, ExportContext, StepType, TestCase, TestStep

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_id(text: str) -> str:
    return re.sub(r"[^\w]", "_", text.lower().strip())[:60]


def _ts_str(s: str) -> str:
    """Escape a string for use inside single-quoted TS string literals."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def _ts_template(s: str) -> str:
    """Escape a string for use inside TS template literals (backtick)."""
    return s.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def _build_locator(step: TestStep) -> str:
    hint = step.locator_hint.strip()
    if not hint:
        return "page.locator('body')"
    if hint.startswith("//") or hint.startswith("(//"):
        return f"page.locator('xpath={_ts_str(hint)}')"
    if hint.startswith("#") or hint.startswith(".") or hint.startswith("["):
        return f"page.locator('{_ts_str(hint)}')"
    if hint.startswith("role="):
        rest = hint[5:]
        role, _, name_part = rest.partition("[name=")
        name = name_part.rstrip("]").strip("'\"")
        if name:
            return f"page.getByRole('{_ts_str(role)}', {{ name: '{_ts_str(name)}' }})"
        return f"page.getByRole('{_ts_str(role)}')"
    if hint.startswith("text="):
        return f"page.getByText('{_ts_str(hint[5:])}')"
    if hint.startswith("label="):
        return f"page.getByLabel('{_ts_str(hint[6:])}')"
    if hint.startswith("placeholder="):
        return f"page.getByPlaceholder('{_ts_str(hint[12:])}')"
    return f"page.locator('{_ts_str(hint)}')"


def _step_to_ts(step: TestStep, indent: str = "    ") -> list[str]:
    lines: list[str] = []
    loc = _build_locator(step)

    if step.step_type == StepType.NAVIGATE:
        url = step.input_value or step.action
        lines.append(f"{indent}await page.goto(`{_ts_template(url)}`);")

    elif step.step_type == StepType.CLICK:
        lines.append(f"{indent}await {loc}.click();")

    elif step.step_type == StepType.INPUT:
        val = _ts_str(step.input_value)
        lines.append(f"{indent}await {loc}.fill('{val}');")

    elif step.step_type == StepType.SELECT:
        val = _ts_str(step.input_value)
        lines.append(f"{indent}await {loc}.selectOption('{val}');")

    elif step.step_type == StepType.ASSERT:
        lines.append(f"{indent}await expect({loc}).toBeVisible();")
        if step.expected_result and not step.expected_result.lower().startswith("element"):
            txt = _ts_str(step.expected_result)
            lines.append(f"{indent}await expect({loc}).toContainText('{txt}');")

    elif step.step_type == StepType.WAIT:
        if step.locator_hint:
            lines.append(f"{indent}await {loc}.waitFor({{ state: 'visible' }});")
        else:
            lines.append(f"{indent}await page.waitForTimeout(1000);")

    elif step.step_type == StepType.SCREENSHOT:
        name = _safe_id(step.action) or f"step_{step.number}"
        lines.append(f"{indent}await page.screenshot({{ path: `screenshots/{name}.png` }});")

    else:
        lines.append(f"{indent}// TODO: {step.action}")

    return lines


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------


class PlaywrightExporter(BaseExporter):
    """Generates Playwright TypeScript test files (.ts)."""

    def file_extension(self) -> str:
        return "ts"

    @property
    def media_type(self) -> str:
        return "text/typescript"

    def export(self, test_cases: list[TestCase], context: ExportContext | None = None) -> str:
        base_url = context.base_url if context else ""
        system_name = context.system_name if context else "System Under Test"
        suite_name = f"{system_name} Tests"

        lines: list[str] = [
            "import { test, expect, Page } from '@playwright/test';",
            "",
            f"test.describe('{_ts_str(suite_name)}', () => {{",
            "",
            "  test.beforeEach(async ({ page }) => {",
        ]
        if base_url:
            lines.append(f"    await page.goto('{_ts_str(base_url)}');")
        lines += ["  });", ""]

        for tc in test_cases:
            lines.append(f"  test('{_ts_str(tc.title)}', async ({{ page }}) => {{")

            if tc.preconditions:
                lines.append("    // Preconditions:")
                for pre in tc.preconditions:
                    lines.append(f"    //   - {pre}")
                lines.append("")

            for step in tc.steps:
                lines.append(f"    // Step {step.number}: {step.action}")
                if step.expected_result:
                    lines.append(f"    //   Expected: {step.expected_result}")
                lines.extend(_step_to_ts(step, indent="    "))
                lines.append("")

            if tc.expected_outcome:
                lines.append(f"    // Verify outcome: {tc.expected_outcome}")

            lines += ["  });", ""]

        lines.append("});")
        return "\n".join(lines)

    def validate(self, content: str) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if "import { test, expect" not in content:
            errors.append("Missing Playwright imports")
        if "test.describe(" not in content:
            errors.append("Missing test.describe block")
        return len(errors) == 0, errors
