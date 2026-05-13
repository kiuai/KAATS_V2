# ADR 002 — Multi-Tenancy Strategy

**Status:** Accepted
**Date:** 2026-05-13
**Deciders:** Platform Architecture Team

---

## Context

KAATS is a multi-tenant SaaS platform. Multiple companies — potentially thousands — will store test data, agent runs, and evidence on the same infrastructure. We must choose how to isolate tenant data to prevent cross-tenant leakage, while keeping infrastructure costs and operational complexity manageable.

The three classical approaches are:

1. **Silo** — one database instance per tenant
2. **Pool** — one shared database, `company_id` column on every table, enforced in application code
3. **Pool + RLS** — one shared database, `company_id` column, enforced at the database engine level via Row-Level Security

For non-relational stores (Cosmos DB, Blob Storage), similar tradeoffs apply.

---

## Decision

**Pool + RLS for Azure SQL.** A single Azure SQL database is shared across all tenants. Every tenant-scoped table has a `company_id` column. Row-Level Security (RLS) is enforced at the database engine level using `SESSION_CONTEXT(N'tenant_id')`.

**Logical namespace isolation for Blob Storage.** All evidence artifacts are stored under `tenant-{company_id}/` path prefixes. The API service has write access to all prefixes but scopes every read/write to the caller's `company_id`. SAS URLs are generated per-blob with a 1-hour TTL — clients cannot enumerate other tenants' containers.

**Logical container isolation for Cosmos DB.** Agent run documents are stored in a single `agent-runs` Cosmos container with `company_id` as the partition key. All queries include a `company_id` filter that maps to the partition key, ensuring all reads and writes are physically isolated at the partition level.

**Shared Service Bus with message-level tenant tagging.** All agent job messages include `company_id` in the application properties. Workers validate the `company_id` claim before processing.

---

## Rationale

### Why not Silo?

Silo isolation (one database per tenant) provides the strongest isolation but:
- Azure SQL costs per instance are significant; 1000 tenants = 1000 instances
- Schema migrations require coordinated rollout across all tenant databases
- Monitoring, backups, and alerting multiply in complexity linearly with tenant count
- Connection pool exhaustion becomes a real problem: 1000 database connections × N connection pool size

Silo is appropriate for enterprise on-premise deployments where a single customer controls the infrastructure. It is not appropriate for a SaaS platform with many small-to-medium tenants.

### Why Pool + RLS over Pool alone?

Pure pool isolation (application-layer `WHERE company_id = ?` on every query) is vulnerable to:
- A developer forgetting to add the filter on a new query
- A bug in the middleware that sets the wrong `company_id`
- A SQL injection that bypasses the application filter

RLS adds a second enforcement layer at the database engine. Even if the application layer fails to filter, the database will not return rows from the wrong tenant. This is a defence-in-depth measure aligned with the principle of least privilege.

### Why not per-tenant Cosmos DB containers?

Cosmos DB charges per container for provisioned throughput (RU/s). A separate container per tenant would require per-container provisioning, making the cost model unpredictable for small tenants. The partition-key approach uses a single container with serverless or shared throughput, keeping costs low while maintaining physical isolation at the partition level.

---

## Implementation Details

### SESSION_CONTEXT Approach

On every SQL connection acquisition (via SQLAlchemy pool event), the application sets:

```sql
EXEC sp_set_session_context @key = N'tenant_id', @value = '{company_id_as_string}', @read_only = 1;
```

The `@read_only = 1` flag prevents the application from overriding the context within the same connection, adding a further guarantee.

The RLS security policy predicate function:

```sql
CREATE FUNCTION dbo.fn_tenant_predicate(@company_id UNIQUEIDENTIFIER)
RETURNS TABLE WITH SCHEMABINDING AS
RETURN SELECT 1 AS result
WHERE CAST(SESSION_CONTEXT(N'tenant_id') AS UNIQUEIDENTIFIER) = @company_id;
```

This function is applied as a FILTER PREDICATE on all tenant-scoped tables. All SELECT, UPDATE, DELETE statements are automatically filtered. INSERT is validated via a BLOCK PREDICATE.

### Middleware Stack

1. `AuthMiddleware` — validates JWT, extracts `user_id` and `company_id` from claims
2. `TenantMiddleware` — calls `sp_set_session_context` on connection checkout; stores `company_id` in `request.state`
3. All downstream code reads `request.state.company_id` — never from the request body

### Blob Storage Scoping

The API service uses a single Blob Storage account with a single container (`kaats-evidence`). Path prefixes enforce logical isolation:

```
kaats-evidence/tenant-{company_id}/evidence/{execution_id}/
```

SAS URL generation is scoped to the exact blob path requested. The service validates that the path prefix matches the caller's `company_id` before generating the SAS.

### Cosmos DB Scoping

All Cosmos queries include:
```
WHERE c.company_id = @company_id
```

Because `company_id` is the partition key, this query is always a single-partition read — both efficient and isolated.

---

## Consequences

**Positive:**
- Single database to manage, migrate, monitor, and back up
- RLS adds a hard database-level guarantee independent of application code
- Low infrastructure cost at launch; scales with tenant count without per-tenant provisioning
- Schema migrations run once, applied to all tenants simultaneously

**Negative / Risks:**
- Noisy-neighbour risk: a single large tenant running many concurrent agent jobs could consume disproportionate SQL compute. Mitigated by per-company rate limiting at the API layer and Elastic Pool configuration.
- RLS adds a small query plan overhead (~2–5% for simple queries). Acceptable for this workload.
- A bug in the `SESSION_CONTEXT` middleware that sets the wrong `company_id` would be a critical security incident. Must be covered by integration tests that run two tenants simultaneously and assert zero cross-contamination.
