// ─────────────────────────────────────────────────────────────────────────────
// KAATS — Main Bicep Template
// Subscription-scope deployment. Creates the resource group and wires all
// modules. Deploy with:
//   az deployment sub create \
//     --location eastus \
//     --template-file infrastructure/bicep/main.bicep \
//     --parameters infrastructure/bicep/parameters/prod.bicepparam
// ─────────────────────────────────────────────────────────────────────────────

targetScope = 'subscription'

// ── Parameters ────────────────────────────────────────────────────────────────

@description('Short environment label: dev | staging | prod')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Azure region for all resources')
param location string = 'eastus'

@description('Resource group name')
param resourceGroupName string = 'rg-kaats-${environment}'

@description('Base name for all resources (e.g. kaats)')
@maxLength(12)
param appName string = 'kaats'

// ── Azure AD / Entra ──────────────────────────────────────────────────────────
@description('Azure AD tenant ID')
param azureTenantId string

@description('App registration client ID')
param azureClientId string

@description('Object ID of the Entra group or user to be SQL admin')
param sqlEntraAdminObjectId string

@description('UPN of the Entra SQL admin (e.g. svc-kaats@corp.com)')
param sqlEntraAdminLogin string

// ── Azure OpenAI ──────────────────────────────────────────────────────────────
@description('Azure OpenAI endpoint URL')
param azureOpenAiEndpoint string

@description('Azure OpenAI deployment name')
param azureOpenAiDeploymentName string = 'gpt-4o'

@description('Azure OpenAI model name')
param azureOpenAiModelName string = 'gpt-4o'

// ── Application ───────────────────────────────────────────────────────────────
@description('SQL database name')
param sqlDatabaseName string = 'kaats'

@description('Cosmos DB database name')
param cosmosDatabaseName string = 'kaats'

@description('Comma-separated CORS allowed origins')
param allowedOrigins string = 'https://kaats.kiu.ai'

@description('Container image tag to deploy')
param imageTag string = 'latest'

// ── Feature flags (vary by environment) ───────────────────────────────────────
@description('Enable VNet injection and private endpoints')
param enablePrivateNetworking bool = false

@description('Storage redundancy: LRS | ZRS')
@allowed(['Standard_LRS', 'Standard_ZRS'])
param storageSkuName string = 'Standard_LRS'

@description('Key Vault tier: standard | premium')
@allowed(['standard', 'premium'])
param keyVaultSku string = 'standard'

@description('Cosmos DB capacity mode: Serverless | Autoscale')
@allowed(['Serverless', 'Autoscale'])
param cosmosCapacityMode string = 'Serverless'

@description('Cosmos DB max RUs for autoscale mode (ignored for Serverless)')
param cosmosMaxThroughput int = 4000

@description('Disable SQL auth (password logins) — enforce Entra-only in prod')
param sqlDisableSqlAuth bool = false

@description('Enable SQL geo-redundant backup')
param sqlGeoRedundantBackup bool = false

@description('SQL backup retention in days')
param sqlBackupRetentionDays int = 7

@description('Enable Key Vault purge protection')
param keyVaultPurgeProtection bool = false

@description('Enable Container Apps min replicas > 0 (always-on in prod)')
param alwaysOn bool = false

// ── Derived names ─────────────────────────────────────────────────────────────
var suffix = '${appName}-${environment}'
var acrName = replace('acr${appName}${environment}', '-', '')  // ACR name: no hyphens

// ─────────────────────────────────────────────────────────────────────────────
// Resource Group
// ─────────────────────────────────────────────────────────────────────────────

resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: resourceGroupName
  location: location
  tags: {
    application: 'KAATS'
    environment: environment
    managedBy: 'bicep'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Managed Identity  (deployed first — all other modules depend on its ID)
// ─────────────────────────────────────────────────────────────────────────────

module identity 'modules/identity.bicep' = {
  name: 'identity'
  scope: rg
  params: {
    location: location
    suffix: suffix
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Monitoring  (Log Analytics + App Insights — needed by Container Apps env)
// ─────────────────────────────────────────────────────────────────────────────

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  scope: rg
  params: {
    location: location
    suffix: suffix
    managedIdentityPrincipalId: identity.outputs.principalId
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Networking  (VNet + subnets + private DNS zones)
// ─────────────────────────────────────────────────────────────────────────────

module networking 'modules/networking.bicep' = {
  name: 'networking'
  scope: rg
  params: {
    location: location
    suffix: suffix
    enablePrivateNetworking: enablePrivateNetworking
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Data Services
// ─────────────────────────────────────────────────────────────────────────────

module storage 'modules/storage.bicep' = {
  name: 'storage'
  scope: rg
  params: {
    location: location
    suffix: suffix
    skuName: storageSkuName
    managedIdentityPrincipalId: identity.outputs.principalId
    enablePrivateEndpoint: enablePrivateNetworking
    privateEndpointSubnetId: networking.outputs.privateEndpointSubnetId
    privateDnsZoneStorageBlobId: networking.outputs.privateDnsZoneStorageBlobId
  }
}

module sqlDatabase 'modules/sql-database.bicep' = {
  name: 'sql-database'
  scope: rg
  params: {
    location: location
    suffix: suffix
    databaseName: sqlDatabaseName
    entraAdminObjectId: sqlEntraAdminObjectId
    entraAdminLogin: sqlEntraAdminLogin
    disableSqlAuth: sqlDisableSqlAuth
    geoRedundantBackup: sqlGeoRedundantBackup
    backupRetentionDays: sqlBackupRetentionDays
    managedIdentityPrincipalId: identity.outputs.principalId
    enablePrivateEndpoint: enablePrivateNetworking
    privateEndpointSubnetId: networking.outputs.privateEndpointSubnetId
    privateDnsZoneSqlId: networking.outputs.privateDnsZoneSqlId
    environment: environment
  }
}

module cosmosDb 'modules/cosmos-db.bicep' = {
  name: 'cosmos-db'
  scope: rg
  params: {
    location: location
    suffix: suffix
    databaseName: cosmosDatabaseName
    capacityMode: cosmosCapacityMode
    maxThroughput: cosmosMaxThroughput
    managedIdentityPrincipalId: identity.outputs.principalId
    enablePrivateEndpoint: enablePrivateNetworking
    privateEndpointSubnetId: networking.outputs.privateEndpointSubnetId
    privateDnsZoneCosmosId: networking.outputs.privateDnsZoneCosmosId
  }
}

module serviceBus 'modules/service-bus.bicep' = {
  name: 'service-bus'
  scope: rg
  params: {
    location: location
    suffix: suffix
    managedIdentityPrincipalId: identity.outputs.principalId
    enablePrivateEndpoint: enablePrivateNetworking
    privateEndpointSubnetId: networking.outputs.privateEndpointSubnetId
    privateDnsZoneServiceBusId: networking.outputs.privateDnsZoneServiceBusId
  }
}

module openAi 'modules/openai.bicep' = {
  name: 'openai'
  scope: rg
  params: {
    location: location
    suffix: suffix
    deploymentName: azureOpenAiDeploymentName
    modelName: azureOpenAiModelName
    managedIdentityPrincipalId: identity.outputs.principalId
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Key Vault  (created after identity so we can assign access)
// ─────────────────────────────────────────────────────────────────────────────

module keyVault 'modules/key-vault.bicep' = {
  name: 'key-vault'
  scope: rg
  params: {
    location: location
    suffix: suffix
    sku: keyVaultSku
    managedIdentityPrincipalId: identity.outputs.principalId
    purgeProtectionEnabled: keyVaultPurgeProtection
    enablePrivateEndpoint: enablePrivateNetworking
    privateEndpointSubnetId: networking.outputs.privateEndpointSubnetId
    privateDnsZoneKeyVaultId: networking.outputs.privateDnsZoneKeyVaultId
    containerAppsSubnetAddressPrefix: networking.outputs.containerAppsSubnetAddressPrefix
    tenantId: azureTenantId
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Container Registry
// ─────────────────────────────────────────────────────────────────────────────

module containerRegistry 'modules/container-registry.bicep' = {
  name: 'container-registry'
  scope: rg
  params: {
    location: location
    registryName: acrName
    managedIdentityId: identity.outputs.id
    managedIdentityPrincipalId: identity.outputs.principalId
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Container Apps Environment
// ─────────────────────────────────────────────────────────────────────────────

module containerAppsEnv 'modules/container-apps-env.bicep' = {
  name: 'container-apps-env'
  scope: rg
  params: {
    location: location
    suffix: suffix
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
    logAnalyticsCustomerId: monitoring.outputs.logAnalyticsCustomerId
    logAnalyticsPrimaryKey: monitoring.outputs.logAnalyticsPrimaryKey
    enableVnetIntegration: enablePrivateNetworking
    infrastructureSubnetId: networking.outputs.containerAppsSubnetId
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Container Apps (api, worker, scheduler, frontend)
// ─────────────────────────────────────────────────────────────────────────────

module containerApps 'modules/container-apps.bicep' = {
  name: 'container-apps'
  scope: rg
  params: {
    location: location
    suffix: suffix
    containerAppsEnvironmentId: containerAppsEnv.outputs.environmentId
    managedIdentityId: identity.outputs.id
    acrLoginServer: containerRegistry.outputs.loginServer
    imageTag: imageTag
    keyVaultUri: keyVault.outputs.vaultUri
    // Connection details
    azureTenantId: azureTenantId
    azureClientId: azureClientId
    azureOpenAiEndpoint: azureOpenAiEndpoint
    azureOpenAiDeploymentName: azureOpenAiDeploymentName
    sqlServerFqdn: sqlDatabase.outputs.fqdn
    sqlDatabaseName: sqlDatabaseName
    sqlAdminLogin: sqlEntraAdminLogin
    cosmosEndpoint: cosmosDb.outputs.endpoint
    cosmosDatabaseName: cosmosDatabaseName
    storageAccountName: storage.outputs.accountName
    allowedOrigins: allowedOrigins
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    environment: environment
    alwaysOn: alwaysOn
    // Service Bus
    serviceBusNamespaceFqdn: serviceBus.outputs.namespaceFqdn
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Container Apps Jobs (burst-scale agent runner)
// ─────────────────────────────────────────────────────────────────────────────

module containerAppsJobs 'modules/container-apps-jobs.bicep' = {
  name: 'container-apps-jobs'
  scope: rg
  params: {
    location: location
    suffix: suffix
    containerAppsEnvironmentId: containerAppsEnv.outputs.environmentId
    managedIdentityId: identity.outputs.id
    acrLoginServer: containerRegistry.outputs.loginServer
    imageTag: imageTag
    keyVaultUri: keyVault.outputs.vaultUri
    azureTenantId: azureTenantId
    azureClientId: azureClientId
    azureOpenAiEndpoint: azureOpenAiEndpoint
    azureOpenAiDeploymentName: azureOpenAiDeploymentName
    sqlServerFqdn: sqlDatabase.outputs.fqdn
    sqlDatabaseName: sqlDatabaseName
    sqlAdminLogin: sqlEntraAdminLogin
    cosmosEndpoint: cosmosDb.outputs.endpoint
    cosmosDatabaseName: cosmosDatabaseName
    storageAccountName: storage.outputs.accountName
    serviceBusNamespaceFqdn: serviceBus.outputs.namespaceFqdn
    serviceBusQueueName: serviceBus.outputs.agentJobsQueueName
    environment: environment
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output resourceGroupName string = rg.name
output apiUrl string = containerApps.outputs.apiUrl
output frontendUrl string = containerApps.outputs.frontendUrl
output acrLoginServer string = containerRegistry.outputs.loginServer
output keyVaultName string = keyVault.outputs.vaultName
output sqlServerFqdn string = sqlDatabase.outputs.fqdn
output cosmosEndpoint string = cosmosDb.outputs.endpoint
output storageAccountName string = storage.outputs.accountName
output managedIdentityClientId string = identity.outputs.clientId
