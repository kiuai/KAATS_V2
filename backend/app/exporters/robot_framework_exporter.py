"""Robot Framework exporter — generates .robot files with SeleniumLibrary."""
from __future__ import annotations

import re

from app.exporters.base import BaseExporter, ExportContext, StepType, TestCase, TestStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rf_loc(hint: str) -> str:
    """Convert a locator hint to Robot Framework SeleniumLibrary locator."""
    h = hint.strip()
    if not h:
        return "css:body"
    if h.startswith("//") or h.startswith("(//"):
        return f"xpath:{h}"
    if h.startswith("#") or h.startswith(".") or h.startswith("["):
        return f"css:{h}"
    if h.startswith("name="):
        return h
    if h.startswith("id="):
        return h
    if h.startswith("text="):
        return h
    return f"css:{h}"


def _step_to_rf(step: TestStep, indent: str = "    ") -> list[str]:
    lines: list[str] = []
    loc = _rf_loc(step.locator_hint)

    if step.step_type == StepType.NAVIGATE:
        url = step.input_value or step.action
        lines.append(f"{indent}Go To    {url}")

    elif step.step_type == StepType.CLICK:
        lines.append(f"{indent}Click Element    {loc}")

    elif step.step_type == StepType.INPUT:
        lines.append(f"{indent}Input Text    {loc}    {step.input_value}")

    elif step.step_type == StepType.SELECT:
        lines.append(f"{indent}Select From List By Label    {loc}    {step.input_value}")

    elif step.step_type == StepType.ASSERT:
        lines.append(f"{indent}Element Should Be Visible    {loc}")
        if step.expected_result:
            lines.append(f"{indent}Element Should Contain    {loc}    {step.expected_result}")

    elif step.step_type == StepType.WAIT:
        if step.locator_hint:
            lines.append(f"{indent}Wait Until Element Is Visible    {loc}    timeout=10s")
        else:
            lines.append(f"{indent}Sleep    1s")

    elif step.step_type == StepType.SCREENSHOT:
        name = re.sub(r"[^\w]", "_", step.action.lower())[:40] or f"step_{step.number}"
        lines.append(f"{indent}Capture Page Screenshot    {name}.png")

    else:
        lines.append(f"{indent}Log    TODO: {step.action}    level=WARN")

    return lines


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------

class RobotFrameworkExporter(BaseExporter):
    """Generates Robot Framework .robot files with SeleniumLibrary."""

    def file_extension(self) -> str:
        return "robot"

    @property
    def media_type(self) -> str:
        return "text/plain"

    def export(self, test_cases: list[TestCase], context: ExportContext | None = None) -> str:
        base_url = (context.base_url if context else "") or "http://localhost:3000"
        system_name = context.system_name if context else "System Under Test"
        browser = "Chrome"

        lines: list[str] = [
            "*** Settings ***",
            "Library           SeleniumLibrary",
            f"Suite Setup       Open Browser    {base_url}    {browser}",
            "Suite Teardown    Close All Browsers",
            "Test Setup        Maximize Browser Window",
            "Test Teardown     Run Keyword If Test Failed    Capture Page Screenshot",
            "",
            "*** Variables ***",
            f"${{BASE_URL}}     {base_url}",
            f"${{BROWSER}}      {browser}",
            "${{TIMEOUT}}     10s",
            "",
            "*** Test Cases ***",
        ]

        for tc in test_cases:
            lines.append(tc.title)
            if tc.description:
                lines.append(f"    [Documentation]    {tc.description}")
            lines.append(f"    [Tags]    {tc.test_type}    {tc.priority}")

            for step in tc.steps:
                lines.append(f"    # Step {step.number}: {step.action}")
                lines.extend(_step_to_rf(step, indent="    "))

            if tc.expected_outcome:
                lines.append(f"    # Expected outcome: {tc.expected_outcome}")
            lines.append("")

        lines += [
            "*** Keywords ***",
            "Navigate To Page",
            "    [Arguments]    ${url}",
            "    Go To    ${url}",
            "    Wait Until Page Contains Element    tag:body    timeout=${TIMEOUT}",
            "",
            "Assert Element Present",
            "    [Arguments]    ${locator}    ${text}=${EMPTY}",
            "    Element Should Be Visible    ${locator}",
            "    Run Keyword If    '${text}' != '${EMPTY}'    Element Should Contain    ${locator}    ${text}",
            "",
            "Fill Form Field",
            "    [Arguments]    ${locator}    ${value}",
            "    Wait Until Element Is Visible    ${locator}    timeout=${TIMEOUT}",
            "    Clear Element Text    ${locator}",
            "    Input Text    ${locator}    ${value}",
            "",
            "Click And Wait",
            "    [Arguments]    ${locator}",
            "    Click Element    ${locator}",
            "    Wait Until Element Is Not Visible    xpath://div[@class='loading']    timeout=${TIMEOUT}",
            "    ...    ignore_error=True",
            "",
        ]

        return "\n".join(lines)

    def validate(self, content: str) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if "*** Settings ***" not in content:
            errors.append("Missing *** Settings *** section")
        if "*** Test Cases ***" not in content:
            errors.append("Missing *** Test Cases *** section")
        return len(errors) == 0, errors
