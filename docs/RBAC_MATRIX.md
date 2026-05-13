# KAATS — RBAC Matrix

Version: 1.0 | Status: Authoritative

---

## 1. Role Definitions

| Role | Code | Scope | Description |
|---|---|---|---|
| Platform Admin | `platform_admin` | Global | Manages all tenants, billing, platform configuration |
| Enterprise Admin | `enterprise_admin` | Enterprise | Manages companies and users within one enterprise |
| Company Admin | `company_admin` | Company | Manages systems, users, and settings within one company |
| System Manager | `system_manager` | System | Owns one or more systems; configures crawl scope and credentials |
| QA Engineer | `qa_engineer` | Company | Runs agents, reviews results, downloads evidence |
| Viewer | `viewer` | Company | Read-only access to results and evidence |

Roles are non-hierarchical in code. A user may hold multiple roles (e.g., `company_admin` + `system_manager`). Every role check is explicit; no implicit inheritance.

---

## 2. Permission Matrix

### 2.1 Platform Administration

| Feature | platform_admin | enterprise_admin | company_admin | system_manager | qa_engineer | viewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Create / delete enterprise | ✅ | — | — | — | — | — |
| Update enterprise settings | ✅ | ✅ | — | — | — | — |
| View all enterprises | ✅ | — | — | — | — | — |
| Manage platform feature flags | ✅ | — | — | — | — | — |
| View platform token usage (all tenants) | ✅ | — | — | — | — | — |
| Manage billing plans | ✅ | — | — | — | — | — |

### 2.2 Enterprise Management

| Feature | platform_admin | enterprise_admin | company_admin | system_manager | qa_engineer | viewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Create / delete company | ✅ | ✅ | — | — | — | — |
| Update company settings | ✅ | ✅ | ✅ | — | — | — |
| View companies in enterprise | ✅ | ✅ | ✅* | — | — | — |
| Invite enterprise-level user | ✅ | ✅ | — | — | — | — |
| View enterprise token usage | ✅ | ✅ | — | — | — | — |

*Company Admin sees only their own company.

### 2.3 User Management

| Feature | platform_admin | enterprise_admin | company_admin | system_manager | qa_engineer | viewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Invite user to company | ✅ | ✅ | ✅ | — | — | — |
| Remove user from company | ✅ | ✅ | ✅ | — | — | — |
| Assign / change role | ✅ | ✅ | ✅ | — | — | — |
| View company user list | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Update own profile | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### 2.4 System Management

| Feature | platform_admin | enterprise_admin | company_admin | system_manager | qa_engineer | viewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Create system | ✅ | ✅ | ✅ | — | — | — |
| Delete system | ✅ | ✅ | ✅ | — | — | — |
| Update system config (URL, auth, scope) | ✅ | ✅ | ✅ | ✅ | — | — |
| Store system credentials | ✅ | ✅ | ✅ | ✅ | — | — |
| View system details | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View all systems in company | ✅ | ✅ | ✅ | ✅* | ✅ | ✅ |

*System Manager sees only systems they own.

### 2.5 Requirements

| Feature | platform_admin | enterprise_admin | company_admin | system_manager | qa_engineer | viewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| View requirements | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Create requirement manually | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Edit requirement | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Delete requirement | ✅ | ✅ | ✅ | ✅ | — | — |
| Approve requirement | ✅ | ✅ | ✅ | ✅ | — | — |
| Export requirements | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### 2.6 Test Scripts

| Feature | platform_admin | enterprise_admin | company_admin | system_manager | qa_engineer | viewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| View test scripts | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Create / edit test script manually | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Delete test script | ✅ | ✅ | ✅ | ✅ | — | — |
| Approve test script | ✅ | ✅ | ✅ | ✅ | — | — |
| Export test script (all formats) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### 2.7 Agent Invocation

| Feature | platform_admin | enterprise_admin | company_admin | system_manager | qa_engineer | viewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Trigger CrawlAgent (on-demand) | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Trigger GenerationAgent (on-demand) | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Trigger ExecutionAgent (on-demand) | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Cancel running agent | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| View agent run status | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View agent run step trace | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View token usage (company level) | ✅ | ✅ | ✅ | ✅ | — | — |

### 2.8 Scheduling

| Feature | platform_admin | enterprise_admin | company_admin | system_manager | qa_engineer | viewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Create scheduled job | ✅ | ✅ | ✅ | ✅ | — | — |
| Edit scheduled job | ✅ | ✅ | ✅ | ✅ | — | — |
| Delete scheduled job | ✅ | ✅ | ✅ | ✅ | — | — |
| Enable / disable scheduled job | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Trigger scheduled job manually | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| View scheduled jobs | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View scheduled job run history | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### 2.9 Test Executions

| Feature | platform_admin | enterprise_admin | company_admin | system_manager | qa_engineer | viewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| View execution list | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View execution step results | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Re-run execution | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Archive / delete execution | ✅ | ✅ | ✅ | ✅ | — | — |

### 2.10 Evidence

| Feature | platform_admin | enterprise_admin | company_admin | system_manager | qa_engineer | viewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| View evidence screenshots | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Download evidence PDF report | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Verify evidence integrity | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Delete evidence | ✅ | ✅ | ✅ | ✅ | — | — |

### 2.11 Reporting and Analytics

| Feature | platform_admin | enterprise_admin | company_admin | system_manager | qa_engineer | viewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| View project summary report | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View script coverage report | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View token usage report (company) | ✅ | ✅ | ✅ | ✅ | — | — |
| View token usage report (enterprise) | ✅ | ✅ | — | — | — | — |
| View token usage report (global) | ✅ | — | — | — | — | — |
| Export reports (CSV / PDF) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 3. Enforcement Model

### JWT Claims
Every API request carries an Entra ID JWT. The following claims are extracted at the middleware layer:

| Claim | Field | Description |
|---|---|---|
| `sub` | `user_id` | Unique user identifier |
| `kaats_company_id` | `company_id` | Active company (set at login) |
| `kaats_enterprise_id` | `enterprise_id` | Parent enterprise |
| `kaats_roles` | `roles[]` | List of role codes |

### Middleware Stack
1. **`AuthMiddleware`** — validates JWT signature and expiry; rejects 401 if invalid.
2. **`TenantMiddleware`** — extracts `company_id`, sets `SESSION_CONTEXT(N'tenant_id')` on SQL connection.
3. **`RBACDependency`** — FastAPI dependency injected into each route; checks required role(s) against JWT claims; raises 403 if insufficient.

### Route Declaration Example
```python
@router.post("/systems/{system_id}/agents/crawl")
async def trigger_crawl(
    system_id: UUID,
    payload: CrawlRequest,
    _: None = Depends(require_roles(["qa_engineer", "system_manager", "company_admin"])),
    db: AsyncSession = Depends(get_db),
):
    ...
```

### Resource-Level Scoping
In addition to role checks, every database query is implicitly filtered by `company_id` via RLS. A `system_manager` cannot access systems outside their own company even if they manipulate the request.

---

## 4. Role Assignment Constraints

| Rule | Enforced by |
|---|---|
| A user cannot assign a role higher than their own | `RBACDependency` service layer check |
| A `company_admin` can only assign roles within their company | Scoped by `company_id` in assignment endpoint |
| `platform_admin` is assigned only via the admin CLI tool (never via API) | No API endpoint exists for `platform_admin` grant |
| A user may hold at most one role per company (except `platform_admin` which is global) | Unique constraint on `(user_id, company_id, role)` in SQL |
