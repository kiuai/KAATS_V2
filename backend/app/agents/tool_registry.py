from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from azure.storage.blob.aio import BlobServiceClient
from langchain.tools import StructuredTool
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.memory import AgentMemory
from app.ai.client import AzureOpenAIClient

log = structlog.get_logger(__name__)


@dataclass
class ToolContext:
    db: AsyncSession
    blob_client: BlobServiceClient | None
    company_id: UUID
    system_id: UUID
    agent_run_id: UUID
    memory: AgentMemory
    ai_client: AzureOpenAIClient


def build_tools(context: ToolContext) -> list[StructuredTool]:
    """
    Build the shared tool set available to all agent types.
    Per-agent-type tools (navigate_to_url, Playwright actions, etc.)
    are built in the individual agent classes.
    """
    return [
        _make_save_to_memory(context),
        _make_get_from_memory(context),
        _make_call_ai(context),
        _make_take_screenshot(context),
    ]


# ── Shared tool factories ─────────────────────────────────────────────────────


def _make_save_to_memory(ctx: ToolContext) -> StructuredTool:
    def save_to_memory(key: str, value: str) -> str:
        """Store a value in the agent's working memory for the current run."""
        ctx.memory.set(key, value)
        log.debug("agent.memory.set", key=key, run_id=str(ctx.agent_run_id))
        return f"Stored '{key}' in working memory."

    return StructuredTool.from_function(
        func=save_to_memory,
        name="save_to_memory",
        description=(
            "Store a string value in the agent's working memory under a given key. "
            "Useful for persisting intermediate results across tool calls."
        ),
    )


def _make_get_from_memory(ctx: ToolContext) -> StructuredTool:
    def get_from_memory(key: str) -> str:
        """Retrieve a previously stored value from agent working memory."""
        value = ctx.memory.get(key)
        if value is None:
            return f"Key '{key}' not found in memory."
        return str(value)

    return StructuredTool.from_function(
        func=get_from_memory,
        name="get_from_memory",
        description=(
            "Retrieve a value from agent working memory by key. "
            "Returns the stored string or a 'not found' message."
        ),
    )


def _make_call_ai(ctx: ToolContext) -> StructuredTool:
    async def call_ai(prompt: str, context: str = "") -> str:
        """
        Call Azure OpenAI with a prompt and optional context.
        Use this to delegate sub-tasks: decomposing requirements, generating
        edge cases, formatting output, etc.
        """
        messages: list[dict[str, str]] = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": prompt})
        try:
            return await ctx.ai_client.complete(messages, max_tokens=2048)
        except Exception as exc:
            log.warning("agent.call_ai.failed", error=str(exc))
            return f"AI call failed: {exc}"

    return StructuredTool.from_function(
        coroutine=call_ai,
        name="call_ai",
        description=(
            "Call Azure OpenAI with a prompt and optional system context. "
            "Returns the model's text response. Use for sub-tasks like "
            "decomposing requirements or generating edge cases."
        ),
    )


def _make_take_screenshot(ctx: ToolContext) -> StructuredTool:
    async def take_screenshot(label: str, page_b64: str) -> str:
        """
        Upload a base64-encoded PNG screenshot to Blob Storage.
        Returns the blob URL for later reference.
        """
        import base64

        if ctx.blob_client is None:
            return "Screenshot skipped: blob client not available."

        try:
            png_bytes = base64.b64decode(page_b64)
            blob_name = (
                f"tenant/{ctx.company_id}/evidence"
                f"/{ctx.agent_run_id}/{label.replace(' ', '_')}.png"
            )
            container_client = ctx.blob_client.get_container_client("kaats-evidence")
            await container_client.upload_blob(
                name=blob_name,
                data=png_bytes,
                overwrite=True,
                content_settings={"content_type": "image/png"},
            )
            url = (
                f"https://{ctx.blob_client.account_name}.blob.core.windows.net"
                f"/kaats-evidence/{blob_name}"
            )
            ctx.memory.append("screenshots", {"label": label, "url": url})
            return url
        except Exception as exc:
            log.warning("agent.screenshot.upload_failed", label=label, error=str(exc))
            return f"Screenshot upload failed: {exc}"

    return StructuredTool.from_function(
        coroutine=take_screenshot,
        name="take_screenshot",
        description=(
            "Upload a base64-encoded PNG screenshot to Blob Storage. "
            "Args: label (descriptive name for the step), page_b64 (base64 PNG string). "
            "Returns the blob URL."
        ),
    )


# ── Legacy builders (kept for backward compat with existing agents) ───────────

