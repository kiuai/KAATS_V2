// ─────────────────────────────────────────────────────────────────────────────
// Azure SQL — Server + Database
// Entra-only auth (configurable). Serverless GP tier with auto-pause in dev.
// TDE enabled by default. Geo-redundant backup in prod.
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource suffix (appName-env)')
param suffix string

@description('SQL database name')
param databaseName string

@description('Object ID of the Entra user/group to be SQL admin')
param entraAdminObjectId string

@description('Login name (UPN) of the Entra SQL admin')
param entraAdminLogin string

@description('Disable SQL password auth — Entra only (recommended for prod)')
param disableSqlAuth bool

@description('Enable geo-redundant backup')
param geoRedundantBackup bool

@description('Backup retention in days')
param backupRetentionDays int

@description('Managed identity principal ID for role assignments')
param managedIdentityPrincipalId string

@description('Enable private endpoint')
param enablePrivateEndpoint bool

@description('Private endpoint subnet resource ID')
param privateEndpointSubnetId string

@description('Private DNS Zone resource ID for SQL')
param privateDnsZoneSqlId string

@description('Environment label (dev | staging | prod) — controls auto-pause')
param environment string

// ─────────────────────────────────────────────────────────────────────────────
// SQL Server
// ─────────────────────────────────────────────────────────────────────────────

resource sqlServer 'Microsoft.Sql/servers@2022-05-01-preview' = {
  name: 'sql-${suffix}'
  location: location
  tags: { component: 'sql' }
  properties: {
    // Entra-only admin (no SQL admin login in prod)
    administrators: {
      administratorType: 'ActiveDirectory'
      principalType: 'Group'   // change to 'User' if entraAdminObjectId is a user OID
      login: entraAdminLogin
      sid: entraAdminObjectId
      tenantId: subscription().tenantId
      azureADOnlyAuthentication: disableSqlAuth
    }
    minimalTlsVersion: '1.2'
    publicNetworkAccess: enablePrivateEndpoint ? 'Disabled' : 'Enabled'
  }
}

// Firewall: allow Azure services (needed for Container Apps) and dev access
resource fwAllowAzureServices 'Microsoft.Sql/servers/firewallRules@2022-05-01-preview' = if (!enablePrivateEndpoint) {
  parent: sqlServer
  name: 'AllowAllAzureIPs'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Database
// General Purpose serverless tier — auto-pause 1 hr in dev, disabled in prod
// ─────────────────────────────────────────────────────────────────────────────

resource database 'Microsoft.Sql/servers/databases@2022-05-01-preview' = {
  parent: sqlServer
  name: databaseName
  location: location
  tags: { component: 'sql' }
  sku: {
    name: 'GP_S_Gen5'
    tier: 'GeneralPurpose'
    family: 'Gen5'
    capacity: 2    // 2 vCores
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: 34359738368  // 32 GB
    autoPauseDelay: environment == 'prod' ? -1 : 60    // -1 = disabled; 60 min in dev
    minCapacity: json('0.5')
    zoneRedundant: false
    readScale: 'Disabled'
    requestedBackupStorageRedundancy: geoRedundantBackup ? 'Geo' : 'Local'
  }
}

// Short-term backup retention
resource backupPolicy 'Microsoft.Sql/servers/databases/backupShortTermRetentionPolicies@2022-05-01-preview' = {
  parent: database
  name: 'default'
  properties: {
    retentionDays: backupRetentionDays
    diffBackupIntervalInHours: 24
  }
}

// Long-term retention (prod: monthly for 1 year)
resource ltrPolicy 'Microsoft.Sql/servers/databases/backupLongTermRetentionPolicies@2022-05-01-preview' = if (geoRedundantBackup) {
  parent: database
  name: 'default'
  properties: {
    weeklyRetention: 'P4W'
    monthlyRetention: 'P12M'
    yearlyRetention: 'PT0S'
    weekOfYear: 1
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Transparent Data Encryption  (enabled by default on Azure SQL, explicit here)
// ─────────────────────────────────────────────────────────────────────────────

resource tde 'Microsoft.Sql/servers/databases/transparentDataEncryption@2022-05-01-preview' = {
  parent: database
  name: 'current'
  properties: {
    state: 'Enabled'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Role: SQL DB Contributor → managed identity (for migration runs via exec)
// ─────────────────────────────────────────────────────────────────────────────

var sqlDbContributorId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '9b7fa17d-e63e-47b0-bb0a-15c516ac86ec'
)

resource roleSqlContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sqlServer.id, managedIdentityPrincipalId, sqlDbContributorId)
  scope: sqlServer
  properties: {
    roleDefinitionId: sqlDbContributorId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Private Endpoint  (prod only)
// ─────────────────────────────────────────────────────────────────────────────

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = if (enablePrivateEndpoint) {
  name: 'pe-sql-${suffix}'
  location: location
  properties: {
    subnet: { id: privateEndpointSubnetId }
    privateLinkServiceConnections: [
      {
        name: 'plsc-sql-${suffix}'
        properties: {
          privateLinkServiceId: sqlServer.id
          groupIds: ['sqlServer']
        }
      }
    ]
  }
}

resource dnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = if (enablePrivateEndpoint) {
  parent: privateEndpoint
  name: 'dns-group-sql'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-database-windows-net'
        properties: { privateDnsZoneId: privateDnsZoneSqlId }
      }
    ]
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output serverId string = sqlServer.id
output serverName string = sqlServer.name
output fqdn string = sqlServer.properties.fullyQualifiedDomainName
output databaseName string = database.name
