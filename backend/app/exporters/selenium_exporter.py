from __future__ import annotations

from app.exporters.base import BaseExporter


class SeleniumExporter(BaseExporter):
    media_type = "text/x-java"
    file_extension = "java"

    def export(self, script: object) -> bytes:
        title = getattr(script, "title", "TestScript")
        class_name = "".join(w.capitalize() for w in title.split())
        lines = [
            "import org.junit.jupiter.api.Test;",
            "import org.openqa.selenium.WebDriver;",
            "import org.openqa.selenium.chrome.ChromeDriver;",
            "",
            f"public class {class_name} {{",
            "    @Test",
            "    public void testMain() {",
            "        WebDriver driver = new ChromeDriver();",
        ]
        for case in getattr(script, "cases", []):
            lines.append(f"        // {case.name}")
            for step in getattr(case, "steps", []):
                lines.append(f"        // Step {step.step_number}: {step.description}")
        lines += ["        driver.quit();", "    }", "}"]
        return "\n".join(lines).encode()
