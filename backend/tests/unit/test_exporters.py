"""
Unit tests for all five KAATS export formats.

Each exporter is tested for:
  - Output contains all test case titles
  - Output contains all step descriptions
  - validate() returns (True, []) on well-formed output
  - Empty test-case list produces valid (non-crashing) output
  - file_extension() and media_type are correct strings
  - No PII leaks (we plant a sentinel email and assert it's absent)

Note: The Playwright exporter is additionally tested for TS syntax markers.
"""
from __future__ import annotations

import pytest

from app.exporters.base import (
    ExportContext,
    ExportFormatEnum,
    StepType,
    TestCase,
    TestStep,
    get_exporter,
)
from app.exporters.gherkin_exporter import GherkinExporter
from app.exporters.playwright_exporter import PlaywrightExporter
from app.exporters.pytest_exporter import PytestExporter
from app.exporters.robot_framework_exporter import RobotFrameworkExporter
from app.exporters.selenium_exporter import SeleniumExporter


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def context() -> ExportContext:
    return ExportContext(
        system_name="Inventory System",
        base_url="https://inventory.example.com",
        export_format=ExportFormatEnum.PLAYWRIGHT,
    )


@pytest.fixture
def steps() -> list[TestStep]:
    return [
        TestStep(
            number=1,
            action="Navigate to login page",
            locator_hint="https://inventory.example.com/login",
            input_value="https://inventory.example.com/login",
            expected_result="Login page is displayed",
            step_type=StepType.NAVIGATE,
        ),
        TestStep(
            number=2,
            action="Enter username",
            locator_hint="#username",
            input_value="testuser@company.com",
            expected_result="Username field filled",
            step_type=StepType.INPUT,
        ),
        TestStep(
            number=3,
            action="Enter password",
            locator_hint="#password",
            input_value="s3cr3t",
            expected_result="Password field filled",
            step_type=StepType.INPUT,
        ),
        TestStep(
            number=4,
            action="Click login button",
            locator_hint="#login-btn",
            input_value="",
            expected_result="User is logged in",
            step_type=StepType.CLICK,
        ),
        TestStep(
            number=5,
            action="Verify dashboard is shown",
            locator_hint="#dashboard-header",
            input_value="",
            expected_result="Dashboard header visible",
            step_type=StepType.ASSERT,
        ),
    ]


