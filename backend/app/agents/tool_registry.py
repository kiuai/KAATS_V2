from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    # Browser-based agents set these before building their tools.
    page: Any = field(default=None)           # Playwright Page
    crawl_job_id: UUID | None = field(default=None)


def build_tools(context: ToolContext) -> list[StructuredTool]:
    """Shared tools available to every agent type."""
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


# ── Crawl tools ───────────────────────────────────────────────────────────────


def build_crawl_tools(ctx: ToolContext) -> list[StructuredTool]:
    """
    Build Playwright-based crawl tools.
    ``ctx.page`` must be a live Playwright Page before calling this.
    ``ctx.crawl_job_id`` is used to update CrawlJob counters.
    """
    return [
        _make_navigate_to_url(ctx),
        _make_extract_page_elements(ctx),
        _make_classify_page_type(ctx),
        _make_take_page_screenshot(ctx),
        _make_analyze_page_with_ai(ctx),
        _make_save_crawl_page(ctx),
        _make_save_requirement(ctx),
        _make_get_unvisited_links(ctx),
        _make_handle_sap_fiori_login(ctx),
        _make_discover_sap_fiori_tiles(ctx),
        _make_launch_sap_fiori_app(ctx),
        _make_extract_sap_ui5_fields(ctx),
    ]


def _make_navigate_to_url(ctx: ToolContext) -> StructuredTool:
    async def navigate_to_url(url: str) -> str:
        """Navigate Playwright browser to URL. Return page title and HTTP status."""
        if ctx.page is None:
            return "error: browser page not available"
        if ctx.memory.in_set("visited_urls", url):
            return f"already_visited: {url}"
        try:
            response = await ctx.page.goto(url, wait_until="networkidle", timeout=30_000)
            ctx.memory.add_to_set("visited_urls", url)
            status = response.status if response else 0
            title = await ctx.page.title()
            log.debug("crawl.navigate", url=url, status=status, run_id=str(ctx.agent_run_id))
            return f"navigated: title={title!r} status={status} url={ctx.page.url!r}"
        except Exception as exc:
            log.warning("crawl.navigate_failed", url=url, error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=navigate_to_url,
        name="navigate_to_url",
        description=(
            "Navigate the browser to a URL. "
            "Returns the page title and HTTP status, or an error message. "
            "Returns 'already_visited' if the URL was previously crawled."
        ),
    )


def _make_extract_page_elements(ctx: ToolContext) -> StructuredTool:
    async def extract_page_elements() -> str:
        """
        Extract all interactive elements from the current page.
        Returns JSON with inputs, buttons, links, selects, tables, and form groups.
        """
        if ctx.page is None:
            return "error: browser page not available"
        try:
            elements = await ctx.page.evaluate("""() => {
                const origin = window.location.origin;
                const result = { inputs: [], buttons: [], links: [], selects: [], tables: [] };

                document.querySelectorAll('input:not([type=hidden])').forEach(el => {
                    const labelEl = document.querySelector('label[for="' + el.id + '"]');
                    result.inputs.push({
                        type: el.type || 'text',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: el.placeholder || '',
                        label: labelEl ? labelEl.textContent.trim() : '',
                        required: el.required
                    });
                });

                document.querySelectorAll('button, input[type=submit], input[type=button]')
                    .forEach(el => {
                        result.buttons.push({
                            text: (el.textContent || el.value || '').trim().slice(0, 80),
                            type: el.type || 'button',
                            ariaLabel: el.getAttribute('aria-label') || ''
                        });
                    });

                document.querySelectorAll('a[href]').forEach(el => {
                    if (el.href && el.href.startsWith(origin)) {
                        result.links.push({
                            href: el.href,
                            text: (el.textContent || '').trim().slice(0, 80)
                        });
                    }
                });

                document.querySelectorAll('select').forEach(el => {
                    const options = Array.from(el.options).slice(0, 5).map(o => o.text.trim());
                    result.selects.push({ name: el.name || el.id || '', options });
                });

                document.querySelectorAll('table, [role=grid]').forEach(el => {
                    const headers = Array.from(
                        el.querySelectorAll('th, [role=columnheader]')
                    ).map(h => h.textContent.trim()).slice(0, 10);
                    const rowCount = el.querySelectorAll('tr, [role=row]').length;
                    result.tables.push({ headers, rowCount });
                });

                return result;
            }""")
            return json.dumps(elements, ensure_ascii=False)[:8_000]
        except Exception as exc:
            log.warning("crawl.extract_elements_failed", error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=extract_page_elements,
        name="extract_page_elements",
        description=(
            "Extract all interactive elements from the current page. "
            "Returns JSON containing inputs, buttons, links, selects, and tables."
        ),
    )


