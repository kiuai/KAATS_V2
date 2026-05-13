from __future__ import annotations

from app.exporters.base import BaseExporter


class PlaywrightExporter(BaseExporter):
    media_type = "text/x-python"
    file_extension = "py"

    def export(self, script: object) -> bytes:
        lines = [
            "import pytest",
            "from playwright.async_api import async_playwright, expect",
            "",
            "",
            f"# {getattr(script, 'title', 'Test Script')}",
            "",
            "@pytest.mark.asyncio",
            "async def test_main():",
            "    async with async_playwright() as pw:",
            "        browser = await pw.chromium.launch(headless=True)",
            "        page = await browser.new_page()",
            "",
        ]
        for case in getattr(script, "cases", []):
            lines.append(f"        # {case.name}")
            for step in getattr(case, "steps", []):
                lines.append(f"        # Step {step.step_number}: {step.description}")
                lines.append(f"        # Expected: {step.expected_outcome or 'N/A'}")
                lines.append(f"        pass  # TODO: implement")
                lines.append("")
        lines += ["        await browser.close()", ""]
        return "\n".join(lines).encode()
