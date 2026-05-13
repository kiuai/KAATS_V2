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


def build_generation_tools(ctx: ToolContext) -> list[StructuredTool]:
    """Build test-generation tools for GenerationAgent."""
    return [
        _make_load_requirement(ctx),
        _make_check_requirement_quality(ctx),
        _make_generate_test_cases(ctx),
        _make_format_as_playwright(ctx),
        _make_format_as_selenium(ctx),
        _make_format_as_pytest(ctx),
        _make_format_as_robot(ctx),
        _make_format_as_gherkin(ctx),
        _make_validate_script_syntax(ctx),
        _make_save_test_script(ctx),
    ]


def _make_load_requirement(ctx: ToolContext) -> StructuredTool:
    async def load_requirement(requirement_id: str) -> str:
        """Load a Requirement from the database and return it as JSON."""
        from uuid import UUID as _UUID

        from app.models.requirement import Requirement

        try:
            req_id = _UUID(requirement_id)
        except ValueError:
            return f"error: invalid UUID {requirement_id!r}"

        req = await ctx.db.get(Requirement, req_id)
        if req is None:
            return f"error: requirement {requirement_id} not found"
        if req.company_id != ctx.company_id:
            return f"error: requirement {requirement_id} not accessible"
        if req.is_deleted:
            return f"error: requirement {requirement_id} has been deleted"

        return json.dumps({
            "id": str(req.id),
            "title": req.title,
            "description": req.description,
            "source_type": req.source_type,
            "business_domain": req.business_domain or "",
            "priority": req.priority,
            "status": req.status,
            "tags": req.tags or [],
        })

    return StructuredTool.from_function(
        coroutine=load_requirement,
        name="load_requirement",
        description=(
            "Load a Requirement record from the database by UUID. "
            "Returns JSON with all fields or an error message."
        ),
    )


def _make_check_requirement_quality(ctx: ToolContext) -> StructuredTool:
    async def check_requirement_quality(requirement_json: str) -> str:
        """
        Score a requirement on completeness, testability, clarity, and atomicity.
        Returns JSON: {score, issues, suggestions, is_testable}.
        """
        from pydantic import BaseModel as _BM

        class _QualityReport(_BM):
            score: int
            issues: list[str]
            suggestions: list[str]
            is_testable: bool

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior QA analyst evaluating software requirements. "
                    "Score and analyse the given requirement."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Requirement JSON:\n{requirement_json[:3_000]}\n\n"
                    "Evaluate this requirement on four dimensions (0-25 each, total 0-100):\n"
                    "1. Completeness: Does it describe WHAT needs to happen?\n"
                    "2. Testability: Can you write a clear pass/fail test for it?\n"
                    "3. Clarity: Is it free of ambiguity and jargon?\n"
                    "4. Atomicity: Does it describe a single testable behaviour?\n\n"
                    "Return the total score, a list of issues found, "
                    "a list of improvement suggestions, and whether the requirement "
                    "is testable as-is (true/false)."
                ),
            },
        ]
        try:
            result = await ctx.ai_client.complete_structured(messages, _QualityReport)
            return result.model_dump_json()
        except Exception as exc:
            log.warning("generation.quality_check_failed", error=str(exc))
            # Fallback: assume testable so we don't block the pipeline
            return json.dumps({
                "score": 50,
                "issues": [f"Quality check failed: {exc}"],
                "suggestions": [],
                "is_testable": True,
            })

    return StructuredTool.from_function(
        coroutine=check_requirement_quality,
        name="check_requirement_quality",
        description=(
            "Score a requirement on completeness, testability, clarity, and atomicity "
            "(0-100). Returns JSON with score, issues, suggestions, and is_testable flag."
        ),
    )


def _make_generate_test_cases(ctx: ToolContext) -> StructuredTool:
    async def generate_test_cases(
        requirement_json: str, quality_report_json: str
    ) -> str:
        """
        Generate structured test cases from a requirement using AI.
        Returns a JSON object {test_cases: [...]}.
        """
        from pydantic import BaseModel as _BM
        from typing import Literal as _Lit

        from app.ai.prompts.generation_prompts import REQUIREMENT_TO_TEST_CASES_PROMPT

        class _Step(_BM):
            step_number: int
            action: str
            locator_hint: str
            input_value: str
            expected_result: str

        class _Case(_BM):
            test_case_id: str
            title: str
            description: str
            preconditions: list[str]
            test_steps: list[_Step]
            expected_outcome: str
            test_type: _Lit["positive", "negative", "boundary", "integration"]
            priority: _Lit["critical", "high", "medium", "low"]

        class _CaseList(_BM):
            test_cases: list[_Case]

        # Build system context from memory
        system_context = ctx.memory.get("system_context", "")

        user_content = (
            REQUIREMENT_TO_TEST_CASES_PROMPT
            .replace("{requirement_json}", requirement_json[:3_000])
            .replace("{quality_report_json}", quality_report_json[:1_000])
            .replace("{system_context}", system_context or "No additional context provided.")
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert software test analyst. Generate comprehensive "
                    "test cases from the given requirement. Use neutral, industry-agnostic "
                    "language. Never assume specific UI technology."
                ),
            },
            {"role": "user", "content": user_content},
        ]
        try:
            result = await ctx.ai_client.complete_structured(
                messages, _CaseList, max_tokens=4_096
            )
            return result.model_dump_json()
        except Exception as exc:
            log.warning("generation.test_cases_failed", error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=generate_test_cases,
        name="generate_test_cases",
        description=(
            "Generate structured test cases (positive, negative, boundary) from a "
            "requirement. Args: requirement_json, quality_report_json. "
            "Returns JSON {test_cases: [...]}."
        ),
    )


