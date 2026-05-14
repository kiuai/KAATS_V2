// ─────────────────────────────────────────────────────────────────────────────
// Storage Account
// Blob containers: evidence, exports, crawl-screenshots, import-files
// Lifecycle policy: Cool after 90 days, Archive after 365 days for evidence
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource suffix (appName-env)')
param suffix string

@description('Storage SKU: Standard_LRS (dev/staging) | Standard_ZRS (prod)')
@allowed(['Standard_LRS', 'Standard_ZRS'])
param skuName string

@description('Managed identity principal ID for role assignments')
param managedIdentityPrincipalId string

@description('Enable private endpoint')
param enablePrivateEndpoint bool

@description('Private endpoint subnet resource ID')
param privateEndpointSubnetId string

@description('Private DNS Zone resource ID for blob storage')
param privateDnsZoneStorageBlobId string

// Storage account name: 3-24 chars, lowercase alphanumeric only
var storageAccountName = replace(toLower('st${replace(suffix, '-', '')}'), '-', '')

// ─────────────────────────────────────────────────────────────────────────────
// Storage Account
// ─────────────────────────────────────────────────────────────────────────────

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: length(storageAccountName) > 24 ? substring(storageAccountName, 0, 24) : storageAccountName
  location: location
  kind: 'StorageV2'
  tags: { component: 'storage' }
  sku: {
    name: skuName
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true          // needed until MI-only migration
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: enablePrivateEndpoint ? 'Disabled' : 'Enabled'
    encryption: {
      services: {
        blob: { enabled: true }
        file: { enabled: true }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Blob Service + Containers
// ─────────────────────────────────────────────────────────────────────────────

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

var containers = ['evidence', 'exports', 'crawl-screenshots', 'import-files']

resource blobContainers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = [
  for name in containers: {
    parent: blobService
    name: name
    properties: {
      publicAccess: 'None'
    }
  }
]

// ─────────────────────────────────────────────────────────────────────────────
// Lifecycle Management Policy
// ─────────────────────────────────────────────────────────────────────────────

resource lifecyclePolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2023-01-01' = {
  parent: storage
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'evidence-tiering'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['evidence/']
            }
            actions: {
              baseBlob: {
                tierToCool: { daysAfterModificationGreaterThan: 90 }
                tierToArchive: { daysAfterModificationGreaterThan: 365 }
              }
              snapshot: {
                delete: { daysAfterCreationGreaterThan: 90 }
              }
            }
          }
        }
        {
          name: 'exports-cleanup'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['exports/']
            }
            actions: {
              baseBlob: {
                delete: { daysAfterModificationGreaterThan: 90 }
              }
            }
          }
        }
        {
          name: 'import-files-cleanup'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['import-files/']
            }
            actions: {
              baseBlob: {
                delete: { daysAfterModificationGreaterThan: 30 }
              }
            }
          }
        }
      ]
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Role: Storage Blob Data Contributor → managed identity
// ─────────────────────────────────────────────────────────────────────────────

var storageBlobDataContributorId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)

resource roleBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, managedIdentityPrincipalId, storageBlobDataContributorId)
  scope: storage
  properties: {
    roleDefinitionId: storageBlobDataContributorId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Private Endpoint  (prod only)
// ─────────────────────────────────────────────────────────────────────────────

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = if (enablePrivateEndpoint) {
  name: 'pe-storage-${suffix}'
  location: location
  properties: {
    subnet: { id: privateEndpointSubnetId }
    privateLinkServiceConnections: [
      {
        name: 'plsc-storage-${suffix}'
        properties: {
          privateLinkServiceId: storage.id
          groupIds: ['blob']
        }
      }
    ]
  }
}

resource dnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = if (enablePrivateEndpoint) {
  parent: privateEndpoint
  name: 'dns-group-storage'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-blob-core-windows-net'
        properties: { privateDnsZoneId: privateDnsZoneStorageBlobId }
      }
    ]
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output accountName string = storage.name
output primaryKey string = storage.listKeys().keys[0].value
output connectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
