// ─────────────────────────────────────────────────────────────────────────────
// Production environment parameters
// Azure Well-Architected Framework — Reliability + Security columns:
//   ZRS storage, Premium KV, Autoscale Cosmos 4000 RU, private endpoints,
//   Entra-only SQL auth, 30-day backup retention, purge protection on.
// ─────────────────────────────────────────────────────────────────────────────

using '../main.bicep'

param environment = 'prod'
param location = 'eastus'
param resourceGroupName = 'rg-kaats-prod'
param appName = 'kaats'

// Azure AD — use production service principal
param azureTenantId = '<your-tenant-id>'
param azureClientId = '<your-prod-client-id>'
param sqlEntraAdminObjectId = '<your-prod-entra-admin-object-id>'
param sqlEntraAdminLogin = 'svc-kaats-prod@yourdomain.com'

// Azure OpenAI — dedicated production capacity
param azureOpenAiEndpoint = 'https://aoai-kaats-prod.openai.azure.com/'
param azureOpenAiDeploymentName = 'gpt-4o'
param azureOpenAiModelName = 'gpt-4o'

// Application
param sqlDatabaseName = 'kaats'
param cosmosDatabaseName = 'kaats'
param allowedOrigins = 'https://kaats.kiu.ai'
param imageTag = 'prod'

// Infrastructure toggles — full production hardening
param enablePrivateNetworking = true      // VNet + private endpoints for all data services
param storageSkuName = 'Standard_ZRS'    // Zone-redundant storage
param keyVaultSku = 'premium'            // Premium — HSM-backed keys
param cosmosCapacityMode = 'Autoscale'
param cosmosMaxThroughput = 4000         // scale 400–4000 RU automatically
param sqlDisableSqlAuth = true           // Entra-only — no password auth
param sqlGeoRedundantBackup = true       // geo-redundant backup
param sqlBackupRetentionDays = 30        // 30-day point-in-time restore
param keyVaultPurgeProtection = true     // can never accidentally delete KV
param alwaysOn = true                    // min 1 replica for cold-start SLA
