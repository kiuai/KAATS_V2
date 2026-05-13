"""
Base types and abstract exporter for the KAATS multi-format export engine.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Export-time domain types (distinct from ORM models)
# ---------------------------------------------------------------------------

class StepType(str, Enum):
    NAVIGATE = "NAVIGATE"
    CLICK = "CLICK"
    INPUT = "INPUT"
    SELECT = "SELECT"
    ASSERT = "ASSERT"
    WAIT = "WAIT"
    SCREENSHOT = "SCREENSHOT"


@dataclass
class TestStep:
    number: int
    action: str           # Business-language action description
    locator_hint: str     # CSS selector, XPath, or element description
    input_value: str      # Data to enter (empty string if not applicable)
    expected_result: str
    step_type: StepType


@dataclass
class TestCase:
    id: str
    title: str
    description: str
    preconditions: list[str] = field(default_factory=list)
    steps: list[TestStep] = field(default_factory=list)
    expected_outcome: str = ""
    test_type: str = "positive"   # positive | negative | boundary | integration
    priority: str = "medium"


@dataclass
class ExportContext:
    system_name: str
    base_url: str
    export_format: "ExportFormatEnum"
    include_comments: bool = True


class ExportFormatEnum(str, Enum):
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"
    PYTEST = "pytest"
    ROBOT_FRAMEWORK = "robot_framework"
    GHERKIN = "gherkin"
    MANUAL_STEPS = "manual_steps"


# ---------------------------------------------------------------------------
# Abstract base exporter
# ---------------------------------------------------------------------------

class BaseExporter(ABC):
    """Abstract base for all format exporters."""

    @abstractmethod
    def export(self, test_cases: list[TestCase], context: ExportContext | None = None) -> str:
        """Convert a list of TestCase objects to format-specific text."""

    @abstractmethod
    def file_extension(self) -> str:
        """Return the file extension (without leading dot)."""

    @property
    def media_type(self) -> str:
        return "text/plain"

    def validate(self, content: str) -> tuple[bool, list[str]]:
        """
        Basic validation of generated content.
        Returns (is_valid, errors). Subclasses may override.
        """
        return True, []

    def filename(self, title: str) -> str:
        safe = re.sub(r"[^\w\s-]", "", title.lower()).strip()
        safe = re.sub(r"\s+", "_", safe)[:60]
        return f"{safe}.{self.file_extension()}"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_exporter(fmt: str) -> BaseExporter:
    from app.exporters.playwright_exporter import PlaywrightExporter
    from app.exporters.selenium_exporter import SeleniumExporter
    from app.exporters.pytest_exporter import PytestExporter
    from app.exporters.robot_framework_exporter import RobotFrameworkExporter
    from app.exporters.gherkin_exporter import GherkinExporter

    mapping: dict[str, type[BaseExporter]] = {
        ExportFormatEnum.PLAYWRIGHT.value: PlaywrightExporter,
        ExportFormatEnum.SELENIUM.value: SeleniumExporter,
        ExportFormatEnum.PYTEST.value: PytestExporter,
        ExportFormatEnum.ROBOT_FRAMEWORK.value: RobotFrameworkExporter,
        ExportFormatEnum.GHERKIN.value: GherkinExporter,
        # Legacy keys
        "playwright_python": PlaywrightExporter,
        "playwright_typescript": PlaywrightExporter,
        "selenium_java": SeleniumExporter,
        "selenium_python": SeleniumExporter,
    }
    cls = mapping.get(fmt)
    if not cls:
        valid = sorted(set(mapping))
        raise ValueError(f"Unknown export format: {fmt!r}. Valid values: {valid}")
    return cls()
