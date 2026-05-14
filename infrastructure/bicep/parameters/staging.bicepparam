// ─────────────────────────────────────────────────────────────────────────────
// Staging environment parameters
// Production-parity minus private networking and ZRS.
// SQL auto-pause disabled. Autoscale Cosmos at lower RU.
// ─────────────────────────────────────────────────────────────────────────────

using '../main.bicep'

param environment = 'staging'
param location = 'eastus'
param resourceGroupName = 'rg-kaats-staging'
param appName = 'kaats'

// Azure AD
param azureTenantId = '<your-tenant-id>'
param azureClientId = '<your-client-id>'
param sqlEntraAdminObjectId = '<your-entra-admin-object-id>'
param sqlEntraAdminLogin = 'svc-kaats-staging@yourdomain.com'

// Azure OpenAI
param azureOpenAiEndpoint = 'https://aoai-kaats-staging.openai.azure.com/'
param azureOpenAiDeploymentName = 'gpt-4o'
param azureOpenAiModelName = 'gpt-4o'

// Application
param sqlDatabaseName = 'kaats_staging'
param cosmosDatabaseName = 'kaats'
param allowedOrigins = 'https://kaats-staging.kiu.ai,https://ca-frontend-kaats-staging.azurecontainerapps.io'
param imageTag = 'staging'

// Communication Services
param acsSenderAddress = 'noreply@staging.kaats.kiu.ai'
param frontendBaseUrl = 'https://kaats-staging.kiu.ai'

// Infrastructure toggles
param enablePrivateNetworking = false     // add private networking before GA
param storageSkuName = 'Standard_LRS'
param keyVaultSku = 'standard'
param cosmosCapacityMode = 'Autoscale'
param cosmosMaxThroughput = 1000
param sqlDisableSqlAuth = true            // enforce Entra-only from staging onward
param sqlGeoRedundantBackup = false
param sqlBackupRetentionDays = 14
param keyVaultPurgeProtection = false
param alwaysOn = true                     // always-on for QA team
