// ─────────────────────────────────────────────────────────────────────────────
// Networking — VNet, subnets, private DNS zones
// Private endpoints are created by the individual data-service modules when
// enablePrivateEndpoint = true; this module provides the subnet IDs and
// pre-creates the Private DNS Zones so they can be linked once.
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource suffix (appName-env)')
param suffix string

@description('Enable VNet injection and private networking')
param enablePrivateNetworking bool

// ─────────────────────────────────────────────────────────────────────────────
// VNet + Subnets
// ─────────────────────────────────────────────────────────────────────────────

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = if (enablePrivateNetworking) {
  name: 'vnet-${suffix}'
  location: location
  tags: { component: 'networking' }
  properties: {
    addressSpace: {
      addressPrefixes: ['10.0.0.0/16']
    }
    subnets: [
      {
        // /23 required for Container Apps VNet-injection (consumption profile)
        name: 'snet-container-apps'
        properties: {
          addressPrefix: '10.0.0.0/23'
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: 'snet-private-endpoints'
        properties: {
          addressPrefix: '10.0.2.0/24'
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Private DNS Zones  (only created when private networking is enabled)
// ─────────────────────────────────────────────────────────────────────────────

resource dnsZoneSql 'Microsoft.Network/privateDnsZones@2020-06-01' = if (enablePrivateNetworking) {
  name: 'privatelink.database.windows.net'
  location: 'global'
}

resource dnsZoneSqlLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = if (enablePrivateNetworking) {
  parent: dnsZoneSql
  name: 'link-sql-${suffix}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource dnsZoneCosmos 'Microsoft.Network/privateDnsZones@2020-06-01' = if (enablePrivateNetworking) {
  name: 'privatelink.documents.azure.com'
  location: 'global'
}

resource dnsZoneCosmosLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = if (enablePrivateNetworking) {
  parent: dnsZoneCosmos
  name: 'link-cosmos-${suffix}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource dnsZoneStorageBlob 'Microsoft.Network/privateDnsZones@2020-06-01' = if (enablePrivateNetworking) {
  name: 'privatelink.blob.core.windows.net'
  location: 'global'
}

resource dnsZoneStorageBlobLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = if (enablePrivateNetworking) {
  parent: dnsZoneStorageBlob
  name: 'link-blob-${suffix}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource dnsZoneServiceBus 'Microsoft.Network/privateDnsZones@2020-06-01' = if (enablePrivateNetworking) {
  name: 'privatelink.servicebus.windows.net'
  location: 'global'
}

resource dnsZoneServiceBusLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = if (enablePrivateNetworking) {
  parent: dnsZoneServiceBus
  name: 'link-sb-${suffix}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource dnsZoneKeyVault 'Microsoft.Network/privateDnsZones@2020-06-01' = if (enablePrivateNetworking) {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
}

resource dnsZoneKeyVaultLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = if (enablePrivateNetworking) {
  parent: dnsZoneKeyVault
  name: 'link-kv-${suffix}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs  (return empty strings when networking is disabled so dependent
//           modules can still compile — they guard on enablePrivateEndpoint)
// ─────────────────────────────────────────────────────────────────────────────

output containerAppsSubnetId string = enablePrivateNetworking ? vnet.properties.subnets[0].id : ''
output containerAppsSubnetAddressPrefix string = enablePrivateNetworking ? '10.0.0.0/23' : ''
output privateEndpointSubnetId string = enablePrivateNetworking ? vnet.properties.subnets[1].id : ''
output privateDnsZoneSqlId string = enablePrivateNetworking ? dnsZoneSql.id : ''
output privateDnsZoneCosmosId string = enablePrivateNetworking ? dnsZoneCosmos.id : ''
output privateDnsZoneStorageBlobId string = enablePrivateNetworking ? dnsZoneStorageBlob.id : ''
output privateDnsZoneServiceBusId string = enablePrivateNetworking ? dnsZoneServiceBus.id : ''
output privateDnsZoneKeyVaultId string = enablePrivateNetworking ? dnsZoneKeyVault.id : ''
output vnetId string = enablePrivateNetworking ? vnet.id : ''