def _make_classify_page_type(ctx: ToolContext) -> StructuredTool:
    async def classify_page_type() -> str:
        """
        Analyse current page DOM and classify as FORM | LIST | DETAIL |
        DASHBOARD | NAVIGATION | UNKNOWN with a confidence score.
        """
        if ctx.page is None:
            return "error: browser page not available"
        try:
            result = await ctx.page.evaluate("""() => {
                const formFieldCount = document.querySelectorAll(
                    'input:not([type=hidden]), select, textarea'
                ).length;
                const tableCount = document.querySelectorAll('table, [role=grid]').length;
                const chartCount = document.querySelectorAll(
                    'canvas, .chart, [class*=chart], [class*=Chart], ' +
                    '[class*=highcharts], [class*=recharts]'
                ).length;
                const navCount = document.querySelectorAll(
                    'nav, [role=navigation], .navbar, .sidebar'
                ).length;
                const h1Count = document.querySelectorAll('h1, h2').length;

                if (formFieldCount >= 3) {
                    return { type: 'FORM', confidence: Math.min(0.5 + formFieldCount * 0.08, 0.95) };
                }
                if (tableCount >= 1 && formFieldCount < 3) {
                    return { type: 'LIST', confidence: Math.min(0.6 + tableCount * 0.1, 0.95) };
                }
                if (chartCount >= 1) {
                    return { type: 'DASHBOARD', confidence: Math.min(0.65 + chartCount * 0.1, 0.95) };
                }
                if (navCount >= 2 && formFieldCount === 0 && tableCount === 0) {
                    return { type: 'NAVIGATION', confidence: 0.70 };
                }
                if (h1Count >= 1 && formFieldCount <= 1) {
                    return { type: 'DETAIL', confidence: 0.60 };
                }
                return { type: 'UNKNOWN', confidence: 0.50 };
            }""")
            return json.dumps(result)
        except Exception as exc:
            log.warning("crawl.classify_failed", error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=classify_page_type,
        name="classify_page_type",
        description=(
            "Classify the current page as FORM, LIST, DETAIL, DASHBOARD, "
            "NAVIGATION, or UNKNOWN. Returns JSON with type and confidence score."
        ),
    )


def _make_take_page_screenshot(ctx: ToolContext) -> StructuredTool:
    async def take_page_screenshot(label: str) -> str:
        """Capture a full-page screenshot, upload to Blob Storage, and return the URL."""
        if ctx.page is None:
            return "error: browser page not available"
        if ctx.blob_client is None:
            return "screenshot_skipped: blob client not available"
        try:
            png_bytes = await ctx.page.screenshot(full_page=True)
            safe_label = label.replace(" ", "_").replace("/", "_")[:80]
            blob_name = (
                f"tenant/{ctx.company_id}/crawl"
                f"/{ctx.agent_run_id}/{safe_label}.png"
            )
            container = ctx.blob_client.get_container_client("kaats-evidence")
            await container.upload_blob(
                name=blob_name,
                data=png_bytes,
                overwrite=True,
                content_settings={"content_type": "image/png"},
            )
            url = (
                f"https://{ctx.blob_client.account_name}.blob.core.windows.net"
                f"/kaats-evidence/{blob_name}"
            )
            ctx.memory.append("crawl_screenshots", {"label": label, "url": url})
            return url
        except Exception as exc:
            log.warning("crawl.screenshot_failed", label=label, error=str(exc))
            return f"screenshot_failed: {exc}"

    return StructuredTool.from_function(
        coroutine=take_page_screenshot,
        name="take_page_screenshot",
        description=(
            "Capture a full-page screenshot of the current browser page and "
            "upload it to Blob Storage. Args: label (descriptive name). "
            "Returns the blob URL or an error message."
        ),
    )


