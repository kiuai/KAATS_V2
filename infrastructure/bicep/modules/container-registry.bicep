// ─────────────────────────────────────────────────────────────────────────────
// Azure Container Registry
// Basic tier (dev/staging), Standard (prod — geo-replication optional).
// Managed identity gets AcrPull role so Container Apps can pull images.
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('ACR name — must be globally unique, alphanumeric only, 5-50 chars')
param registryName string

@description('Managed identity resource ID')
param managedIdentityId string

@description('Managed identity principal ID for role assignments')
param managedIdentityPrincipalId string

// ─────────────────────────────────────────────────────────────────────────────
// Registry
// ─────────────────────────────────────────────────────────────────────────────

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  tags: { component: 'container-registry' }
  sku: {
    name: 'Standard'
  }
  properties: {
    adminUserEnabled: false           // use managed identity — no admin credentials
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
    zoneRedundancy: 'Disabled'
    policies: {
      retentionPolicy: {
        status: 'enabled'
        days: 30
      }
      softDeletePolicy: {
        status: 'enabled'
        retentionDays: 7
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Role: AcrPull → managed identity (Container Apps pull images)
// ─────────────────────────────────────────────────────────────────────────────

var acrPullId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)

resource roleAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, managedIdentityPrincipalId, acrPullId)
  scope: acr
  properties: {
    roleDefinitionId: acrPullId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Role: AcrPush → managed identity (CI/CD pipeline pushes images)
// In practice CI uses a dedicated SP; this covers the fallback case.
// ─────────────────────────────────────────────────────────────────────────────

var acrPushId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '8311e382-0749-4cb8-b61a-304f252e45ec'
)

resource roleAcrPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, managedIdentityPrincipalId, acrPushId)
  scope: acr
  properties: {
    roleDefinitionId: acrPushId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output registryId string = acr.id
output loginServer string = acr.properties.loginServer
output registryName string = acr.name