def _make_format_as_playwright(ctx: ToolContext) -> StructuredTool:
    async def format_as_playwright(test_cases_json: str, base_url: str) -> str:
        """Convert test cases to Playwright TypeScript (.ts). Returns complete file content."""
        from app.ai.prompts.generation_prompts import FORMAT_SYSTEM_PROMPT

        system = FORMAT_SYSTEM_PROMPT.format(format_name="Playwright TypeScript")
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Convert these test cases to Playwright TypeScript:\n\n"
                    f"Base URL: {base_url or 'Use BASE_URL env var'}\n\n"
                    f"Test cases:\n{test_cases_json[:6_000]}\n\n"
                    "Requirements:\n"
                    "- Import from '@playwright/test'\n"
                    "- Use `const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';`\n"
                    "- Use role-based locators (getByRole, getByLabel) over CSS selectors\n"
                    "- Use test.describe() to group test cases for the same requirement\n"
                    "- Each test case becomes a separate test() block\n"
                    "- Add await expect() assertions after each major action\n"
                    "- Output ONLY the TypeScript file content"
                ),
            },
        ]
        try:
            return await ctx.ai_client.complete(messages, max_tokens=4_096)
        except Exception as exc:
            log.warning("generation.format_playwright_failed", error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=format_as_playwright,
        name="format_as_playwright",
        description=(
            "Convert test cases JSON to Playwright TypeScript. "
            "Args: test_cases_json, base_url. Returns complete .ts file content."
        ),
    )


def _make_format_as_selenium(ctx: ToolContext) -> StructuredTool:
    async def format_as_selenium(test_cases_json: str, base_url: str) -> str:
        """Convert test cases to Selenium Python (pytest-selenium). Returns .py file content."""
        from app.ai.prompts.generation_prompts import FORMAT_SYSTEM_PROMPT

        system = FORMAT_SYSTEM_PROMPT.format(format_name="Selenium Python (pytest-selenium)")
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Convert these test cases to Selenium Python with pytest:\n\n"
                    f"Base URL: {base_url or 'Use BASE_URL env var'}\n\n"
                    f"Test cases:\n{test_cases_json[:6_000]}\n\n"
                    "Requirements:\n"
                    "- Import: pytest, selenium.webdriver, By, WebDriverWait, "
                    "expected_conditions as EC, os\n"
                    "- Use `BASE_URL = os.environ.get('BASE_URL', 'http://localhost:3000')`\n"
                    "- Provide a @pytest.fixture for the WebDriver\n"
                    "- Use explicit waits (WebDriverWait) not time.sleep\n"
                    "- Group test cases in a class, one method per test case\n"
                    "- Output ONLY the Python file content"
                ),
            },
        ]
        try:
            return await ctx.ai_client.complete(messages, max_tokens=4_096)
        except Exception as exc:
            log.warning("generation.format_selenium_failed", error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=format_as_selenium,
        name="format_as_selenium",
        description=(
            "Convert test cases JSON to Selenium Python (pytest-selenium). "
            "Args: test_cases_json, base_url. Returns complete .py file content."
        ),
    )


def _make_format_as_pytest(ctx: ToolContext) -> StructuredTool:
    async def format_as_pytest(test_cases_json: str, base_url: str) -> str:
        """Convert test cases to pure pytest. Returns .py file content."""
        from app.ai.prompts.generation_prompts import FORMAT_SYSTEM_PROMPT

        system = FORMAT_SYSTEM_PROMPT.format(format_name="pytest")
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Convert these test cases to pytest (no UI automation framework):\n\n"
                    f"Base URL: {base_url or 'Use BASE_URL env var'}\n\n"
                    f"Test cases:\n{test_cases_json[:6_000]}\n\n"
                    "Requirements:\n"
                    "- Import pytest, requests, os\n"
                    "- Use `BASE_URL = os.environ.get('BASE_URL', 'http://localhost:3000')`\n"
                    "- Where UI interaction is implied, add a comment '# UI action: ...' "
                    "and assert the HTTP response or state change\n"
                    "- Use pytest.mark.parametrize for boundary/data-driven cases\n"
                    "- Output ONLY the Python file content"
                ),
            },
        ]
        try:
            return await ctx.ai_client.complete(messages, max_tokens=4_096)
        except Exception as exc:
            log.warning("generation.format_pytest_failed", error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=format_as_pytest,
        name="format_as_pytest",
        description=(
            "Convert test cases JSON to pure pytest. "
            "Args: test_cases_json, base_url. Returns complete .py file content."
        ),
    )


def _make_format_as_robot(ctx: ToolContext) -> StructuredTool:
    async def format_as_robot(test_cases_json: str, base_url: str) -> str:
        """Convert test cases to Robot Framework. Returns .robot file content."""
        from app.ai.prompts.generation_prompts import FORMAT_SYSTEM_PROMPT

        system = FORMAT_SYSTEM_PROMPT.format(format_name="Robot Framework")
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Convert these test cases to Robot Framework (.robot):\n\n"
                    f"Base URL: {base_url or 'Use BASE_URL env var'}\n\n"
                    f"Test cases:\n{test_cases_json[:6_000]}\n\n"
                    "Requirements:\n"
                    "- Include *** Settings ***, *** Variables ***, *** Test Cases ***, "
                    "*** Keywords *** sections\n"
                    "- Use SeleniumLibrary\n"
                    "- Define ${BASE_URL} in *** Variables *** as %{BASE_URL=http://localhost:3000}\n"
                    "- Create reusable keywords for common actions\n"
                    "- Each test case becomes a Robot test case\n"
                    "- Output ONLY the .robot file content"
                ),
            },
        ]
        try:
            return await ctx.ai_client.complete(messages, max_tokens=4_096)
        except Exception as exc:
            log.warning("generation.format_robot_failed", error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=format_as_robot,
        name="format_as_robot",
        description=(
            "Convert test cases JSON to Robot Framework. "
            "Args: test_cases_json, base_url. Returns complete .robot file content."
        ),
    )


