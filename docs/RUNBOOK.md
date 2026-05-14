# KAATS Runbook

Operational reference for on-call engineers. Covers alerts, diagnosis steps,
and recovery procedures for the KAATS production environment (Azure Container
Apps + SQL Server + Cosmos DB + Service Bus).

---

## Table of contents

1. [Service map](#1-service-map)
2. [Health checks](#2-health-checks)
3. [Alert reference](#3-alert-reference)
4. [Common failure scenarios](#4-common-failure-scenarios)
5. [Secrets rotation](#5-secrets-rotation)
6. [Disaster recovery](#6-disaster-recovery)
7. [Escalation contacts](#7-escalation-contacts)

---

## 1. Service map

| Container | Port | Purpose |
|---|---|---|
| `ca-api-kaats-{env}` | 8000 | FastAPI application |
| `ca-worker-kaats-{env}` | — | Agent worker (Service Bus consumer) |
| `ca-scheduler-kaats-{env}` | — | Cron-style job scheduler |
| `ca-frontend-kaats-{env}` | 5173 | React SPA (nginx) |
| `sqlserver-{env}` | 1433 | Azure SQL Server (MSSQL) |
| Cosmos DB | 443 | Agent step log storage |
| Service Bus | 443 | AI-jobs / crawl-jobs / result-events topics |
| Blob Storage | 443 | Evidence screenshots + reports |
| ACS | 443 | Invitation email delivery |

---

## 2. Health checks

```bash
# Liveness (no auth required)
curl https://api.kaats.kiu.ai/health/live

# Readiness (checks DB + dependencies)
curl https://api.kaats.kiu.ai/health/ready
```

Expected responses:

| Endpoint | Healthy | Degraded |
|---|---|---|
| `/health/live` | `200 {"status":"ok"}` | `5xx` |
| `/health/ready` | `200 {"status":"ok"}` | `503 {"status":"degraded", ...}` |

---

## 3. Alert reference

### API_HIGH_ERROR_RATE
**Trigger:** HTTP 5xx rate > 5 % over 5 minutes (Application Insights)  
**Severity:** P1  
**Diagnosis:**
1. Check Container Apps logs: `az containerapp logs show -n ca-api-kaats-prod -g rg-kaats-prod --tail 200`
2. Look for `unhandled_error` log entries — they include `request_id` and `correlation_id`.
3. Check DB connectivity: `curl https://api.kaats.kiu.ai/health/ready`
4. Check recent deployments: `az containerapp revision list -n ca-api-kaats-prod -g rg-kaats-prod`

**Recovery:** If caused by a bad deploy, activate the previous revision (see §4.4).

---

### DB_CONNECTION_EXHAUSTED
**Trigger:** `db.pool.overflow` metric > 0 sustained for > 2 minutes  
**Severity:** P2  
**Diagnosis:**
1. Check `database.py` pool settings: `pool_size=10, max_overflow=20`.
2. Look for long-running queries: connect to SQL Server and run
   `SELECT * FROM sys.dm_exec_requests WHERE status = 'running' ORDER BY total_elapsed_time DESC`.
3. Check for deadlocks in the SQL error log.

**Recovery:**
- Scale out the API container: `az containerapp update -n ca-api-kaats-prod -g rg-kaats-prod --min-replicas 2 --max-replicas 10`
- If a runaway query is identified, kill it with `KILL <session_id>`.

---

### SERVICE_BUS_DEAD_LETTER
**Trigger:** Dead-letter count > 10 on any topic subscription  
**Severity:** P2  
**Diagnosis:**
1. Inspect messages:
   ```bash
   az servicebus topic subscription show \
     --resource-group rg-kaats-prod \
     --namespace-name sbns-kaats-prod \
     --topic-name ai-jobs \
     --name worker
   ```
2. Check worker logs for deserialization errors or repeated exceptions.
3. Check agent run records for `FAILED` status with error details.

**Recovery:**
- Fix the underlying bug and redeploy.
- If messages are recoverable, requeue them from the DLQ; otherwise discard.

---

### AGENT_RUN_STUCK
**Trigger:** `agent_runs` row with `status = 'running'` and `updated_at` > 30 min ago  
**Severity:** P3  
**Diagnosis:**
1. Check worker logs for the specific `run_id`.
2. Check if the worker container is healthy.
3. Check if the Playwright browser pool timed out (look for `browser_pool.startup_skipped`).

**Recovery:**
```sql
-- Mark stuck run as failed so the UI shows a terminal state
UPDATE agent_runs
SET status = 'failed',
    error_message = 'Marked failed by operator — run timed out',
    completed_at = GETUTCDATE()
WHERE id = '<run_id>' AND status = 'running';
```

---

### QUOTA_EXCEEDED_SPIKE
**Trigger:** HTTP 429 rate > 10 % over 5 minutes  
**Severity:** P3 (informational — expected under load; P2 if caused by a bug)  
**Diagnosis:**
1. Check `/usage/quota` for the affected company.
2. Determine if the rate limiting is legitimate (plan enforcement) or a mis-configuration.

**Recovery:** If legitimate, inform the customer to upgrade. If misconfigured, adjust `company_plans` directly:
```sql
UPDATE company_plans SET monthly_agent_run_limit = 500 WHERE company_id = '<id>';
```

---

## 4. Common failure scenarios

### 4.1 API container won't start

1. Pull the latest image locally and inspect:
   ```bash
   docker pull <acr>.azurecr.io/kaats-api:<tag>
   docker run --env-file .env.prod <image> python -c "from app.main import app; print('ok')"
   ```
2. Check for missing environment variables — all required settings are documented in `backend/app/config.py`.
3. Check if the database is reachable from within the Container Apps environment (private networking issue?).

---

### 4.2 Alembic migration failed mid-deploy

Symptom: API starts but returns 500 for requests that hit migrated tables.

```bash
# Connect to the API container and check migration state
az containerapp exec -n ca-api-kaats-prod -g rg-kaats-prod \
  --command "alembic current"

# Apply the missing migration
az containerapp exec -n ca-api-kaats-prod -g rg-kaats-prod \
  --command "alembic upgrade head"
```

If the migration is destructive and cannot be applied cleanly, roll back to the
previous image revision and revert the migration in a hotfix.

---

### 4.3 Email invitations not being delivered

1. Check ACS logs in the Azure Portal → Communication Services → Email → Logs.
2. Verify `ACS_CONNECTION_STRING` and `ACS_SENDER_ADDRESS` env vars are set on the API container.
3. Check the API logs for `email.send_failed` entries.
4. In dev/staging, emails are only logged (no ACS client) — this is expected.

---

### 4.4 Rolling back a bad deployment

Container Apps keeps prior revisions available:

```bash
# List revisions (newest first)
az containerapp revision list \
  -n ca-api-kaats-prod -g rg-kaats-prod \
  --query "[].{name:name, active:properties.active, created:properties.createdTime}" \
  -o table

# Activate a previous revision (single-revision mode: this deactivates the current one)
az containerapp revision activate \
  -n ca-api-kaats-prod -g rg-kaats-prod \
  --revision <previous-revision-name>
```

---

### 4.5 Cosmos DB rate limiting (429 from Cosmos)

Symptom: Agent step logs fail to write; `cosmos.write_failed` log entries.

1. Check RU consumption in Azure Portal → Cosmos DB → Metrics → Total Request Units.
2. If in Serverless mode, check for runaway agent producing thousands of steps.
3. If in Autoscale mode, increase `cosmosMaxThroughput` in the Bicep params and redeploy.

---

## 5. Secrets rotation

All secrets are stored in Azure Key Vault (`kv-kaats-{env}`). Container Apps
mounts them as secret references — updating Key Vault does **not** automatically
reload secrets in running containers. A new revision must be deployed.

### 5.1 Rotate SQL Server password

1. Generate a new password: `openssl rand -base64 32`
2. Update the SQL Server login:
   ```sql
   ALTER LOGIN sa WITH PASSWORD = '<new-password>';
   ```
3. Update Key Vault:
   ```bash
   az keyvault secret set --vault-name kv-kaats-prod \
     --name sql-password --value '<new-password>'
   ```
4. Redeploy (triggers a new revision with the refreshed secret):
   ```bash
   az containerapp update -n ca-api-kaats-prod -g rg-kaats-prod \
     --set-env-vars AZURE_SQL_PASSWORD=secretref:sql-password
   ```

### 5.2 Rotate Azure AD client secret

1. Create a new secret in Entra ID → App registrations → KAATS → Certificates & secrets.
2. Update Key Vault: `az keyvault secret set --vault-name kv-kaats-prod --name azure-client-secret --value '<new-secret>'`
3. Redeploy all three containers (api, worker, scheduler).
4. Delete the old secret from Entra ID (keep it until the new one is confirmed working).

### 5.3 Rotate ACS connection string

1. Regenerate the key in the Azure Portal → Communication Services → Keys.
2. Update Key Vault: `az keyvault secret set --vault-name kv-kaats-prod --name acs-connection-string --value '<new-string>'`
3. Redeploy the API container.

### 5.4 Rotate storage account key

1. Rotate in the Azure Portal → Storage account → Access keys → Rotate.
2. Update Key Vault with the new key value.
3. Redeploy the API and worker containers.

---

## 6. Disaster recovery

### 6.1 SQL Server point-in-time restore

Production is configured with 30-day backup retention and geo-redundant backups.

```bash
# Restore to a new database (do not overwrite the live DB)
az sql db restore \
  --resource-group rg-kaats-prod \
  --server sql-kaats-prod \
  --name kaats \
  --dest-name kaats-restore-$(date +%Y%m%d) \
  --time "2026-05-14T12:00:00Z"
```

After verifying data integrity in the restored database:
1. Run Alembic against the restored DB to confirm schema version.
2. Update the `AZURE_SQL_DATABASE` env var in Container Apps to point to the restored DB.
3. Rename databases as appropriate.

### 6.2 Cosmos DB backup

Cosmos DB uses continuous backup mode (4-hour RPO). To restore:
1. Open Azure Portal → Cosmos DB → Point-in-time restore.
2. Restore to a new account (cannot restore in-place).
3. Update `AZURE_COSMOS_ENDPOINT` in the API container to point to the restored account.

### 6.3 Regional failover

If `eastus` is unavailable:
1. SQL Server geo-redundant backup can be restored in any region.
2. Redeploy the Bicep stack targeting a new region: change `param location = 'westus2'`.
3. Update DNS (Azure Front Door / custom domain) to point to the new environment.

### 6.4 Full environment rebuild

In the event of complete environment loss:
1. Restore secrets from the backup Key Vault or your secrets manager.
2. Re-provision infrastructure: `az deployment group create --template-file infrastructure/bicep/main.bicep --parameters infrastructure/bicep/parameters/prod.bicepparam`
3. Restore the SQL database (§6.1).
4. Redeploy container images from ACR (images are retained for 90 days).
5. Run `alembic upgrade head` against the restored database.
6. Validate with `curl https://api.kaats.kiu.ai/health/ready`.

---

## 7. Escalation contacts

| Role | Contact | When to escalate |
|---|---|---|
| On-call engineer | PagerDuty rotation | Any P1/P2 alert |
| Platform lead | (see team directory) | Extended outage > 30 min, data loss |
| Azure support | Portal → Support | Azure platform issues, quota increases |
| Anthropic support | (see API key owner) | LLM API outage or capacity issues |
