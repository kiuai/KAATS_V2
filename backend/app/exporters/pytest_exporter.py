from __future__ import annotations

from app.exporters.base import BaseExporter


class PytestExporter(BaseExporter):
    media_type = "text/x-python"
    file_extension = "py"

    def export(self, script: object) -> bytes:
        title = getattr(script, "title", "test_script")
        fn_name = "test_" + title.lower().replace(" ", "_")
        lines = [
            "import pytest",
            "",
            "",
            f"def {fn_name}():",
        ]
        for case in getattr(script, "cases", []):
            for step in getattr(case, "steps", []):
                lines.append(f"    # Step {step.step_number}: {step.description}")
                lines.append(f"    pass")
        lines.append("")
        return "\n".join(lines).encode()