def _make_format_as_gherkin(ctx: ToolContext) -> StructuredTool:
    async def format_as_gherkin(test_cases_json: str, base_url: str) -> str:
        """Convert test cases to Gherkin .feature file. Returns .feature file content."""
        from app.ai.prompts.generation_prompts import FORMAT_SYSTEM_PROMPT

        system = FORMAT_SYSTEM_PROMPT.format(format_name="Gherkin (BDD)")
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Convert these test cases to a Gherkin .feature file:\n\n"
                    f"Base URL context: {base_url or 'N/A'}\n\n"
                    f"Test cases:\n{test_cases_json[:6_000]}\n\n"
                    "Requirements:\n"
                    "- Start with a Feature: block with a brief description\n"
                    "- Use a Background: block for common preconditions\n"
                    "- Each positive test case → Scenario\n"
                    "- Data-driven/boundary cases → Scenario Outline with Examples table\n"
                    "- Steps must use Given/When/Then/And/But keywords\n"
                    "- Use neutral business language throughout\n"
                    "- Output ONLY the .feature file content"
                ),
            },
        ]
        try:
            return await ctx.ai_client.complete(messages, max_tokens=4_096)
        except Exception as exc:
            log.warning("generation.format_gherkin_failed", error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=format_as_gherkin,
        name="format_as_gherkin",
        description=(
            "Convert test cases JSON to a Gherkin .feature file with Scenario Outline "
            "where applicable. Args: test_cases_json, base_url. Returns .feature content."
        ),
    )


def _make_validate_script_syntax(ctx: ToolContext) -> StructuredTool:
    def validate_script_syntax(script_content: str, format: str) -> str:
        """
        Validate a generated script for syntax errors.
        Returns JSON: {valid: bool, errors: [str]}.
        """
        import ast
        import subprocess
        import tempfile
        import os

        errors: list[str] = []
        fmt = format.lower().replace("-", "_").replace(" ", "_")

        if fmt in ("pytest", "selenium"):
            try:
                ast.parse(script_content)
            except SyntaxError as exc:
                errors.append(f"SyntaxError at line {exc.lineno}: {exc.msg}")

        elif fmt == "playwright":
            # Try TypeScript compiler if available
            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".ts", mode="w", delete=False, encoding="utf-8"
                ) as f:
                    f.write(script_content)
                    tmppath = f.name
                result = subprocess.run(
                    ["tsc", "--noEmit", "--target", "ES2020",
                     "--lib", "ES2020,DOM", tmppath],
                    capture_output=True, text=True, timeout=30,
                )
                os.unlink(tmppath)
                if result.returncode != 0:
                    raw = (result.stdout + result.stderr).strip()
                    errors.extend(raw.splitlines()[:10])
            except FileNotFoundError:
                # tsc not on PATH — do lightweight structural check
                for required in ("import", "test(", "expect("):
                    if required not in script_content:
                        errors.append(
                            f"warning: generated file may not be valid Playwright TS "
                            f"(missing '{required}')"
                        )
            except subprocess.TimeoutExpired:
                errors.append("tsc validation timed out")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"tsc check error: {exc}")

        elif fmt == "robot_framework":
            for section in ("*** Test Cases ***", "*** Settings ***"):
                if section not in script_content:
                    errors.append(f"Missing required Robot Framework section: {section}")

        elif fmt == "gherkin":
            for keyword in ("Feature:", "Scenario"):
                if keyword not in script_content:
                    errors.append(f"Missing required Gherkin keyword: {keyword}")
            for step_kw in ("Given", "When", "Then"):
                if step_kw not in script_content:
                    errors.append(f"Missing BDD step keyword: {step_kw}")

        valid = len(errors) == 0
        if not valid:
            log.debug(
                "generation.validation_failed",
                format=fmt,
                error_count=len(errors),
                run_id=str(ctx.agent_run_id),
            )
        return json.dumps({"valid": valid, "errors": errors})

    return StructuredTool.from_function(
        func=validate_script_syntax,
        name="validate_script_syntax",
        description=(
            "Validate generated script syntax. "
            "Args: script_content (str), format ('playwright'|'selenium'|'pytest'|"
            "'robot_framework'|'gherkin'). "
            "Returns JSON {valid: bool, errors: [str]}."
        ),
    )


def _make_save_test_script(ctx: ToolContext) -> StructuredTool:
    async def save_test_script(
        requirement_id: str,
        title: str,
        test_cases_json: str,
        rendered_content: str,
        export_format: str,
    ) -> str:
        """
        Persist a TestScript with its TestCase and TestStep records.
        Returns the new script ID (UUID string).
        """
        from uuid import UUID as _UUID

        from app.config import get_settings
        from app.models.enums import ExportFormat, TestScriptStatus
        from app.models.test_script import TestCase, TestScript, TestStep

        settings = get_settings()

        # Parse test cases
        test_cases: list[dict] = []
        try:
            data = json.loads(test_cases_json)
            if isinstance(data, dict):
                test_cases = data.get("test_cases", [])
            elif isinstance(data, list):
                test_cases = data
        except Exception:
            pass

        # Map format string to ExportFormat enum value
        fmt_map: dict[str, str] = {
            "playwright": ExportFormat.PLAYWRIGHT.value,
            "playwright_typescript": ExportFormat.PLAYWRIGHT.value,
            "selenium": ExportFormat.SELENIUM.value,
            "pytest": ExportFormat.PYTEST.value,
            "robot_framework": ExportFormat.ROBOT_FRAMEWORK.value,
            "gherkin": ExportFormat.GHERKIN.value,
            "manual_steps": ExportFormat.MANUAL_STEPS.value,
        }
        db_format = fmt_map.get(export_format.lower(), ExportFormat.PLAYWRIGHT.value)

        req_id: _UUID | None = None
        if requirement_id:
            try:
                req_id = _UUID(requirement_id)
            except ValueError:
                pass

        user_id_str: str | None = ctx.memory.get("triggered_by_user_id")
        created_by: _UUID | None = None
        if user_id_str:
            try:
                created_by = _UUID(user_id_str)
            except ValueError:
                pass

        try:
            script = TestScript(
                requirement_id=req_id,
                system_id=ctx.system_id,
                company_id=ctx.company_id,
                title=title[:500],
                script_content=test_cases_json[:65_000],
                rendered_content=rendered_content[:65_000],
                export_format=db_format,
                ai_generated=True,
                ai_model_version=settings.azure_openai_deployment_name,
                status=TestScriptStatus.DRAFT.value,
                created_by=created_by,
            )
            ctx.db.add(script)
            await ctx.db.flush()

            # Persist structured TestCase + TestStep records
            for i, tc in enumerate(test_cases):
                if not isinstance(tc, dict):
                    continue
                case = TestCase(
                    script_id=script.id,
                    name=tc.get("title", f"Test Case {i + 1}")[:500],
                    description=tc.get("description", ""),
                    order_index=i,
                )
                ctx.db.add(case)
                await ctx.db.flush()

                for step_data in tc.get("test_steps", []):
                    if not isinstance(step_data, dict):
                        continue
                    hint = step_data.get("locator_hint", "")
                    value = step_data.get("input_value", "")
                    detail = " — ".join(filter(None, [hint, value])) or step_data.get("action", "")
                    step = TestStep(
                        case_id=case.id,
                        step_number=step_data.get("step_number", 0),
                        action=step_data.get("action", "action")[:100],
                        description=detail[:2_000],
                        expected_outcome=step_data.get("expected_result"),
                        parameters=(
                            {"locator_hint": hint, "input_value": value}
                            if hint or value
                            else None
                        ),
                    )
                    ctx.db.add(step)

                await ctx.db.flush()

            script_id = str(script.id)
            ctx.memory.append("generated_script_ids", script_id)
            ctx.memory.increment("scripts_generated_count")
            log.info(
                "generation.script_saved",
                script_id=script_id,
                format=db_format,
                test_case_count=len(test_cases),
            )
            return script_id
        except Exception as exc:
            log.warning("generation.save_script_failed", title=title[:50], error=str(exc))
            return f"error: {exc}"

    return StructuredTool.from_function(
        coroutine=save_test_script,
        name="save_test_script",
        description=(
            "Persist a generated test script to the database with all its test cases "
            "and steps. Args: requirement_id, title, test_cases_json, rendered_content, "
            "export_format. Returns the new TestScript ID."
        ),
    )