def _make_analyze_page_with_ai(ctx: ToolContext) -> StructuredTool:
    async def analyze_page_with_ai(
        page_title: str, page_type: str, elements_json: str
    ) -> str:
        """
        Call Azure OpenAI to summarise the business purpose of the page,
        identify the business process it supports, and list 1-3 testable
        requirements.  Returns JSON: {summary, business_process, requirements}.
        """
        from pydantic import BaseModel as _BM

        class _Req(_BM):
            title: str
            description: str

        class _Analysis(_BM):
            summary: str
            business_process: str
            requirements: list[_Req]

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior business analyst extracting testable requirements "
                    "from web application UI observations. Be concise and precise."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Page title: {page_title}\n"
                    f"Page classification: {page_type}\n"
                    f"UI elements (JSON): {elements_json[:3_000]}\n\n"
                    "Provide:\n"
                    "1. A 1-2 sentence summary of this page's business purpose.\n"
                    "2. The main business process it supports (e.g. 'Purchase Order Entry').\n"
                    "3. Between 1 and 3 testable business requirements implied by this page. "
                    "Each requirement must describe observable user-facing behaviour."
                ),
            },
        ]
        try:
            result = await ctx.ai_client.complete_structured(messages, _Analysis)
            return result.model_dump_json()
        except Exception as exc:
            log.warning("crawl.ai_analysis_failed", error=str(exc))
            # Fall back to plain-text completion
            try:
                plain = await ctx.ai_client.complete(messages, max_tokens=1024)
                return json.dumps({
                    "summary": plain[:500],
                    "business_process": "unknown",
                    "requirements": [],
                })
            except Exception:
                return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=analyze_page_with_ai,
        name="analyze_page_with_ai",
        description=(
            "Use AI to analyse the current page. "
            "Args: page_title (str), page_type (str), elements_json (str from "
            "extract_page_elements). "
            "Returns JSON with summary, business_process, and requirements list."
        ),
    )


