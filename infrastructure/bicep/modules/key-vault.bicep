// ─────────────────────────────────────────────────────────────────────────────
// Key Vault
// Secrets are populated post-deployment by scripts/deploy.sh.
// All Container Apps pull secrets via managed identity — no credential env vars.
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource suffix (appName-env)')
param suffix string

@description('Key Vault SKU: standard | premium')
@allowed(['standard', 'premium'])
param sku string

@description('Managed identity principal ID')
param managedIdentityPrincipalId string

@description('Enable purge protection (recommended for prod)')
param purgeProtectionEnabled bool

@description('Enable private endpoint')
param enablePrivateEndpoint bool

@description('Private endpoint subnet resource ID (ignored if enablePrivateEndpoint = false)')
param privateEndpointSubnetId string

@description('Private DNS Zone resource ID for Key Vault')
param privateDnsZoneKeyVaultId string

@description('Container Apps subnet CIDR — allowed in network ACL for non-private envs')
param containerAppsSubnetAddressPrefix string

@description('Azure AD tenant ID')
param tenantId string

// ─────────────────────────────────────────────────────────────────────────────
// Key Vault
// ─────────────────────────────────────────────────────────────────────────────

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${suffix}'
  location: location
  tags: { component: 'key-vault' }
  properties: {
    tenantId: tenantId
    sku: {
      family: 'A'
      name: sku
    }
    enableRbacAuthorization: true       // Use Azure RBAC — no legacy access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: purgeProtectionEnabled ? true : null
    publicNetworkAccess: enablePrivateEndpoint ? 'Disabled' : 'Enabled'
    networkAcls: enablePrivateEndpoint ? {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
      ipRules: []
      virtualNetworkRules: []
    } : {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
      ipRules: []
      virtualNetworkRules: []
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Role: Key Vault Secrets Officer → managed identity (read + write secrets)
// ─────────────────────────────────────────────────────────────────────────────

var kvSecretsOfficerId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
)

resource roleKvSecretsOfficer 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, managedIdentityPrincipalId, kvSecretsOfficerId)
  scope: kv
  properties: {
    roleDefinitionId: kvSecretsOfficerId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Private Endpoint  (prod only)
// ─────────────────────────────────────────────────────────────────────────────

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = if (enablePrivateEndpoint) {
  name: 'pe-kv-${suffix}'
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'plsc-kv-${suffix}'
        properties: {
          privateLinkServiceId: kv.id
          groupIds: ['vault']
        }
      }
    ]
  }
}

resource dnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = if (enablePrivateEndpoint) {
  parent: privateEndpoint
  name: 'dns-group-kv'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-vaultcore-azure-net'
        properties: {
          privateDnsZoneId: privateDnsZoneKeyVaultId
        }
      }
    ]
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output vaultUri string = kv.properties.vaultUri
output vaultName string = kv.name
output vaultId string = kv.id
