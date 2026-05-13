from __future__ import annotations

from app.exporters.base import BaseExporter


class GherkinExporter(BaseExporter):
    media_type = "text/plain"
    file_extension = "feature"

    def export(self, script: object) -> bytes:
        title = getattr(script, "title", "Feature")
        lines = [f"Feature: {title}", ""]
        for case in getattr(script, "cases", []):
            lines.append(f"  Scenario: {case.name}")
            for step in getattr(case, "steps", []):
                prefix = "Given" if step.step_number == 1 else "And"
                lines.append(f"    {prefix} {step.description}")
            lines.append("")
        return "\n".join(lines).encode()
