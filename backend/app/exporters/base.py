from __future__ import annotations

from abc import ABC, abstractmethod


class BaseExporter(ABC):
    media_type: str
    file_extension: str

    @abstractmethod
    def export(self, script: object) -> bytes:
        """Convert a TestScriptRead to bytes in this format."""

    def filename(self, script: object) -> str:
        title = getattr(script, "title", "script").lower().replace(" ", "_")
        return f"{title}.{self.file_extension}"


def get_exporter(fmt: str) -> BaseExporter:
    from app.exporters.playwright_exporter import PlaywrightExporter
    from app.exporters.selenium_exporter import SeleniumExporter
    from app.exporters.pytest_exporter import PytestExporter
    from app.exporters.robot_framework_exporter import RobotFrameworkExporter
    from app.exporters.gherkin_exporter import GherkinExporter

    mapping: dict[str, type[BaseExporter]] = {
        "playwright_python": PlaywrightExporter,
        "selenium_java": SeleniumExporter,
        "pytest": PytestExporter,
        "robot_framework": RobotFrameworkExporter,
        "gherkin": GherkinExporter,
    }
    cls = mapping.get(fmt)
    if not cls:
        raise ValueError(f"Unknown export format: {fmt}")
    return cls()