# ── Execution tools ───────────────────────────────────────────────────────────


def build_execution_tools(ctx: ToolContext) -> list[StructuredTool]:
    """
    Build full Playwright-based execution tools for ExecutionAgent.
    ``ctx.page`` must be a live Playwright Page before calling this.
    """
    return [
        _make_load_test_script(ctx),
        _make_create_execution_run(ctx),
        _make_browser_navigate(ctx),
        _make_browser_click(ctx),
        _make_browser_fill(ctx),
        _make_browser_select(ctx),
        _make_browser_assert_visible(ctx),
        _make_browser_assert_text(ctx),
        _make_browser_assert_url(ctx),
        _make_browser_wait(ctx),
        _make_browser_wait_for_element(ctx),
        _make_take_step_screenshot(ctx),
        _make_save_step_result(ctx),
        _make_finalize_execution_run(ctx),
        _make_generate_evidence_report(ctx),
        _make_create_test_result(ctx),
    ]


# ── Load test script ──────────────────────────────────────────────────────────


def _make_load_test_script(ctx: ToolContext) -> StructuredTool:
    async def load_test_script(script_id: str) -> str:
        """Load TestScript from DB with all test cases and steps. Returns JSON."""
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select as sa_select
        from app.models.test_script import TestScript, TestCase, TestStep

        try:
            sid = UUID(script_id)
        except ValueError:
            return f"error: invalid script_id '{script_id}'"

        stmt = (
            sa_select(TestScript)
            .where(TestScript.id == sid)
            .options(
                selectinload(TestScript.cases).selectinload(TestCase.steps)
            )
        )
        result = await ctx.db.execute(stmt)
        script = result.scalar_one_or_none()
        if script is None:
            return f"error: TestScript {script_id} not found"

        payload = {
            "script_id": str(script.id),
            "title": script.title,
            "description": script.description,
            "export_format": script.export_format,
            "system_id": str(script.system_id),
            "test_cases": [
                {
                    "case_id": str(case.id),
                    "name": case.name,
                    "description": case.description,
                    "stop_on_failure": case.stop_on_failure,
                    "order_index": case.order_index,
                    "steps": [
                        {
                            "step_id": str(step.id),
                            "step_number": step.step_number,
                            "action": step.action,
                            "description": step.description,
                            "expected_outcome": step.expected_outcome or "",
                            "parameters": step.parameters or {},
                        }
                        for step in sorted(case.steps, key=lambda s: s.step_number)
                    ],
                }
                for case in sorted(script.cases, key=lambda c: c.order_index)
            ],
        }
        ctx.memory.set(f"script_{script_id}", json.dumps(payload))
        return json.dumps(payload)

    return StructuredTool.from_function(
        coroutine=load_test_script,
        name="load_test_script",
        description=(
            "Load a TestScript from the database including all test cases and steps. "
            "Returns JSON with the full script structure. "
            "Also stores the script in working memory under 'script_{script_id}'."
        ),
    )


# ── Create execution run ──────────────────────────────────────────────────────


def _make_create_execution_run(ctx: ToolContext) -> StructuredTool:
    async def create_execution_run(script_id: str) -> str:
        """Create an ExecutionRun record with status=RUNNING. Returns run_id."""
        from app.models.execution_evidence import ExecutionRun
        from app.models.enums import ExecutionStatus

        try:
            sid = UUID(script_id)
        except ValueError:
            return f"error: invalid script_id '{script_id}'"

        run = ExecutionRun(
            agent_run_id=ctx.agent_run_id,
            test_script_id=sid,
            company_id=ctx.company_id,
            status=ExecutionStatus.RUNNING.value,
        )
        ctx.db.add(run)
        await ctx.db.flush()

        run_id = str(run.id)
        # Track all run_ids created in this agent run
        existing: list[str] = ctx.memory.get("execution_run_ids") or []
        existing.append(run_id)
        ctx.memory.set("execution_run_ids", existing)
        ctx.memory.set(f"run_id_for_script_{script_id}", run_id)

        log.info("execution.run_created", run_id=run_id, script_id=script_id)
        return json.dumps({"run_id": run_id, "status": "running"})

    return StructuredTool.from_function(
        coroutine=create_execution_run,
        name="create_execution_run",
        description=(
            "Create a new ExecutionRun record (status=RUNNING) for a TestScript. "
            "Returns JSON with 'run_id'. Must be called before save_step_result."
        ),
    )


# ── Browser interaction tools ─────────────────────────────────────────────────


