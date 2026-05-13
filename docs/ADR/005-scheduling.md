# ADR 005 — Scheduling: In-Process asyncio Loop vs Azure Alternatives

**Status:** Accepted
**Date:** 2026-05-13
**Deciders:** Platform Architecture Team

---

## Context

KAATS needs to trigger AI agent jobs on a schedule — recurring cron expressions (e.g., crawl every Monday at 02:00) and one-shot future timestamps. The scheduling component must:

1. Evaluate which jobs are due at the current moment
2. Dispatch them to the Worker Service (via Service Bus)
3. Record each dispatch in the database
4. Handle failures: retry, escalate, auto-disable after repeated failures
5. Be reliable: a job that is due must not be silently skipped

We evaluated four approaches:

**Option A: In-process asyncio loop** — A standalone Python service (`scheduler`) runs an infinite asyncio loop. Every 60 seconds it queries Azure SQL for due jobs, enqueues them to Service Bus, and updates `next_run_at`.

**Option B: Azure Logic Apps** — Logic Apps schedules are configured per-job via the Logic Apps designer. Each job has its own Logic App flow that triggers on a recurrence schedule.

**Option C: Azure Container Apps Jobs** — Azure Container Apps Jobs supports cron-triggered jobs. Each scheduled KAATS job is mapped to a Container Apps Job with a matching cron schedule.

**Option D: AKS CronJob** — Deploy a Kubernetes cluster; each scheduled job maps to a `CronJob` resource.

---

## Decision

**Option A: In-process asyncio loop running as a dedicated Azure Container App.**

A single `scheduler` service evaluates all due `ScheduledJob` records every 60 seconds and publishes `AgentJobMessage` messages to Service Bus. The Worker Service consumes and executes these messages.

---

## Rationale

### Option B (Logic Apps) rejected

Logic Apps is a visual workflow tool optimised for integration scenarios (connecting SaaS APIs, transforming data). Using it as a scheduler introduces:

**Per-job resource model** — Each scheduled job requires its own Logic App flow. With 1000 tenants each having 5 scheduled jobs, that is 5000 Logic App resources to create, update, and delete. There is no API to create/modify Logic App flows programmatically without the ARM template/SDK — making dynamic CRUD operations on scheduled jobs complex.

**No shared state** — Each Logic App flow is isolated. Implementing failure escalation logic (increment `consecutive_failures`, auto-disable after N failures) requires writing back to SQL from within the Logic App, which adds complexity and latency.

**Cost model** — Logic Apps charges per action execution. For a high-frequency schedule (e.g., every 30 minutes × 1000 jobs), the action cost accumulates. The asyncio approach has zero per-dispatch cost beyond the Service Bus message.

**Debugging** — Logic Apps run history is stored in the Logic Apps portal with limited filtering. Our structured logging to Azure Monitor is far richer.

### Option C (Container Apps Jobs) rejected

Azure Container Apps Jobs supports cron-triggered execution, but:

**Per-job container overhead** — Each `ScheduledJob` record would require creating a Container Apps Job resource with a matching cron schedule. Dynamic creation, update, and deletion via the Azure SDK is possible but adds an Azure management-plane dependency to the application layer. A slow Azure API response would delay user operations.

**Minimum cron granularity** — Container Apps Jobs cron supports down to 1-minute intervals, which matches our requirement, but the scheduling is handled by the Azure platform. If the platform misfires or delays a job (documented behaviour: jobs may start up to 1 minute late), our SLA is affected without any recourse.

**Resource management complexity** — 1000 tenants × 5 jobs each = 5000 Container Apps Job definitions. Azure has quotas on resource counts per subscription. Staying within quota requires coordination with the infrastructure team.

**State management is still our problem** — Container Apps Jobs run our code when triggered, but the failure escalation, run history, and token usage tracking must still be implemented by us. The Job only adds a trigger layer — we get little benefit over managing the trigger ourselves.

### Option D (AKS CronJob) rejected

AKS adds full Kubernetes management overhead — node pools, upgrades, networking, RBAC — for a use case that does not require the full feature set. Our deployment target is Azure Container Apps (serverless). Introducing AKS solely for scheduling would create a split deployment model with disproportionate operational cost.

### Option A chosen

The in-process asyncio loop approach:

**Keeps scheduling logic in the application layer.** `compute_next_run()`, `consecutive_failures` tracking, auto-disable, and catch-up logic are plain Python code — readable, testable, and version-controlled alongside the rest of the application.

**`FOR UPDATE SKIP LOCKED` prevents double-firing.** If two Scheduler instances run simultaneously (e.g., during a rolling deployment), the SQL advisory lock guarantees exactly-one dispatch per due job.

**Service Bus decouples dispatch from execution.** The Scheduler only enqueues messages. If the Worker is temporarily unavailable, messages accumulate in Service Bus and are processed when the Worker recovers — no job is lost.

**Simple to operate.** The scheduler is a single Azure Container App with 0.25 CPU / 0.5 GB RAM. It runs one asyncio task. If it crashes, Container Apps restarts it within seconds. The worst case is a missed 60-second polling cycle.

**Catch-up handling is explicit.** On startup, the Scheduler queries for any jobs with `next_run_at < NOW`. It fires them immediately (up to 24 hours overdue), ensuring that a scheduler outage does not silently skip scheduled jobs.

---

## Implementation Notes

### Concurrency Safety

```sql
BEGIN TRANSACTION;

SELECT id, company_id, system_id, agent_type, cron_expression, timezone, next_run_at
FROM scheduled_jobs WITH (UPDLOCK, ROWLOCK)
WHERE is_enabled = 1
  AND next_run_at <= GETUTCDATE()
ORDER BY next_run_at ASC;

-- Process each row...

UPDATE scheduled_jobs
SET next_run_at = @computed_next,
    last_run_at = GETUTCDATE()
WHERE id = @job_id;

COMMIT;
```

The `WITH (UPDLOCK, ROWLOCK)` hint acquires update locks immediately, preventing two scheduler instances from reading the same due job simultaneously. This is equivalent to `SELECT ... FOR UPDATE SKIP LOCKED` behaviour in PostgreSQL.

### High Availability

The Scheduler runs with a minimum replica count of 1. If the single instance fails, Azure Container Apps restarts it within ~30 seconds. The maximum delay in job dispatch during a restart is 60 seconds (polling interval) + 30 seconds (restart) = ~90 seconds. This is within acceptable bounds for minute-resolution scheduling.

For stricter SLAs, the replica count can be increased to 2. The `UPDLOCK` ensures the two instances do not double-fire.

---

## Consequences

**Positive:**
- All scheduling logic is version-controlled Python — readable, testable, debuggable
- Failure escalation and run history are handled in the same codebase as the rest of KAATS
- Zero per-dispatch infrastructure cost
- Service Bus decouples dispatch from execution — no job loss during Worker downtime

**Negative / Risks:**
- The Scheduler is a single point of failure for scheduled job dispatch. Mitigated by Container Apps auto-restart and the catch-up logic.
- Polling every 60 seconds means the minimum scheduling granularity is ~1 minute. This is sufficient for KAATS use cases (no sub-minute scheduling required).
- A very large number of due jobs in a single polling cycle (e.g., many jobs set for midnight) could cause a transaction that holds update locks for several seconds. Mitigated by batching: process at most 100 jobs per polling cycle; remainder are picked up in the next cycle.