def build_crawl_tools(page: Any, memory: Any) -> list:  # type: ignore[type-arg]
    """Build Playwright-based tools for CrawlAgent. See crawl_agent.py for full impl."""
    from langchain.tools import tool

    @tool
    async def navigate_to_url(url: str) -> str:  # type: ignore[misc]
        """Navigate the browser to a URL. Returns the page title."""
        await page.goto(url, wait_until="networkidle")
        return await page.title()

    @tool
    async def get_page_title() -> str:  # type: ignore[misc]
        """Return the current page title."""
        return await page.title()

    @tool
    async def get_page_text() -> str:  # type: ignore[misc]
        """Return all visible text content of the current page."""
        return await page.inner_text("body")

    @tool
    async def get_interactive_elements() -> str:  # type: ignore[misc]
        """Return all interactive elements with labels."""
        elements = await page.query_selector_all("button, input, a, select, textarea")
        results = []
        for el in elements[:100]:
            tag = await el.evaluate("el => el.tagName")
            label = await el.get_attribute("aria-label") or await el.inner_text() or ""
            results.append(f"{tag}: {label[:80]}")
        return "\n".join(results)

    @tool
    async def click_element(selector: str) -> str:  # type: ignore[misc]
        """Click an element by CSS selector."""
        await page.click(selector)
        return f"Clicked: {selector}"

    @tool
    async def fill_input(selector: str, value: str) -> str:  # type: ignore[misc]
        """Fill an input field by CSS selector."""
        await page.fill(selector, value)
        return f"Filled {selector}"

    @tool
    async def get_navigation_links() -> str:  # type: ignore[misc]
        """Return all same-origin href links on the current page."""
        origin = "/".join(page.url.split("/")[:3])
        links = await page.eval_on_selector_all(
            "a[href]",
            f"els => els.map(e => e.href).filter(h => h.startsWith('{origin}'))",
        )
        return "\n".join(links[:200])

    @tool
    async def get_current_url() -> str:  # type: ignore[misc]
        """Return the current browser URL."""
        return page.url

    @tool
    async def check_visited(url: str) -> str:  # type: ignore[misc]
        """Check if a URL has already been crawled."""
        return str(memory.in_set("visited_urls", url))

    @tool
    async def mark_visited(url: str) -> str:  # type: ignore[misc]
        """Mark a URL as crawled in working memory."""
        memory.add_to_set("visited_urls", url)
        return f"Marked visited: {url}"

    @tool
    async def save_requirement_draft(title: str, description: str) -> str:  # type: ignore[misc]
        """Save a requirement draft to working memory."""
        memory.append("discovered_requirements", {"title": title, "description": description})
        count = len(memory.get("discovered_requirements", []))
        return f"Saved requirement draft #{count}"

    return [
        navigate_to_url, get_page_title, get_page_text, get_interactive_elements,
        click_element, fill_input, get_navigation_links, get_current_url,
        check_visited, mark_visited, save_requirement_draft,
    ]


def build_generation_tools(db_session: Any, memory: Any) -> list:  # type: ignore[type-arg]
    """Build tools for GenerationAgent."""
    from langchain.tools import tool

    @tool
    async def save_script_draft(  # type: ignore[misc]
        title: str, content: str, format: str = "playwright_python"
    ) -> str:
        """Save a generated test script draft to working memory."""
        memory.append("generated_scripts", {"title": title, "content": content, "format": format})
        return f"Script draft saved: {title}"

    @tool
    def validate_playwright_syntax(script_content: str) -> str:  # type: ignore[misc]
        """Validate Python/Playwright script syntax using ast.parse."""
        import ast
        try:
            ast.parse(script_content)
            if "playwright" not in script_content.lower() and "async" not in script_content:
                return "warning: script does not appear to use Playwright async API"
            return "valid"
        except SyntaxError as exc:
            return f"syntax_error: {exc}"

    @tool
    async def decompose_requirement(requirement_text: str) -> str:  # type: ignore[misc]
        """Decompose a requirement into discrete, ordered test steps."""
        return (
            "Use the call_ai tool to decompose this requirement: "
            f"'{requirement_text[:500]}' into numbered test steps."
        )

    return [save_script_draft, validate_playwright_syntax, decompose_requirement]


def build_execution_tools(page: Any, memory: Any, db_session: Any) -> list:  # type: ignore[type-arg]
    """Build Playwright-based tools for ExecutionAgent."""
    from langchain.tools import tool

    @tool
    async def navigate_to_url(url: str) -> str:  # type: ignore[misc]
        """Navigate the browser to a URL."""
        await page.goto(url, wait_until="networkidle")
        return f"Navigated to {url}"

    @tool
    async def click_element(selector: str) -> str:  # type: ignore[misc]
        """Click an element by CSS selector."""
        await page.click(selector, timeout=30000)
        return f"Clicked: {selector}"

    @tool
    async def fill_input(selector: str, value: str) -> str:  # type: ignore[misc]
        """Fill an input field."""
        await page.fill(selector, value)
        return f"Filled: {selector}"

    @tool
    async def assert_element_visible(selector: str) -> str:  # type: ignore[misc]
        """Assert that an element is visible on the page."""
        visible = await page.is_visible(selector)
        return "passed" if visible else f"failed: element not visible: {selector}"

    @tool
    async def assert_text_contains(text: str) -> str:  # type: ignore[misc]
        """Assert that the page contains a specific text string."""
        content = await page.inner_text("body")
        return "passed" if text in content else f"failed: text not found: {text!r}"

    @tool
    async def mark_step_passed(reason: str = "") -> str:  # type: ignore[misc]
        """Record the current step as passed."""
        step = memory.get("current_step_index", 0)
        memory.append("step_results", {"step": step, "status": "passed", "reason": reason})
        memory.increment("current_step_index")
        return f"Step {step} passed"

    @tool
    async def mark_step_failed(reason: str) -> str:  # type: ignore[misc]
        """Record the current step as failed with a reason."""
        step = memory.get("current_step_index", 0)
        memory.append("step_results", {"step": step, "status": "failed", "reason": reason})
        memory.increment("current_step_index")
        return f"Step {step} failed: {reason}"

    return [
        navigate_to_url, click_element, fill_input,
        assert_element_visible, assert_text_contains,
        mark_step_passed, mark_step_failed,
    ]
