// ─────────────────────────────────────────────────────────────────────────────
// Managed Identity
// Single User-Assigned Managed Identity shared by all Container Apps.
// Role assignments are co-located here so the full IAM picture is in one file.
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource suffix (appName-env)')
param suffix string

// ─────────────────────────────────────────────────────────────────────────────
// User-Assigned Managed Identity
// ─────────────────────────────────────────────────────────────────────────────

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${suffix}'
  location: location
  tags: { component: 'identity' }
}

// ─────────────────────────────────────────────────────────────────────────────
// Built-in Role Definition IDs
// ─────────────────────────────────────────────────────────────────────────────

// Note: Data-plane role assignments for Cosmos, Storage, Service Bus, Key Vault
// are created in the respective data-service modules because they need the
// resource's scope. Subscription-scoped roles are assigned here.

// Monitoring Metrics Publisher — lets the identity push custom metrics
var monitoringMetricsPublisherId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '3913510d-42f4-4e42-8a64-420c390055eb'
)

resource roleMonitoring 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().id, identity.id, monitoringMetricsPublisherId)
  properties: {
    roleDefinitionId: monitoringMetricsPublisherId
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output id string = identity.id
output principalId string = identity.properties.principalId
output clientId string = identity.properties.clientId
