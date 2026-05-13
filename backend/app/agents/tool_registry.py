from __future__ import annotations

from langchain.tools import StructuredTool, Tool
from playwright.async_api import Page


def build_crawl_tools(page: Page, memory: any) -> list:  # type: ignore[valid-type]
    """Build the tool set for CrawlAgent."""
    from langchain.tools import tool

    @tool
    async def navigate_to_url(url: str) -> str:
        """Navigate the browser to a URL. Returns the page title."""
        await page.goto(url, wait_until="networkidle")
        return await page.title()

    @tool
    async def get_page_title() -> str:  # type: ignore[override]
        """Return the current page title."""
        return await page.title()

    @tool
    async def get_page_text() -> str:  # type: ignore[override]
        """Return all visible text content of the current page."""
        return await page.inner_text("body")

    @tool
    async def get_interactive_elements() -> str:  # type: ignore[override]
        """Return all interactive elements (buttons, inputs, links) with labels."""
        elements = await page.query_selector_all("button, input, a, select, textarea")
        results = []
        for el in elements[:100]:
            tag = await el.get_attribute("data-tag") or await el.evaluate("el => el.tagName")
            label = await el.get_attribute("aria-label") or await el.inner_text() or ""
            results.append(f"{tag}: {label[:80]}")
        return "\n".join(results)

    @tool
    async def click_element(selector: str) -> str:
        """Click an element by CSS selector."""
        await page.click(selector)
        return f"Clicked: {selector}"

    @tool
    async def fill_input(selector: str, value: str) -> str:
        """Fill an input field by CSS selector."""
        await page.fill(selector, value)
        return f"Filled {selector} with value"

    @tool
    async def get_navigation_links() -> str:  # type: ignore[override]
        """Return all same-origin href links on the current page."""
        origin = page.url.split("/")[0] + "//" + page.url.split("/")[2]
        links = await page.eval_on_selector_all(
            "a[href]",
            f"els => els.map(e => e.href).filter(h => h.startsWith('{origin}'))"
        )
        return "\n".join(links[:200])

    @tool
    async def get_current_url() -> str:  # type: ignore[override]
        """Return the current browser URL."""
        return page.url

    @tool
    async def check_visited(url: str) -> str:
        """Check if a URL has already been crawled."""
        return str(memory.in_set("visited_urls", url))

    @tool
    async def mark_visited(url: str) -> str:
        """Mark a URL as crawled."""
        memory.add_to_set("visited_urls", url)
        return f"Marked visited: {url}"

    @tool
    async def save_requirement_draft(title: str, description: str) -> str:
        """Save a requirement draft to working memory."""
        memory.append("generated_requirements", {"title": title, "description": description})
        count = len(memory.get("generated_requirements", []))
        return f"Saved requirement draft #{count}"

    @tool
    async def take_screenshot(step_description: str = "") -> str:
        """Take a screenshot of the current page."""
        data = await page.screenshot(full_page=False)
        memory.append("screenshots", {"description": step_description, "data": data})
        return "Screenshot captured"

    return [
        navigate_to_url, get_page_title, get_page_text, get_interactive_elements,
        click_element, fill_input, get_navigation_links, get_current_url,
        check_visited, mark_visited, save_requirement_draft, take_screenshot,
    ]


def build_generation_tools(db_session: any, memory: any) -> list:  # type: ignore[valid-type]
    """Build the tool set for GenerationAgent."""
    from langchain.tools import tool

    @tool
    async def save_script_draft(title: str, content: str, format: str = "playwright_python") -> str:
        """Save a generated test script draft to working memory."""
        memory.append("pending_scripts", {"title": title, "content": content, "format": format})
        return f"Script draft saved: {title}"

    @tool
    def validate_playwright_syntax(script_content: str) -> str:
        """Validate Python/Playwright script syntax."""
        import ast
        try:
            ast.parse(script_content)
            return "valid"
        except SyntaxError as exc:
            return f"syntax_error: {exc}"

    @tool
    async def decompose_requirement(requirement_text: str) -> str:
        """Decompose a requirement into discrete, ordered test steps."""
        return f"Decomposed requirement into steps — store the steps in the script draft."

    return [save_script_draft, validate_playwright_syntax, decompose_requirement]


def build_execution_tools(page: Page, memory: any, db_session: any) -> list:  # type: ignore[valid-type]
    """Build the tool set for ExecutionAgent."""
    from langchain.tools import tool

    @tool
    async def navigate_to_url(url: str) -> str:
        """Navigate the browser to a URL."""
        await page.goto(url, wait_until="networkidle")
        return f"Navigated to {url}"

    @tool
    async def click_element(selector: str) -> str:
        """Click an element by CSS selector."""
        await page.click(selector, timeout=30000)
        return f"Clicked: {selector}"

    @tool
    async def fill_input(selector: str, value: str) -> str:
        """Fill an input field."""
        await page.fill(selector, value)
        return f"Filled: {selector}"

    @tool
    async def assert_element_visible(selector: str) -> str:
        """Assert that an element is visible on the page."""
        visible = await page.is_visible(selector)
        return "passed" if visible else f"failed: element not visible: {selector}"

    @tool
    async def assert_text_contains(text: str) -> str:
        """Assert that the page contains a specific text string."""
        content = await page.inner_text("body")
        return "passed" if text in content else f"failed: text not found: {text}"

    @tool
    async def take_screenshot(step_description: str = "", step_status: str = "passed") -> str:
        """Capture a screenshot of the current state."""
        data = await page.screenshot(full_page=False)
        step_num = memory.get("current_step_index", 0)
        memory.append("raw_screenshots", {
            "step": step_num,
            "description": step_description,
            "status": step_status,
            "data": data,
        })
        return f"Screenshot captured for step {step_num}"

    @tool
    async def mark_step_passed(reason: str = "") -> str:
        """Record the current step as passed."""
        step = memory.get("current_step_index", 0)
        memory.append("passed_steps", step)
        memory.increment("current_step_index")
        return f"Step {step} passed"

    @tool
    async def mark_step_failed(reason: str) -> str:
        """Record the current step as failed with a reason."""
        step = memory.get("current_step_index", 0)
        memory.append("failed_steps", {"step": step, "reason": reason})
        memory.increment("current_step_index")
        return f"Step {step} failed: {reason}"

    return [
        navigate_to_url, click_element, fill_input,
        assert_element_visible, assert_text_contains,
        take_screenshot, mark_step_passed, mark_step_failed,
    ]
