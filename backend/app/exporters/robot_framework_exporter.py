from __future__ import annotations

from app.exporters.base import BaseExporter


class RobotFrameworkExporter(BaseExporter):
    media_type = "text/plain"
    file_extension = "robot"

    def export(self, script: object) -> bytes:
        title = getattr(script, "title", "Test Suite")
        lines = [
            "*** Settings ***",
            "Library    Browser",
            "",
            "*** Test Cases ***",
            title,
        ]
        for case in getattr(script, "cases", []):
            for step in getattr(case, "steps", []):
                lines.append(f"    # Step {step.step_number}: {step.description}")
                lines.append(f"    Log    {step.description}")
        lines.append("")
        return "\n".join(lines).encode()