def _make_browser_navigate(ctx: ToolContext) -> StructuredTool:
    async def browser_navigate(url: str) -> str:
        """Navigate to URL. Returns title and HTTP status."""
        if ctx.page is None:
            return "error: browser page not available"
        try:
            response = await ctx.page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            status = response.status if response else 0
            title = await ctx.page.title()
            return json.dumps({"success": True, "title": title, "status_code": status, "url": ctx.page.url})
        except Exception as exc:
            return json.dumps({"success": False, "title": "", "status_code": 0, "error_message": str(exc)})

    return StructuredTool.from_function(
        coroutine=browser_navigate,
        name="browser_navigate",
        description="Navigate the browser to a URL. Returns JSON: {success, title, status_code}.",
    )


def _make_browser_click(ctx: ToolContext) -> StructuredTool:
    async def browser_click(locator: str, description: str = "") -> str:
        """
        Click element using multi-strategy: CSS → XPath → aria-label → visible text.
        Returns JSON: {success, element_found, error_message}.
        """
        if ctx.page is None:
            return json.dumps({"success": False, "element_found": False, "error_message": "no browser"})

        strategies = [
            ("css", locator),
            ("xpath", f"xpath={locator}" if not locator.startswith("xpath=") else locator),
            ("aria", f"[aria-label='{locator}']"),
            ("text", f"text={locator}"),
            ("role", f"role=button[name='{locator}']"),
        ]

        for strategy_name, sel in strategies:
            try:
                el = ctx.page.locator(sel).first
                count = await el.count()
                if count > 0:
                    await el.click(timeout=10_000)
                    log.debug("execution.click", strategy=strategy_name, locator=locator)
                    return json.dumps({"success": True, "element_found": True, "error_message": ""})
            except Exception:
                continue

        return json.dumps({
            "success": False,
            "element_found": False,
            "error_message": f"Element not found with any strategy: {locator!r}",
        })

    return StructuredTool.from_function(
        coroutine=browser_click,
        name="browser_click",
        description=(
            "Click an element. Tries CSS selector, XPath, aria-label, and visible text. "
            "Returns JSON: {success, element_found, error_message}."
        ),
    )


def _make_browser_fill(ctx: ToolContext) -> StructuredTool:
    async def browser_fill(locator: str, value: str, description: str = "") -> str:
        """Clear and fill an input field. Returns JSON: {success, error_message}."""
        if ctx.page is None:
            return json.dumps({"success": False, "error_message": "no browser"})
        try:
            el = ctx.page.locator(locator).first
            await el.fill(value, timeout=10_000)
            return json.dumps({"success": True, "error_message": ""})
        except Exception as exc:
            return json.dumps({"success": False, "error_message": str(exc)})

    return StructuredTool.from_function(
        coroutine=browser_fill,
        name="browser_fill",
        description="Clear and fill a form input field. Returns JSON: {success, error_message}.",
    )


def _make_browser_select(ctx: ToolContext) -> StructuredTool:
    async def browser_select(locator: str, option_text: str, description: str = "") -> str:
        """Select dropdown option by visible text. Returns JSON: {success, error_message}."""
        if ctx.page is None:
            return json.dumps({"success": False, "error_message": "no browser"})
        try:
            await ctx.page.locator(locator).select_option(label=option_text, timeout=10_000)
            return json.dumps({"success": True, "error_message": ""})
        except Exception as exc:
            return json.dumps({"success": False, "error_message": str(exc)})

    return StructuredTool.from_function(
        coroutine=browser_select,
        name="browser_select",
        description="Select a dropdown option by its visible text. Returns JSON: {success, error_message}.",
    )


def _make_browser_assert_visible(ctx: ToolContext) -> StructuredTool:
    async def browser_assert_visible(locator: str, description: str = "") -> str:
        """Assert element is visible on page. Returns JSON: {passed, error_message}."""
        if ctx.page is None:
            return json.dumps({"passed": False, "error_message": "no browser"})
        try:
            visible = await ctx.page.locator(locator).first.is_visible()
            if visible:
                return json.dumps({"passed": True, "error_message": ""})
            return json.dumps({"passed": False, "error_message": f"Element not visible: {locator!r}"})
        except Exception as exc:
            return json.dumps({"passed": False, "error_message": str(exc)})

    return StructuredTool.from_function(
        coroutine=browser_assert_visible,
        name="browser_assert_visible",
        description="Assert an element is visible. Returns JSON: {passed, error_message}.",
    )


def _make_browser_assert_text(ctx: ToolContext) -> StructuredTool:
    async def browser_assert_text(locator: str, expected_text: str, description: str = "") -> str:
        """Assert element contains expected_text (partial match). Returns JSON: {passed, actual_text, error_message}."""
        if ctx.page is None:
            return json.dumps({"passed": False, "actual_text": "", "error_message": "no browser"})
        try:
            el = ctx.page.locator(locator).first
            actual = await el.inner_text(timeout=10_000)
            passed = expected_text.lower() in actual.lower()
            return json.dumps({
                "passed": passed,
                "actual_text": actual[:500],
                "error_message": "" if passed else f"Expected {expected_text!r} not found in {actual[:200]!r}",
            })
        except Exception as exc:
            return json.dumps({"passed": False, "actual_text": "", "error_message": str(exc)})

    return StructuredTool.from_function(
        coroutine=browser_assert_text,
        name="browser_assert_text",
        description="Assert element contains expected text (partial match). Returns JSON: {passed, actual_text, error_message}.",
    )


def _make_browser_assert_url(ctx: ToolContext) -> StructuredTool:
    async def browser_assert_url(expected_pattern: str) -> str:
        """Assert current URL contains expected_pattern. Returns JSON: {passed, actual_url}."""
        if ctx.page is None:
            return json.dumps({"passed": False, "actual_url": ""})
        actual = ctx.page.url
        passed = expected_pattern.lower() in actual.lower()
        return json.dumps({"passed": passed, "actual_url": actual})

    return StructuredTool.from_function(
        coroutine=browser_assert_url,
        name="browser_assert_url",
        description="Assert current URL contains the expected pattern. Returns JSON: {passed, actual_url}.",
    )


