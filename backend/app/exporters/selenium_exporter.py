"""Selenium Python (pytest + WebDriverWait) exporter."""

from __future__ import annotations

import re

from app.exporters.base import BaseExporter, ExportContext, StepType, TestCase, TestStep

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_name(text: str) -> str:
    return re.sub(r"[^\w]", "_", text.lower().strip())[:60]


def _py_str(s: str) -> str:
    """Escape for Python double-quoted string literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _build_by(hint: str) -> str:
    """Return By.<TYPE>, '<value>' string for a locator hint."""
    h = hint.strip()
    if not h:
        return 'By.TAG_NAME, "body"'
    if h.startswith("//") or h.startswith("(//"):
        return f'By.XPATH, "{_py_str(h)}"'
    if h.startswith("#"):
        return f'By.CSS_SELECTOR, "{_py_str(h)}"'
    if h.startswith(".") or h.startswith("["):
        return f'By.CSS_SELECTOR, "{_py_str(h)}"'
    if h.startswith("name="):
        return f'By.NAME, "{_py_str(h[5:])}"'
    if h.startswith("id="):
        return f'By.ID, "{_py_str(h[3:])}"'
    return f'By.CSS_SELECTOR, "{_py_str(h)}"'


def _step_to_py(step: TestStep, indent: str = "        ") -> list[str]:
    lines: list[str] = []
    by = _build_by(step.locator_hint)

    if step.step_type == StepType.NAVIGATE:
        url = _py_str(step.input_value or step.action)
        lines.append(f'{indent}driver.get("{url}")')

    elif step.step_type == StepType.CLICK:
        lines += [
            f"{indent}el = WebDriverWait(driver, 10).until(",
            f"{indent}    EC.element_to_be_clickable(({by}))",
            f"{indent})",
            f"{indent}el.click()",
        ]

    elif step.step_type == StepType.INPUT:
        val = _py_str(step.input_value)
        lines += [
            f"{indent}el = WebDriverWait(driver, 10).until(",
            f"{indent}    EC.visibility_of_element_located(({by}))",
            f"{indent})",
            f"{indent}el.clear()",
            f'{indent}el.send_keys("{val}")',
        ]

    elif step.step_type == StepType.SELECT:
        val = _py_str(step.input_value)
        lines += [
            f"{indent}el = WebDriverWait(driver, 10).until(",
            f"{indent}    EC.visibility_of_element_located(({by}))",
            f"{indent})",
            f'{indent}Select(el).select_by_visible_text("{val}")',
        ]

    elif step.step_type == StepType.ASSERT:
        lines += [
            f"{indent}el = WebDriverWait(driver, 10).until(",
            f"{indent}    EC.visibility_of_element_located(({by}))",
            f"{indent})",
        ]
        if step.expected_result:
            expected = _py_str(step.expected_result)
            lines.append(f'{indent}assert "{expected}" in el.text, (')
            lines.append(
                f'{indent}    f"Expected \\"{expected}\\" in element text, got: {{el.text}}"'
            )
            lines.append(f"{indent})")
        else:
            lines.append(f'{indent}assert el.is_displayed(), "Element should be visible"')

    elif step.step_type == StepType.WAIT:
        if step.locator_hint:
            lines += [
                f"{indent}WebDriverWait(driver, 10).until(",
                f"{indent}    EC.visibility_of_element_located(({by}))",
                f"{indent})",
            ]
        else:
            lines.append(f"{indent}import time; time.sleep(1)")

    elif step.step_type == StepType.SCREENSHOT:
        name = _safe_name(step.action) or f"step_{step.number}"
        lines.append(f'{indent}driver.save_screenshot("screenshots/{name}.png")')

    else:
        lines.append(f"{indent}pass  # TODO: {step.action}")

    return lines


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------


class SeleniumExporter(BaseExporter):
    """Generates pytest + Selenium WebDriver Python tests (.py)."""

    def file_extension(self) -> str:
        return "py"

    @property
    def media_type(self) -> str:
        return "text/x-python"

    def export(self, test_cases: list[TestCase], context: ExportContext | None = None) -> str:
        base_url = (context.base_url if context else "") or "http://localhost:3000"
        system_name = context.system_name if context else "SystemTests"
        class_name = (
            "".join(w.capitalize() for w in re.sub(r"[^\w\s]", "", system_name).split())
            or "TestSuite"
        )

        lines: list[str] = [
            "import pytest",
            "from selenium import webdriver",
            "from selenium.webdriver.common.by import By",
            "from selenium.webdriver.support.ui import WebDriverWait, Select",
            "from selenium.webdriver.support import expected_conditions as EC",
            "from selenium.webdriver.chrome.options import Options",
            "",
            "",
            "@pytest.fixture(scope='module')",
            "def driver():",
            "    options = Options()",
            "    options.add_argument('--headless')",
            "    options.add_argument('--no-sandbox')",
            "    options.add_argument('--disable-dev-shm-usage')",
            "    d = webdriver.Chrome(options=options)",
            "    d.implicitly_wait(5)",
            "    yield d",
            "    d.quit()",
            "",
            "",
            "@pytest.fixture(scope='module')",
            "def base_url():",
            f'    return "{_py_str(base_url)}"',
            "",
            "",
            f"class Test{class_name}:",
        ]

        for tc in test_cases:
            method_name = "test_" + (_safe_name(tc.title) or tc.id)
            lines += [
                "",
                f"    def {method_name}(self, driver, base_url):",
            ]
            if tc.description or tc.preconditions:
                lines.append('        """')
                if tc.description:
                    lines.append(f"        {tc.description}")
                if tc.preconditions:
                    lines.append("        Preconditions:")
                    for pre in tc.preconditions:
                        lines.append(f"            - {pre}")
                lines.append('        """')

            for step in tc.steps:
                lines.append(f"        # Step {step.number}: {step.action}")
                if step.expected_result:
                    lines.append(f"        # Expected: {step.expected_result}")
                lines.extend(_step_to_py(step, indent="        "))

        lines.append("")
        return "\n".join(lines)

    def validate(self, content: str) -> tuple[bool, list[str]]:
        errors: list[str] = []
        try:
            compile(content, "<selenium_export>", "exec")
        except SyntaxError as exc:
            errors.append(f"Syntax error: {exc}")
        return len(errors) == 0, errors