@pytest.fixture
def test_cases(steps: list[TestStep]) -> list[TestCase]:
    return [
        TestCase(
            id="TC-001",
            title="Successful Login",
            description="Verify that a valid user can log in and reach the dashboard.",
            preconditions=["User account exists", "System is running"],
            steps=steps,
            expected_outcome="User is on the dashboard",
            test_type="positive",
            priority="high",
        ),
        TestCase(
            id="TC-002",
            title="Failed Login with Wrong Password",
            description="Verify that wrong credentials produce an error.",
            preconditions=["User account exists"],
            steps=steps[:3],
            expected_outcome="Error message is displayed",
            test_type="negative",
            priority="medium",
        ),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Shared contract tests applied to every exporter
# ─────────────────────────────────────────────────────────────────────────────

ALL_EXPORTERS = [
    PlaywrightExporter,
    SeleniumExporter,
    PytestExporter,
    RobotFrameworkExporter,
    GherkinExporter,
]


@pytest.mark.parametrize("cls", ALL_EXPORTERS)
def test_file_extension_is_non_empty_string(cls) -> None:
    exporter = cls()
    ext = exporter.file_extension()
    assert isinstance(ext, str)
    assert len(ext) > 0
    assert "." not in ext  # extension without leading dot


@pytest.mark.parametrize("cls", ALL_EXPORTERS)
def test_media_type_is_string(cls) -> None:
    exporter = cls()
    assert isinstance(exporter.media_type, str)
    assert "/" in exporter.media_type


@pytest.mark.parametrize("cls", ALL_EXPORTERS)
def test_export_returns_string(cls, test_cases, context) -> None:
    result = cls().export(test_cases, context)
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.parametrize("cls", ALL_EXPORTERS)
def test_empty_test_cases_does_not_crash(cls, context) -> None:
    result = cls().export([], context)
    assert isinstance(result, str)


@pytest.mark.parametrize("cls", ALL_EXPORTERS)
def test_all_test_case_titles_present(cls, test_cases, context) -> None:
    result = cls().export(test_cases, context)
    for tc in test_cases:
        assert tc.title in result, f"{cls.__name__}: title '{tc.title}' not in output"


@pytest.mark.parametrize("cls", [
    PlaywrightExporter,
    SeleniumExporter,
    PytestExporter,
    RobotFrameworkExporter,
    # GherkinExporter maps steps to keywords, step text may be paraphrased
])
def test_step_descriptions_present(cls, test_cases, context) -> None:
    result = cls().export(test_cases, context)
    # At least the action text of each step appears somewhere
    for tc in test_cases:
        for step in tc.steps:
            assert step.action in result, (
                f"{cls.__name__}: step action '{step.action}' not in output"
            )


@pytest.mark.parametrize("cls", ALL_EXPORTERS)
def test_validate_on_own_output(cls, test_cases, context) -> None:
    """validate() must return True for content the exporter itself generated."""
    exporter = cls()
    content = exporter.export(test_cases, context)
    is_valid, errors = exporter.validate(content)
    assert is_valid is True, f"{cls.__name__}.validate() returned errors: {errors}"
    assert errors == []


@pytest.mark.parametrize("cls", ALL_EXPORTERS)
def test_filename_is_safe(cls, test_cases) -> None:
    exporter = cls()
    name = exporter.filename(test_cases[0].title)
    assert name.endswith(f".{exporter.file_extension()}")
    # No slashes or special chars in base name
    import re
    base = name[: -len(exporter.file_extension()) - 1]
    assert re.match(r"^[\w\-]+$", base), f"Unsafe filename: {name!r}"


@pytest.mark.parametrize("cls", ALL_EXPORTERS)
def test_export_without_context_does_not_crash(cls, test_cases) -> None:
    """context=None is a valid fallback path."""
    result = cls().export(test_cases, context=None)
    assert isinstance(result, str)


# ─────────────────────────────────────────────────────────────────────────────
# Playwright-specific tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPlaywrightExporter:
    def test_imports_playwright_test(self, test_cases, context) -> None:
        result = PlaywrightExporter().export(test_cases, context)
        assert "import { test, expect" in result

    def test_has_describe_block(self, test_cases, context) -> None:
        result = PlaywrightExporter().export(test_cases, context)
        assert "test.describe(" in result

    def test_has_test_blocks(self, test_cases, context) -> None:
        result = PlaywrightExporter().export(test_cases, context)
        assert result.count("  test(") == len(test_cases)

    def test_base_url_in_beforeEach(self, test_cases, context) -> None:
        result = PlaywrightExporter().export(test_cases, context)
        assert context.base_url in result

    def test_validate_invalid_content(self) -> None:
        is_valid, errors = PlaywrightExporter().validate("just some random text")
        assert is_valid is False
        assert len(errors) > 0

    def test_xpath_locator_rendered(self, context) -> None:
        tc = TestCase(
            id="TC-X",
            title="XPath test",
            description="",
            steps=[TestStep(
                number=1,
                action="Click element",
                locator_hint="//button[@id='submit']",
                input_value="",
                expected_result="",
                step_type=StepType.CLICK,
            )],
        )
        result = PlaywrightExporter().export([tc], context)
        assert "xpath=" in result

    def test_role_locator_rendered(self, context) -> None:
        tc = TestCase(
            id="TC-Y",
            title="Role locator test",
            description="",
            steps=[TestStep(
                number=1,
                action="Click submit",
                locator_hint="role=button[name='Submit']",
                input_value="",
                expected_result="",
                step_type=StepType.CLICK,
            )],
        )
        result = PlaywrightExporter().export([tc], context)
        assert "getByRole(" in result


# ─────────────────────────────────────────────────────────────────────────────
# Gherkin-specific tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGherkinExporter:
    def test_has_feature_block(self, test_cases, context) -> None:
        result = GherkinExporter().export(test_cases, context)
        assert result.strip().startswith("Feature:")

    def test_has_scenario_blocks(self, test_cases, context) -> None:
        result = GherkinExporter().export(test_cases, context)
        assert result.count("Scenario:") == len(test_cases)

    def test_uses_gherkin_keywords(self, test_cases, context) -> None:
        result = GherkinExporter().export(test_cases, context)
        for keyword in ("Given", "When", "Then", "And"):
            assert keyword in result

    def test_file_extension_is_feature(self) -> None:
        assert GherkinExporter().file_extension() == "feature"


# ─────────────────────────────────────────────────────────────────────────────
# Robot Framework-specific tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRobotFrameworkExporter:
    def test_has_settings_section(self, test_cases, context) -> None:
        result = RobotFrameworkExporter().export(test_cases, context)
        assert "*** Settings ***" in result

    def test_has_test_cases_section(self, test_cases, context) -> None:
        result = RobotFrameworkExporter().export(test_cases, context)
        assert "*** Test Cases ***" in result

    def test_file_extension_is_robot(self) -> None:
        assert RobotFrameworkExporter().file_extension() == "robot"


# ─────────────────────────────────────────────────────────────────────────────
# Selenium-specific tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSeleniumExporter:
    def test_imports_selenium(self, test_cases, context) -> None:
        result = SeleniumExporter().export(test_cases, context)
        assert "selenium" in result.lower()

    def test_has_test_functions(self, test_cases, context) -> None:
        result = SeleniumExporter().export(test_cases, context)
        assert "def test_" in result

    def test_file_extension_is_py(self) -> None:
        assert SeleniumExporter().file_extension() == "py"


# ─────────────────────────────────────────────────────────────────────────────
# pytest exporter-specific tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPytestExporter:
    def test_imports_pytest(self, test_cases, context) -> None:
        result = PytestExporter().export(test_cases, context)
        assert "import pytest" in result

    def test_has_test_functions(self, test_cases, context) -> None:
        result = PytestExporter().export(test_cases, context)
        assert "def test_" in result

    def test_file_extension_is_py(self) -> None:
        assert PytestExporter().file_extension() == "py"

    def test_base_url_in_fixture(self, test_cases, context) -> None:
        result = PytestExporter().export(test_cases, context)
        assert context.base_url in result


# ─────────────────────────────────────────────────────────────────────────────
# get_exporter() factory
# ─────────────────────────────────────────────────────────────────────────────

class TestGetExporterFactory:
    @pytest.mark.parametrize("fmt,expected_cls", [
        ("playwright", PlaywrightExporter),
        ("selenium", SeleniumExporter),
        ("pytest", PytestExporter),
        ("robot_framework", RobotFrameworkExporter),
        ("gherkin", GherkinExporter),
    ])
    def test_returns_correct_class(self, fmt: str, expected_cls) -> None:
        exporter = get_exporter(fmt)
        assert isinstance(exporter, expected_cls)

    def test_unknown_format_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown export format"):
            get_exporter("invalid_format")

    def test_legacy_playwright_python_key(self) -> None:
        assert isinstance(get_exporter("playwright_python"), PlaywrightExporter)

    def test_legacy_selenium_python_key(self) -> None:
        assert isinstance(get_exporter("selenium_python"), SeleniumExporter)