def _make_browser_wait(ctx: ToolContext) -> StructuredTool:
    async def browser_wait(milliseconds: int) -> str:
        """Wait for specified time. Returns 'waited: Nms'."""
        import asyncio
        ms = max(0, min(milliseconds, 10_000))  # cap at 10 s
        await asyncio.sleep(ms / 1000)
        return f"waited: {ms}ms"

    return StructuredTool.from_function(
        coroutine=browser_wait,
        name="browser_wait",
        description="Wait for specified milliseconds (max 10 000). Use sparingly — prefer browser_wait_for_element.",
    )


def _make_browser_wait_for_element(ctx: ToolContext) -> StructuredTool:
    async def browser_wait_for_element(locator: str, timeout_ms: int = 10_000) -> str:
        """Wait until element appears. Returns JSON: {appeared, timeout_reached}."""
        if ctx.page is None:
            return json.dumps({"appeared": False, "timeout_reached": True})
        try:
            await ctx.page.locator(locator).first.wait_for(
                state="visible", timeout=min(timeout_ms, 30_000)
            )
            return json.dumps({"appeared": True, "timeout_reached": False})
        except Exception:
            return json.dumps({"appeared": False, "timeout_reached": True})

    return StructuredTool.from_function(
        coroutine=browser_wait_for_element,
        name="browser_wait_for_element",
        description="Wait until element is visible. Returns JSON: {appeared, timeout_reached}.",
    )


# ── Screenshot + evidence tools ───────────────────────────────────────────────


