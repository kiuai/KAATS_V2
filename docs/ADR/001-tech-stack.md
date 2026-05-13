# ADR 001 — Technology Stack

**Status:** Accepted
**Date:** 2026-05-13
**Deciders:** Platform Architecture Team

---

## Context

KAATS is a new, greenfield multi-tenant SaaS platform. We need to choose the full technology stack for:
- Backend API
- Async worker/agent runtime
- Frontend SPA
- Relational data store
- Document/trace store
- Binary artifact store
- Async messaging
- Browser automation (for agent execution)
- Identity and authentication

Constraints:
- Azure deployment target (customer preference; key services already on Azure)
- Python expertise in the team for AI/agent work
- Must support production-grade async I/O for high agent concurrency
- No vendor lock-in for compute; container-based deployment required
- Timeline: production-ready in one development cycle

---

## Decision

| Layer | Technology | Version |
|---|---|---|
| Backend framework | FastAPI | 0.111+ |
| Language (backend) | Python | 3.12 |
| ORM | SQLAlchemy (async) | 2.0+ |
| SQL driver | aioodbc | latest |
| AI/agent SDK | LangChain + LangChain-Community | 0.2.x |
| LLM provider | Azure OpenAI (GPT-4o) | — |
| Browser automation | Playwright (async Python) | 1.44+ |
| Frontend framework | React | 18 |
| Frontend bundler | Vite | 5 |
| Frontend language | TypeScript | 5.4+ |
| Relational store | Azure SQL Database | Standard S3 |
| Document store | Azure Cosmos DB | Core API (NoSQL) |
| Object/blob store | Azure Blob Storage | LRS |
| Async messaging | Azure Service Bus | Standard tier |
| Image annotation | Pillow | 10+ |
| PDF generation | reportlab | 4+ |
| Scheduler utility | croniter | 1.4+ |
| Token budget | tiktoken | 0.7+ |
| Auth provider | Microsoft Entra ID | — |
| Container runtime | Docker + Azure Container Apps | — |
| CI/CD | GitHub Actions | — |
| Container registry | Azure Container Registry | — |

---

## Rationale

### FastAPI over Django / Flask
FastAPI provides native async support, automatic OpenAPI schema generation from type hints, and a dependency injection model well-suited for per-request tenant context. Django's synchronous-first model would require significant workarounds for high-concurrency agent workloads. Flask lacks type-driven schema generation.

### SQLAlchemy 2.0 async over raw queries
SQLAlchemy 2.0's async session model works natively with aioodbc and Azure SQL. The declarative mapping approach makes multi-table relationships clear and maintainable. Raw queries would require manual connection lifecycle management and offer no abstraction for RLS session context.

### Azure SQL over PostgreSQL or Cosmos DB (for relational data)
The customer base includes enterprises already standardised on Azure SQL. Azure SQL's Row-Level Security implementation is mature and well-documented. It also supports the SKIP LOCKED clause needed by the scheduler. Cosmos DB is unsuitable for relational queries and transactions.

### Cosmos DB for agent run documents
Agent step traces are append-heavy, variable-schema, and need sub-second write latency. They are queried by `run_id` and `company_id` — both fit the partition key model. A SQL table for step traces would grow to billions of rows and require frequent schema migrations as the agent evolves.

### Azure Service Bus over RabbitMQ / Redis Pub-Sub
Service Bus is a managed service with zero operational overhead on Azure. It provides at-least-once delivery semantics, dead-letter queues, and topic/subscription filtering — all required. Redis Pub-Sub lacks persistence. RabbitMQ would require self-managed infrastructure.

### Playwright over Selenium for browser automation
Playwright's async Python API integrates naturally with the asyncio-based agent runtime. It is more reliable on modern single-page applications than Selenium (auto-waits, network interception). The async API allows multiple browser contexts to run concurrently in the same worker process.

### React 18 + Vite + TypeScript over Next.js / Angular
The frontend is primarily a dashboard and monitoring UI — no server-side rendering requirement. React 18 with Vite provides a fast development experience and a small production bundle. TypeScript ensures type safety for API response types shared with the backend's OpenAPI schema.

---

## Consequences

**Positive:**
- Fully async backend aligns with high-concurrency agent workloads
- Azure-native services reduce operational overhead
- LangChain's tool abstraction makes it straightforward to add new agent tools without touching the core agent loop
- OpenAPI schema generated automatically from FastAPI — frontend types can be generated from it

**Negative / Risks:**
- LangChain is a fast-moving library; pin minor versions and review changelogs on each upgrade
- Azure SQL ODBC driver (aioodbc) has less community support than asyncpg; some edge cases in async connection pooling need careful handling
- Pillow + reportlab add ~50 MB to the worker container image; acceptable given the container build pipeline