def _make_save_crawl_page(ctx: ToolContext) -> StructuredTool:
    async def save_crawl_page(
        url: str,
        title: str,
        page_type: str,
        elements_json: str,
        screenshot_url: str,
        ai_summary: str,
    ) -> str:
        """Persist a CrawlPage record to the database. Returns the page ID."""
        from app.models.crawl_job import CrawlJob, CrawlPage

        try:
            elements: Any = None
            if elements_json and not elements_json.startswith("error"):
                try:
                    elements = json.loads(elements_json)
                except Exception:
                    elements = None

            page_record = CrawlPage(
                crawl_job_id=ctx.crawl_job_id,
                url=url[:2048],
                title=title[:500] if title else None,
                page_type=page_type.upper()[:50],
                ui_elements=elements,
                screenshot_blob_url=(
                    screenshot_url
                    if screenshot_url and not screenshot_url.startswith("error")
                    and not screenshot_url.startswith("screenshot_")
                    else None
                ),
                ai_summary=ai_summary[:5_000] if ai_summary else None,
                crawled_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            ctx.db.add(page_record)
            await ctx.db.flush()

            if ctx.crawl_job_id:
                job = await ctx.db.get(CrawlJob, ctx.crawl_job_id)
                if job:
                    job.pages_discovered = (job.pages_discovered or 0) + 1
                    await ctx.db.flush()

            page_id = str(page_record.id)
            ctx.memory.set("last_page_id", page_id)
            log.debug("crawl.page_saved", url=url, page_id=page_id)
            return page_id
        except Exception as exc:
            log.warning("crawl.save_page_failed", url=url, error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=save_crawl_page,
        name="save_crawl_page",
        description=(
            "Persist a crawled page to the database. "
            "Args: url, title, page_type, elements_json, screenshot_url, ai_summary. "
            "Returns the new CrawlPage ID (UUID string)."
        ),
    )


def _make_save_requirement(ctx: ToolContext) -> StructuredTool:
    async def save_requirement(
        title: str, description: str, source_page_id: str
    ) -> str:
        """Create a Requirement record linked to this crawl job. Returns the requirement ID."""
        from uuid import UUID as _UUID

        from app.models.crawl_job import CrawlJob, CrawlPage
        from app.models.enums import (
            RequirementPriority,
            RequirementSourceType,
            RequirementStatus,
        )
        from app.models.requirement import Requirement

        try:
            req = Requirement(
                system_id=ctx.system_id,
                company_id=ctx.company_id,
                title=title[:500],
                description=description,
                source_type=RequirementSourceType.CRAWL_GENERATED.value,
                source_reference=source_page_id[:500] if source_page_id else None,
                status=RequirementStatus.DRAFT.value,
                priority=RequirementPriority.MEDIUM.value,
            )
            ctx.db.add(req)
            await ctx.db.flush()

            # Link to source CrawlPage
            if source_page_id:
                try:
                    page_rec = await ctx.db.get(CrawlPage, _UUID(source_page_id))
                    if page_rec:
                        existing = page_rec.requirement_ids or []
                        page_rec.requirement_ids = existing + [str(req.id)]
                        await ctx.db.flush()
                except (ValueError, Exception):
                    pass

            # Increment CrawlJob counter
            if ctx.crawl_job_id:
                job = await ctx.db.get(CrawlJob, ctx.crawl_job_id)
                if job:
                    job.requirements_generated = (job.requirements_generated or 0) + 1
                    await ctx.db.flush()

            req_id = str(req.id)
            ctx.memory.append("crawl_requirement_ids", req_id)
            log.debug("crawl.requirement_saved", title=title[:50], req_id=req_id)
            return req_id
        except Exception as exc:
            log.warning("crawl.save_requirement_failed", title=title[:50], error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=save_requirement,
        name="save_requirement",
        description=(
            "Create a business requirement discovered during the crawl. "
            "Args: title (str), description (str), source_page_id (UUID string from "
            "save_crawl_page). Returns the new Requirement ID."
        ),
    )


def _make_get_unvisited_links(ctx: ToolContext) -> StructuredTool:
    async def get_unvisited_links(max_links: int = 10) -> str:
        """
        Return a JSON list of unvisited same-domain links from the current page.
        """
        if ctx.page is None:
            return "error: browser page not available"
        try:
            origin: str = await ctx.page.evaluate("() => window.location.origin")
            # Escape single quotes in origin to avoid JS injection
            safe_origin = origin.replace("'", "\\'")
            all_links: list[str] = await ctx.page.eval_on_selector_all(
                "a[href]",
                f"els => [...new Set(els.map(e => e.href))].filter(h => h.startsWith('{safe_origin}'))",
            )
            visited: set = ctx.memory.get("visited_urls", set())
            unvisited = [lnk for lnk in all_links if lnk not in visited]
            # Deduplicate, trim query strings that just add noise
            seen: set[str] = set()
            deduped: list[str] = []
            for lnk in unvisited:
                base = lnk.split("?")[0]
                if base not in seen:
                    seen.add(base)
                    deduped.append(lnk)
            return json.dumps(deduped[:max_links])
        except Exception as exc:
            log.warning("crawl.get_links_failed", error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=get_unvisited_links,
        name="get_unvisited_links",
        description=(
            "Return a JSON list of up to max_links unvisited in-domain hrefs "
            "found on the current page. Returns [] when crawl is complete."
        ),
    )


# ── SAP Fiori tools ───────────────────────────────────────────────────────────


def _make_handle_sap_fiori_login(ctx: ToolContext) -> StructuredTool:
    async def handle_sap_fiori_login(username: str, password: str) -> str:
        """Attempt SAP Fiori login. Returns 'success' or an error message."""
        if ctx.page is None:
            return "error: browser page not available"
        try:
            # Wait for a login field to appear (SAP logon form variations)
            username_selectors = [
                "input#USERNAME_FIELD-inner",
                "input[name=j_username]",
                "input[autocomplete=username]",
                "input[name=logonuidfield]",
            ]
            password_selectors = [
                "input#PASSWORD_FIELD-inner",
                "input[type=password]",
                "input[name=j_password]",
                "input[name=logonpassfield]",
            ]

            await ctx.page.wait_for_selector(
                ", ".join(username_selectors), timeout=10_000
            )
            await ctx.page.fill(", ".join(username_selectors), username)
            await ctx.page.fill(", ".join(password_selectors), password)

            # Click the logon button
            submit_selectors = (
                "button[type=submit], input[type=submit], "
                ".sapMBtn:has-text('Log On'), .sapMBtn:has-text('Sign In'), "
                "#LOGON_PAGE_LOGON_BUTTON"
            )
            await ctx.page.click(submit_selectors, timeout=10_000)

            # Wait for Fiori shell to load
            try:
                await ctx.page.wait_for_selector(
                    "#shell-header, .sapUshellShellHead, .sapUshellShell",
                    timeout=20_000,
                )
                log.info("crawl.sap_fiori_login_success", run_id=str(ctx.agent_run_id))
                return "success"
            except Exception:
                return "login_submitted_but_fiori_shell_not_found"
        except Exception as exc:
            log.warning("crawl.sap_fiori_login_failed", error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=handle_sap_fiori_login,
        name="handle_sap_fiori_login",
        description=(
            "Log in to a SAP Fiori system. "
            "Args: username (str), password (str). "
            "Returns 'success' or an error message."
        ),
    )


def _make_discover_sap_fiori_tiles(ctx: ToolContext) -> StructuredTool:
    async def discover_sap_fiori_tiles() -> str:
        """
        Extract all tile groups and tiles from the SAP Fiori Launchpad.
        Returns JSON: {groups: [{title, tiles: [{title, app_id, semantic_object}]}]}.
        """
        if ctx.page is None:
            return "error: browser page not available"
        try:
            await ctx.page.wait_for_selector(
                ".sapUshellTile, .sapUshellTileContainerHeader", timeout=15_000
            )
            result = await ctx.page.evaluate("""() => {
                const groups = [];
                const containers = document.querySelectorAll('.sapUshellTileContainer');
                containers.forEach(container => {
                    const titleEl = container.querySelector('.sapUshellTileContainerHeader');
                    const groupTitle = titleEl ? titleEl.textContent.trim() : 'Default';
                    const tiles = [];
                    container.querySelectorAll('.sapUshellTile').forEach(tile => {
                        const titleNode = tile.querySelector(
                            '.sapUshellTileTitle, [class*=Title], [class*=title]'
                        );
                        const tileTitle = (
                            titleNode ? titleNode.textContent.trim() :
                            tile.getAttribute('aria-label') || ''
                        ).slice(0, 120);
                        if (!tileTitle) return;
                        const appId = tile.id || tile.getAttribute('data-help-id') || '';
                        const semanticObj = tile.getAttribute('data-target-semantic-object') || '';
                        tiles.push({ title: tileTitle, app_id: appId, semantic_object: semanticObj });
                    });
                    if (tiles.length > 0) groups.push({ title: groupTitle, tiles });
                });
                return { groups };
            }""")
            ctx.memory.set("sap_tile_groups", result)
            log.info(
                "crawl.sap_tiles_discovered",
                groups=len(result.get("groups", [])),
                run_id=str(ctx.agent_run_id),
            )
            return json.dumps(result)
        except Exception as exc:
            log.warning("crawl.sap_tiles_failed", error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=discover_sap_fiori_tiles,
        name="discover_sap_fiori_tiles",
        description=(
            "Extract all tile groups and app tiles from the SAP Fiori Launchpad. "
            "Returns JSON with groups containing tile titles and semantic objects."
        ),
    )


def _make_launch_sap_fiori_app(ctx: ToolContext) -> StructuredTool:
    async def launch_sap_fiori_app(tile_title: str) -> str:
        """Click the named SAP Fiori tile and wait for the app to load. Returns the app URL."""
        if ctx.page is None:
            return "error: browser page not available"
        try:
            # Try several selector strategies
            selectors = [
                f".sapUshellTile:has-text('{tile_title}')",
                f"[aria-label='{tile_title}']",
                f"[aria-label*='{tile_title}']",
                f"[title='{tile_title}']",
            ]
            clicked = False
            for sel in selectors:
                try:
                    await ctx.page.click(sel, timeout=5_000)
                    clicked = True
                    break
                except Exception:
                    continue

            if not clicked:
                return f"error: tile '{tile_title}' not found"

            await ctx.page.wait_for_load_state("networkidle", timeout=20_000)
            current_url = ctx.page.url
            ctx.memory.add_to_set("visited_urls", current_url)
            return current_url
        except Exception as exc:
            log.warning(
                "crawl.sap_launch_app_failed", tile=tile_title, error=str(exc)
            )
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=launch_sap_fiori_app,
        name="launch_sap_fiori_app",
        description=(
            "Click the named SAP Fiori launchpad tile and wait for the app to load. "
            "Args: tile_title (str). Returns the URL of the opened app."
        ),
    )


