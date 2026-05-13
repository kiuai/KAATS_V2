# ADR 003 — Agentic AI: LangChain Agents vs Fine-Tuned Models

**Status:** Accepted
**Date:** 2026-05-13
**Deciders:** Platform Architecture Team

---

## Context

KAATS requires AI to perform three complex, multi-step tasks:

1. **Crawl** — Navigate an unknown web application, discover all UI flows, and produce structured requirements. The number of pages, their structure, and the interaction patterns are entirely unknown at the time of invocation.

2. **Generate** — Take a structured requirement and produce a complete, executable test script. The output must be syntactically valid code (Playwright Python) and must cover both the happy path and edge cases.

3. **Execute** — Run a test script step-by-step, interpret UI state at each step, decide whether to continue or stop, and evaluate pass/fail based on expected outcomes.

We evaluated two approaches:

**Option A: LangChain `AgentExecutor` + Azure OpenAI GPT-4o (ReAct pattern)**
Each agent is a ReAct loop: the model reasons about the current state, selects a tool from a defined tool set, observes the result, then reasons again. The model drives the flow dynamically.

**Option B: Fine-tuned models + fixed pipeline**
Train or fine-tune a model specifically for each task type (crawl, generate, execute) on a curated dataset of test automation examples. Use a deterministic pipeline to orchestrate the steps.

---

## Decision

**Option A: LangChain `AgentExecutor` + Azure OpenAI GPT-4o with ReAct.**

All three agents are implemented as `AgentExecutor` instances with task-specific tool sets and system prompts. GPT-4o is the underlying model for all agents. No fine-tuning is performed at launch.

---

## Rationale

### Dynamic decision-making is the core requirement

Crawling an unknown web application is fundamentally a dynamic task. A fixed pipeline cannot anticipate:
- Infinite scroll vs. paginated navigation
- Single-page apps with hash routing vs. server-side rendering
- Login flows that differ across systems
- Multi-step wizard forms that require context from previous steps

A ReAct agent does not need the flow pre-programmed. It reasons from observations about what tool to call next. A fine-tuned model on a fixed pipeline would require explicit hand-coded branches for every discovered pattern — an unbounded engineering effort.

### GPT-4o quality is sufficient without fine-tuning

GPT-4o performs well on test automation tasks out of the box because:
- Training data includes large quantities of Playwright, Selenium, and Cypress code
- It can reason about HTML structure and UI element relationships without domain-specific fine-tuning
- Its instruction-following capability makes it reliable for structured output (JSON, valid Python code)

Fine-tuning would improve cost and latency but would require:
- A curated dataset of crawl/generation/execution examples — which we do not have at launch
- A periodic retraining pipeline to keep the model current with new system patterns
- A separate model endpoint, increasing operational complexity

The quality improvement from fine-tuning is not worth this overhead at launch. The decision can be revisited once we have production data for a training set.

### Tool isolation enables testing and traceability

The ReAct pattern separates reasoning (LLM call) from action (tool execution). Every tool is a Python function with a clear interface. This means:
- Each tool can be unit-tested independently
- Tool calls are logged in the Cosmos step trace — giving full observability of what the agent did and why
- A tool can be replaced or upgraded (e.g., swap `take_screenshot` for a cloud-based screenshot service) without modifying the agent prompt

A fine-tuned pipeline embeds both reasoning and action in the model weights — harder to debug, harder to change.

### LangChain reduces implementation complexity

LangChain's `AgentExecutor` provides:
- Tool definition via `@tool` decorator
- Token tracking via callbacks
- Async execution (`arun`)
- Built-in retry logic for tool failures
- Structured logging

Building this infrastructure from scratch would take weeks. LangChain provides it out of the box.

### ReAct reliability for multi-step tasks

ReAct has been validated in research and production for multi-step task completion. The pattern's interleaving of thought, action, and observation reduces hallucination compared to asking the model to plan and execute in a single call. For KAATS tasks — which require up to 200 steps in a crawl run — ReAct is the right approach.

---

## Rejected Alternatives

### Option B: Fine-tuned models

Rejected because:
1. No training dataset exists at launch
2. Dynamic task requirements cannot be fully captured in a fixed pipeline
3. Fine-tuned models degrade on out-of-distribution inputs — exactly the situation when crawling a new system type
4. Operational overhead of training pipeline is unjustified without a clear quality gap

### Function Calling without ReAct (single-step)

GPT-4o supports function calling as a single-step interaction (model calls one tool, returns result). This could theoretically replace the ReAct loop. Rejected because:
- Multi-step tasks require intermediate reasoning between tool calls
- ReAct's explicit "Thought" steps improve reliability on long tasks
- Single-step function calling does not support the sequential dependency between tools (e.g., navigate → get elements → click → screenshot)

---

## Consequences

**Positive:**
- Agents work on any web application without prior training
- Full step-level observability via Cosmos step traces
- Tools are independently testable and replaceable
- GPT-4o's capability covers all three task types with a single model

**Negative / Risks:**
- GPT-4o is more expensive than a fine-tuned smaller model. Token usage tracking and per-company rate limiting are mandatory.
- LangChain is a rapidly evolving library. Pin to `~0.2.x` minor versions and audit changes before upgrading.
- Prompt injection is a risk when the agent observes content from the crawled system (e.g., a page containing LLM instruction text). Mitigate by wrapping all tool observations in a trusted XML envelope and never concatenating raw page content directly into the system prompt.
- Non-determinism: the same crawl run on the same system may produce slightly different requirement sets. This is acceptable — requirements are reviewed before generation is triggered.