def _make_take_step_screenshot(ctx: ToolContext) -> StructuredTool:
    async def take_step_screenshot(
        step_number: int,
        step_description: str,
        outcome: str,
    ) -> str:
        """
        Capture full-page screenshot, annotate with Pillow, upload to Blob.
        Returns blob URL (or empty string on failure).
        """
        from app.agents.screenshot_annotator import get_annotator
        from app.blob import upload_bytes, build_evidence_path

        run_id = ctx.memory.get("current_execution_run_id") or str(ctx.agent_run_id)

        # Capture screenshot from Playwright
        raw_bytes: bytes = b""
        if ctx.page is not None:
            try:
                raw_bytes = await ctx.page.screenshot(full_page=True, timeout=15_000)
            except Exception as exc:
                log.warning("execution.screenshot_failed", error=str(exc), step=step_number)

        if not raw_bytes:
            # Produce a minimal 1×1 placeholder so we always have something
            from PIL import Image as _PILImage
            import io as _io
            img = _PILImage.new("RGB", (1920, 1080), color=(200, 200, 200))
            buf = _io.BytesIO()
            img.save(buf, format="PNG")
            raw_bytes = buf.getvalue()

        # Annotate
        try:
            annotated = get_annotator().annotate(
                image_bytes=raw_bytes,
                step_number=step_number,
                description=step_description,
                outcome=outcome,
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as exc:
            log.warning("execution.annotation_failed", error=str(exc))
            annotated = raw_bytes

        # Upload to Blob
        blob_path = build_evidence_path(
            str(ctx.company_id),
            run_id,
            f"step_{step_number:03d}.png",
        )
        if ctx.blob_client is not None:
            try:
                await upload_bytes(blob_path, annotated, content_type="image/png")
                settings_url = (
                    f"https://{ctx.blob_client.account_name}.blob.core.windows.net"
                    f"/kaats-evidence/{blob_path}"
                )
                ctx.memory.append(
                    "step_screenshots",
                    {"step": step_number, "url": settings_url, "blob_path": blob_path},
                )
                log.debug("execution.screenshot_uploaded", step=step_number, path=blob_path)
                return settings_url
            except Exception as exc:
                log.warning("execution.screenshot_upload_failed", error=str(exc), step=step_number)

        return blob_path  # Return path even if blob upload failed

    return StructuredTool.from_function(
        coroutine=take_step_screenshot,
        name="take_step_screenshot",
        description=(
            "Capture a full-page screenshot, annotate it with step metadata and outcome, "
            "and upload to Blob Storage. "
            "Args: step_number (int), step_description (str), outcome ('passed'|'failed'|'blocked'|'error'). "
            "Returns the blob URL."
        ),
    )


def _make_save_step_result(ctx: ToolContext) -> StructuredTool:
    async def save_step_result(
        execution_run_id: str,
        step_number: int,
        step_description: str,
        action: str,
        expected_result: str,
        actual_result: str,
        outcome: str,
        screenshot_url: str,
        duration_ms: int = 0,
    ) -> str:
        """Persist ExecutionStepResult record. Returns step_result_id."""
        from app.models.execution_evidence import ExecutionStepResult

        try:
            run_uuid = UUID(execution_run_id)
        except ValueError:
            return f"error: invalid execution_run_id '{execution_run_id}'"

        step_result = ExecutionStepResult(
            execution_run_id=run_uuid,
            step_number=step_number,
            step_description=step_description[:2000],
            action=action[:100],
            expected_result=expected_result[:4000],
            actual_result=(actual_result or "")[:4000],
            outcome=outcome,
            screenshot_blob_url=screenshot_url[:2048] if screenshot_url else None,
            duration_ms=max(0, duration_ms),
        )
        ctx.db.add(step_result)
        await ctx.db.flush()

        result_id = str(step_result.id)
        ctx.memory.append("saved_step_result_ids", result_id)
        return json.dumps({"step_result_id": result_id, "outcome": outcome})

    return StructuredTool.from_function(
        coroutine=save_step_result,
        name="save_step_result",
        description=(
            "Persist an ExecutionStepResult to the database. "
            "Args: execution_run_id, step_number, step_description, action, "
            "expected_result, actual_result, outcome, screenshot_url, duration_ms. "
            "Returns JSON with step_result_id."
        ),
    )


def _make_finalize_execution_run(ctx: ToolContext) -> StructuredTool:
    async def finalize_execution_run(execution_run_id: str) -> str:
        """Calculate totals, set status, set completed_at. Returns summary JSON."""
        from sqlalchemy import select as sa_select
        from app.models.execution_evidence import ExecutionRun, ExecutionStepResult
        from app.models.enums import ExecutionStatus, StepOutcome

        try:
            run_uuid = UUID(execution_run_id)
        except ValueError:
            return f"error: invalid execution_run_id '{execution_run_id}'"

        run = await ctx.db.get(ExecutionRun, run_uuid)
        if run is None:
            return f"error: ExecutionRun {execution_run_id} not found"

        # Count step results
        result = await ctx.db.execute(
            sa_select(ExecutionStepResult).where(
                ExecutionStepResult.execution_run_id == run_uuid
            )
        )
        steps = result.scalars().all()
        total = len(steps)
        passed = sum(1 for s in steps if s.outcome == StepOutcome.PASSED.value)
        failed = sum(1 for s in steps if s.outcome == StepOutcome.FAILED.value)
        blocked = sum(1 for s in steps if s.outcome == StepOutcome.BLOCKED.value)

        # Determine overall status
        if failed > 0 or total == 0:
            status = ExecutionStatus.FAILED.value
        elif blocked > 0:
            status = ExecutionStatus.FAILED.value
        else:
            status = ExecutionStatus.PASSED.value

        run.status = status
        run.total_steps = total
        run.passed_steps = passed
        run.failed_steps = failed
        run.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await ctx.db.flush()

        summary = {
            "execution_run_id": execution_run_id,
            "status": status,
            "total_steps": total,
            "passed_steps": passed,
            "failed_steps": failed,
            "blocked_steps": blocked,
        }
        log.info("execution.run_finalized", **summary)
        return json.dumps(summary)

    return StructuredTool.from_function(
        coroutine=finalize_execution_run,
        name="finalize_execution_run",
        description=(
            "Calculate totals for all step results and update ExecutionRun status "
            "(PASSED if all steps pass, FAILED otherwise). "
            "Sets completed_at timestamp. Returns summary JSON."
        ),
    )


def _make_generate_evidence_report(ctx: ToolContext) -> StructuredTool:
    async def generate_evidence_report(execution_run_id: str) -> str:
        """
        Build a PDF evidence report with reportlab and upload to Blob.
        Returns PDF blob URL.
        """
        from sqlalchemy import select as sa_select
        from sqlalchemy.orm import selectinload
        from app.models.execution_evidence import ExecutionRun, ExecutionStepResult
        from app.models.test_script import TestScript
        from app.blob import upload_bytes, build_evidence_path, download_bytes
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            Image as RLImage, PageBreak, HRFlowable,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        import io as _io

        try:
            run_uuid = UUID(execution_run_id)
        except ValueError:
            return f"error: invalid execution_run_id '{execution_run_id}'"

        run = await ctx.db.get(ExecutionRun, run_uuid)
        if run is None:
            return f"error: ExecutionRun {execution_run_id} not found"

        # Load step results ordered by step_number
        sr_result = await ctx.db.execute(
            sa_select(ExecutionStepResult)
            .where(ExecutionStepResult.execution_run_id == run_uuid)
            .order_by(ExecutionStepResult.step_number)
        )
        steps: list[ExecutionStepResult] = list(sr_result.scalars().all())

        # Load script title
        script = await ctx.db.get(TestScript, run.test_script_id)
        script_title = script.title if script else f"Script {run.test_script_id}"

        # ── Build PDF in memory ───────────────────────────────────────────────
        buf = _io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
            title="Evidence Report",
            author="KAATS",
        )

        styles = getSampleStyleSheet()
        _PAGE_W = A4[0] - 4 * cm

        # Custom styles
        h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=20, spaceAfter=6,
                             textColor=colors.HexColor("#1e3a5f"), alignment=TA_CENTER)
        h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=14, spaceAfter=4,
                             textColor=colors.HexColor("#1e3a5f"))
        body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, spaceAfter=4)
        label = ParagraphStyle("Label", parent=styles["Normal"], fontSize=9,
                               textColor=colors.HexColor("#6b7280"))
        mono = ParagraphStyle("Mono", parent=styles["Normal"], fontSize=9,
                              fontName="Courier", spaceAfter=4, backColor=colors.HexColor("#f3f4f6"))

        def outcome_colour(o: str) -> colors.Color:
            mapping = {
                "passed": colors.HexColor("#22c55e"),
                "failed": colors.HexColor("#ef4444"),
                "blocked": colors.HexColor("#f97316"),
                "error": colors.HexColor("#ef4444"),
            }
            return mapping.get(o.lower(), colors.grey)

        exec_date = (run.completed_at or run.started_at).strftime("%Y-%m-%d %H:%M UTC")
        overall = run.status.upper()
        overall_c = outcome_colour(run.status)

        story: list = []

        # ── Cover page ────────────────────────────────────────────────────────
        story.append(Spacer(1, 3 * cm))
        story.append(Paragraph("KAATS — Evidence Report", h1))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1e3a5f")))
        story.append(Spacer(1, 0.5 * cm))

        cover_data = [
            ["Script:", script_title],
            ["Execution Date:", exec_date],
            ["Execution Run ID:", execution_run_id],
            ["Overall Outcome:", overall],
        ]
        cover_table = Table(cover_data, colWidths=[4 * cm, _PAGE_W - 4 * cm])
        cover_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (1, 3), (1, 3), overall_c),
            ("FONTNAME", (1, 3), (1, 3), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(cover_table)
        story.append(Spacer(1, 1 * cm))

        # ── Summary table ─────────────────────────────────────────────────────
        story.append(Paragraph("Execution Summary", h2))
        summary_data = [
            ["Total Steps", "Passed", "Failed", "Blocked"],
            [
                str(run.total_steps),
                str(run.passed_steps),
                str(run.failed_steps),
                str(run.total_steps - run.passed_steps - run.failed_steps),
            ],
        ]
        sum_table = Table(summary_data, colWidths=[_PAGE_W / 4] * 4)
        sum_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, 1), [colors.HexColor("#f9fafb")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (1, 1), (1, 1), colors.HexColor("#22c55e")),
            ("TEXTCOLOR", (2, 1), (2, 1), colors.HexColor("#ef4444")),
            ("TEXTCOLOR", (3, 1), (3, 1), colors.HexColor("#f97316")),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ]))
        story.append(sum_table)
        story.append(PageBreak())

        # ── Per-step pages ────────────────────────────────────────────────────
        for step in steps:
            oc = step.outcome
            oc_colour = outcome_colour(oc)

            story.append(Paragraph(
                f"Step {step.step_number:03d} — {step.step_description}", h2
            ))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
            story.append(Spacer(1, 0.2 * cm))

            # Step metadata table
            meta = [
                ["Action:", step.action],
                ["Expected:", step.expected_result or "—"],
                ["Actual:", step.actual_result or "—"],
                ["Duration:", f"{step.duration_ms} ms"],
            ]
            meta_table = Table(meta, colWidths=[3 * cm, _PAGE_W - 3 * cm])
            meta_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(meta_table)
            story.append(Spacer(1, 0.3 * cm))

            # Outcome badge
            badge_data = [[f"  {oc.upper()}  "]]
            badge = Table(badge_data, colWidths=[3 * cm])
            badge.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), oc_colour),
                ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
                ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (0, 0), 11),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("TOPPADDING", (0, 0), (0, 0), 6),
                ("BOTTOMPADDING", (0, 0), (0, 0), 6),
                ("ROUNDEDCORNERS", [3, 3, 3, 3]),
            ]))
            story.append(badge)
            story.append(Spacer(1, 0.4 * cm))

            # Error message if present
            if step.error_message:
                story.append(Paragraph("Error:", label))
                story.append(Paragraph(step.error_message[:500], mono))
                story.append(Spacer(1, 0.2 * cm))

            # Screenshot
            if step.screenshot_blob_url and ctx.blob_client is not None:
                try:
                    # Extract blob path from full URL
                    blob_path = step.screenshot_blob_url
                    if "/kaats-evidence/" in blob_path:
                        blob_path = blob_path.split("/kaats-evidence/", 1)[1].split("?")[0]
                    img_bytes = await download_bytes(blob_path)
                    img_stream = _io.BytesIO(img_bytes)
                    # Scale to fit page width
                    from PIL import Image as _PILImage
                    pil_img = _PILImage.open(_io.BytesIO(img_bytes))
                    orig_w, orig_h = pil_img.size
                    scale = min(_PAGE_W / orig_w, 18 * cm / orig_h)
                    rl_img = RLImage(img_stream, width=orig_w * scale, height=orig_h * scale)
                    story.append(rl_img)
                except Exception as exc:
                    story.append(Paragraph(f"[Screenshot unavailable: {exc}]", body))
            else:
                story.append(Paragraph("[No screenshot captured]", body))

            story.append(PageBreak())

        # Build PDF
        doc.build(story)
        pdf_bytes = buf.getvalue()

        # Upload PDF
        pdf_blob_path = build_evidence_path(
            str(ctx.company_id),
            execution_run_id,
            "evidence_report.pdf",
        )
        pdf_url = ""
        if ctx.blob_client is not None:
            try:
                await upload_bytes(pdf_blob_path, pdf_bytes, content_type="application/pdf")
                pdf_url = (
                    f"https://{ctx.blob_client.account_name}.blob.core.windows.net"
                    f"/kaats-evidence/{pdf_blob_path}"
                )
                # Update ExecutionRun record
                run.evidence_pdf_blob_url = pdf_url
                await ctx.db.flush()
                log.info("execution.report_generated", run_id=execution_run_id, path=pdf_blob_path)
            except Exception as exc:
                log.warning("execution.report_upload_failed", error=str(exc))
                pdf_url = f"local:{pdf_blob_path}"

        # Track report URLs in memory
        existing_reports: list[str] = ctx.memory.get("report_urls") or []
        existing_reports.append(pdf_url)
        ctx.memory.set("report_urls", existing_reports)

        return json.dumps({"report_url": pdf_url, "size_bytes": len(pdf_bytes)})

    return StructuredTool.from_function(
        coroutine=generate_evidence_report,
        name="generate_evidence_report",
        description=(
            "Build a professional PDF evidence report for an ExecutionRun using reportlab. "
            "Includes cover page, summary table, and per-step pages with screenshots. "
            "Uploads the PDF to Blob Storage and updates the ExecutionRun record. "
            "Returns JSON with 'report_url'."
        ),
    )