def _make_extract_sap_ui5_fields(ctx: ToolContext) -> StructuredTool:
    async def extract_sap_ui5_fields() -> str:
        """
        Detect SAP UI5 controls via the sap.ui.getCore() JavaScript API.
        Returns a JSON list of controls with type, label, required, enabled flags.
        """
        if ctx.page is None:
            return "error: browser page not available"
        try:
            controls = await ctx.page.evaluate("""() => {
                if (typeof sap === 'undefined' || !sap.ui) return [];
                let core;
                try { core = sap.ui.getCore(); } catch (_) { return []; }
                if (!core) return [];

                const elements = core.mElements || {};
                const SUPPORTED = new Set([
                    'sap.m.Input', 'sap.m.Select', 'sap.m.DatePicker',
                    'sap.m.DateTimePicker', 'sap.m.CheckBox', 'sap.m.Button',
                    'sap.m.Table', 'sap.m.TextArea', 'sap.m.ComboBox',
                    'sap.m.MultiComboBox', 'sap.ui.comp.smartfield.SmartField',
                    'sap.ui.comp.smarttable.SmartTable',
                ]);

                const result = [];
                Object.values(elements).forEach(el => {
                    try {
                        const meta = el.getMetadata && el.getMetadata();
                        if (!meta) return;
                        const name = meta.getName && meta.getName();
                        if (!SUPPORTED.has(name)) return;
                        if (el.getVisible && !el.getVisible()) return;

                        const ctrl = {
                            type: name,
                            id: el.getId ? el.getId() : '',
                            label: (
                                (el.getLabel && el.getLabel()) ||
                                (el.getTitle && el.getTitle()) ||
                                (el.getText && el.getText()) || ''
                            ),
                            required: !!(el.getRequired && el.getRequired()),
                            enabled: el.getEnabled ? el.getEnabled() : true,
                        };

                        if (name === 'sap.m.Select' || name === 'sap.m.ComboBox' ||
                            name === 'sap.m.MultiComboBox') {
                            ctrl.items = (el.getItems ? el.getItems() : [])
                                .slice(0, 5)
                                .map(i => i.getText ? i.getText() : '');
                        }

                        if (name === 'sap.m.Table' || name === 'sap.ui.comp.smarttable.SmartTable') {
                            ctrl.columns = (el.getColumns ? el.getColumns() : [])
                                .slice(0, 10)
                                .map(c => {
                                    const h = c.getHeader ? c.getHeader() : null;
                                    return h && h.getText ? h.getText() : '';
                                });
                        }

                        result.push(ctrl);
                    } catch (_) {}
                });

                return result;
            }""")
            return json.dumps(controls, ensure_ascii=False)[:8_000]
        except Exception as exc:
            log.warning("crawl.sap_ui5_extract_failed", error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=extract_sap_ui5_fields,
        name="extract_sap_ui5_fields",
        description=(
            "Extract SAP UI5 controls from the current page using the sap.ui.getCore() API. "
            "Returns a JSON list of controls with type, label, required, and enabled flags. "
            "Use this instead of extract_page_elements for SAP Fiori apps."
        ),
    )


# ── Generation tools ──────────────────────────────────────────────────────────


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


# ── Execution tools ───────────────────────────────────────────────────────────


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
