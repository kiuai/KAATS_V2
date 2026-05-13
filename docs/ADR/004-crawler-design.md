# ADR 004 — Crawler Design

**Status:** Accepted
**Date:** 2026-05-13
**Deciders:** Platform Architecture Team

---

## Context

The `CrawlAgent` must navigate a live web application to discover all significant UI flows and produce structured requirements. The core design question is: **how should the agent traverse the application?**

We evaluated three traversal strategies:

1. **AI-directed free exploration** — The LLM decides what to do next at every step with no structural guidance. The agent is given a start URL and told to "explore the application and document all flows."

2. **BFS (Breadth-First Search) with AI annotation** — The agent follows a BFS algorithm to enumerate all same-origin pages. At each page, the LLM is called to annotate the UI flows it finds. Navigation decisions follow the BFS queue, not the LLM's whim.

3. **Sitemap-seeded crawl** — Parse `robots.txt` and `sitemap.xml` first, then use those URLs as the BFS seed set.

---

## Decision

**BFS with AI annotation** (Option 2), with **sitemap seeding as an optional enhancement** (Option 3 as an add-on).

The crawler uses a deterministic BFS queue to enumerate all same-origin URLs. At each page, the LLM annotates the UI flows, interactive elements, and pre/post-conditions. URL discovery is done by extracting all `<a href>` links from the page — not by asking the LLM to guess what URLs exist.

---

## Rationale

### Why BFS over AI-directed free exploration?

AI-directed free exploration is appealing because it mirrors how a human QA analyst might explore an app. However:

**Completeness** — A free-exploring agent will naturally gravitate toward familiar patterns and may miss entire sections of the application that are reachable but not prominently linked from the main navigation. BFS guarantees that every same-origin URL the agent encounters will be visited (subject to `max_pages`).

**Reproducibility** — The same application crawled twice with free exploration may produce very different requirement sets depending on the LLM's non-deterministic choices. BFS produces a more consistent coverage result.

**Loop avoidance** — A free-exploring agent can get stuck in cycles (visit A → visit B → visit A again) unless given explicit visited-URL tracking. BFS with a visited set handles this deterministically.

**Cost efficiency** — Free exploration wastes tokens asking the LLM "where should I go next?" BFS eliminates this decision cost. The LLM is used only for annotation (the task that genuinely requires intelligence), not for navigation decisions.

### Why BFS over sitemap-only?

Sitemap-only crawling misses:
- Dynamic routes generated client-side (React Router, Vue Router) that are not in `sitemap.xml`
- Authenticated pages that sitemaps don't index
- Forms and wizard flows that exist as a single URL with multiple states

BFS discovers these because it follows all `<a href>` links in the rendered DOM after JavaScript execution (Playwright renders the full SPA before extracting links).

Sitemap parsing is added as an optional enhancement: if `sitemap.xml` is found, its URLs are added to the BFS seed set to accelerate discovery, but BFS continues regardless.

### AI annotation is where the LLM adds value

The LLM is invoked once per page to:
- Identify the purpose of the page
- List all interactive elements with their roles
- Describe pre-conditions (what state must be true to reach this page)
- Describe post-conditions (what happens after the primary action)
- Draft a structured `Requirement` record

This is a task that requires semantic understanding of UI — the LLM excels here. It is also a bounded task (one page at a time) that produces a structured output, making it easy to validate.

---

## BFS Algorithm Details

```
Input: system.base_url, crawl_config
Output: list of Requirement records

1. Initialize queue = [base_url], visited = {}, requirements = []
2. While queue not empty and pages_visited < max_pages:
   a. Dequeue next_url
   b. If next_url in visited: skip
   c. Mark next_url as visited
   d. Navigate to next_url (Playwright)
   e. Wait for network idle (Playwright auto-wait)
   f. Call LLM to annotate current page → requirement_draft
   g. Append requirement_draft to requirements
   h. Extract all same-origin <a href> links from DOM
   i. Filter links:
      - Remove already-visited URLs
      - Remove URLs matching crawl_config.exclude_patterns
      - Remove non-HTML resources (.pdf, .zip, .png, .jpg, etc.)
      - Keep only same-origin URLs
   j. Enqueue filtered links (deduped)
   k. Save checkpoint every 10 pages
3. Flush all requirements to SQL
```

### URL Filtering Rules

| Rule | Reason |
|---|---|
| Same-origin only | Avoid crawling external sites |
| Exclude file downloads | Not UI flows |
| Exclude auth callbacks (`/callback`, `/oauth2/redirect`) | Not content pages |
| Exclude `crawl_config.exclude_patterns` | Admin-configured per system |
| Skip query-string variants of visited paths | Reduce duplicate content |

---

## Playwright Configuration for Crawling

- **Headless**: yes
- **Viewport**: 1920×1080
- **Wait strategy**: `networkidle` (wait until no network requests for 500ms)
- **JavaScript**: enabled (required for SPA routing)
- **Context isolation**: new browser context per crawl run (no cookies carried across systems)
- **Auth injection**: credentials from `system.auth_config` are injected via Playwright's `storageState` or a pre-authentication step before BFS begins

---

## Consequences

**Positive:**
- Deterministic, reproducible coverage
- No wasted tokens on navigation decisions
- Handles SPAs correctly (Playwright renders full JS)
- Simple to reason about, debug, and extend

**Negative / Risks:**
- BFS may visit more pages than necessary for large applications. `max_pages` (default: 200) limits this; Company Admins can configure it per system.
- Applications with client-side-only routing (no `<a href>` links — e.g., button-driven navigation) may not be fully discovered by BFS alone. The agent can use the `click_element` tool to trigger navigations if the LLM annotation identifies navigation elements.
- Infinite scroll and paginated lists may generate many near-duplicate URLs. The URL filtering rules deduplicate by path (ignoring query strings for page/offset parameters).