def _make_create_test_result(ctx: ToolContext) -> StructuredTool:
    async def create_test_result(
        assignment_id: str,
        execution_run_id: str,
        outcome: str,
        notes: str = "",
    ) -> str:
        """
        Create or update a TestResult linking this execution to a test cycle assignment.
        Returns result_id.
        """
        from app.models.test_result import TestResult
        from sqlalchemy import select as sa_select

        try:
            assign_uuid = UUID(assignment_id)
            run_uuid = UUID(execution_run_id)
        except ValueError as exc:
            return f"error: invalid UUID — {exc}"

        # Load the execution run to get test_script_id
        from app.models.execution_evidence import ExecutionRun
        run = await ctx.db.get(ExecutionRun, run_uuid)
        if run is None:
            return f"error: ExecutionRun {execution_run_id} not found"

        # Check for existing result for this assignment
        existing = await ctx.db.execute(
            sa_select(TestResult).where(TestResult.assignment_id == assign_uuid)
        )
        test_result = existing.scalar_one_or_none()
        now_dt = datetime.now(timezone.utc).replace(tzinfo=None)

        triggered_by_str = ctx.memory.get("triggered_by_user_id")
        user_uuid: Any = UUID(triggered_by_str) if triggered_by_str else ctx.agent_run_id

        if test_result is None:
            test_result = TestResult(
                assignment_id=assign_uuid,
                test_script_id=run.test_script_id,
                company_id=ctx.company_id,
                executed_by=user_uuid,
                execution_agent_run_id=ctx.agent_run_id,
                executed_at=now_dt,
                outcome=outcome,
                notes=notes[:2000] if notes else None,
            )
            ctx.db.add(test_result)
        else:
            test_result.outcome = outcome
            test_result.notes = notes[:2000] if notes else None
            test_result.executed_at = now_dt
            test_result.execution_agent_run_id = ctx.agent_run_id

        await ctx.db.flush()
        return json.dumps({"result_id": str(test_result.id), "outcome": outcome})

    return StructuredTool.from_function(
        coroutine=create_test_result,
        name="create_test_result",
        description=(
            "Create or update a TestResult linking an ExecutionRun to a test cycle assignment. "
            "Args: assignment_id (UUID), execution_run_id (UUID), outcome (str), notes (str). "
            "Returns JSON with result_id."
        ),
    )
