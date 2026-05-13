"""Pure pytest + httpx exporter — API-focused, no browser."""
from __future__ import annotations

import re

from app.exporters.base import BaseExporter, ExportContext, StepType, TestCase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_name(text: str) -> str:
    return re.sub(r"[^\w]", "_", text.lower().strip())[:60]


def _py_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------

class PytestExporter(BaseExporter):
    """Generates pure pytest + httpx API tests (.py)."""

    def file_extension(self) -> str:
        return "py"

    @property
    def media_type(self) -> str:
        return "text/x-python"

    def export(self, test_cases: list[TestCase], context: ExportContext | None = None) -> str:
        base_url = (context.base_url if context else "") or "http://localhost:8000"
        system_name = context.system_name if context else "API"

        lines: list[str] = [
            "import pytest",
            "import httpx",
            "",
            "",
            f'BASE_URL = "{_py_str(base_url)}"',
            "",
            "",
            "@pytest.fixture(scope='module')",
            "def client():",
            "    with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:",
            "        yield c",
            "",
        ]

        for tc in test_cases:
            fn_name = "test_" + (_safe_name(tc.title) or tc.id)
            lines.append("")
            lines.append(f"def {fn_name}(client):")

            # Docstring
            if tc.description or tc.preconditions:
                lines.append('    """')
                if tc.description:
                    lines.append(f"    {tc.description}")
                if tc.preconditions:
                    lines.append("    Preconditions:")
                    for pre in tc.preconditions:
                        lines.append(f"        - {pre}")
                lines.append('    """')

            lines.append("    # Arrange")
            lines.append("    headers: dict = {}")
            lines.append("    payload: dict = {}")
            lines.append("")

            last_response_var: str | None = None

            for step in tc.steps:
                lines.append(f"    # Step {step.number}: {step.action}")

                if step.step_type == StepType.NAVIGATE:
                    path = step.input_value or step.locator_hint or "/"
                    # Strip full URL to path
                    if path.startswith("http"):
                        from urllib.parse import urlparse
                        try:
                            path = urlparse(path).path or "/"
                        except Exception:
                            path = "/"
                    resp_var = f"response_{step.number}"
                    last_response_var = resp_var
                    lines += [
                        f"    # Act",
                        f'    {resp_var} = client.get("{_py_str(path)}", headers=headers)',
                        f"    assert {resp_var}.status_code == 200, (",
                        f'        f"Expected 200, got {{{resp_var}.status_code}}: {{{resp_var}.text}}"',
                        f"    )",
                    ]

                elif step.step_type == StepType.INPUT:
                    field_name = _safe_name(step.action) or f"field_{step.number}"
                    lines.append(f'    payload["{_py_str(field_name)}"] = "{_py_str(step.input_value)}"')

                elif step.step_type == StepType.CLICK:
                    # Treat click as a POST to the locator path
                    path = step.locator_hint or "/"
                    resp_var = f"response_{step.number}"
                    last_response_var = resp_var
                    lines += [
                        f"    # Act: POST {path}",
                        f'    {resp_var} = client.post("{_py_str(path)}", json=payload, headers=headers)',
                        f"    assert {resp_var}.status_code in (200, 201, 204), (",
                        f'        f"Expected success, got {{{resp_var}.status_code}}: {{{resp_var}.text}}"',
                        f"    )",
                    ]

                elif step.step_type == StepType.ASSERT:
                    ref = last_response_var or "response"
                    if step.expected_result:
                        exp = _py_str(step.expected_result)
                        lines += [
                            f"    # Assert: {exp}",
                            f"    data = {ref}.json()",
                        ]
                        if step.locator_hint:
                            key = re.sub(r"[^\w]", "", step.locator_hint.lstrip("#.["))
                            lines += [
                                f'    assert "{_py_str(key)}" in str(data), (',
                                f'        f"Expected to find \\"{_py_str(key)}\\" in response: {{data}}"',
                                f"    )",
                            ]
                        else:
                            lines.append(f'    assert data is not None, "Response body should not be empty"')

                elif step.step_type in (StepType.WAIT, StepType.SCREENSHOT):
                    lines.append(f"    pass  # {step.step_type.value}: {step.action}")

                else:
                    lines.append(f"    # {step.action}")

                lines.append("")

            if tc.expected_outcome:
                lines.append(f"    # Expected outcome: {tc.expected_outcome}")

        lines.append("")
        return "\n".join(lines)

    def validate(self, content: str) -> tuple[bool, list[str]]:
        errors: list[str] = []
        try:
            compile(content, "<pytest_export>", "exec")
        except SyntaxError as exc:
            errors.append(f"Syntax error: {exc}")
        return len(errors) == 0, errors
