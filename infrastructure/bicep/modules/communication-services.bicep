// ─────────────────────────────────────────────────────────────────────────────
// Azure Communication Services — email channel
// Provisions an ACS resource + Email Communication Service + custom domain.
//
// The connection string is stored in Key Vault so container apps can mount it
// as a secret reference (same pattern as Service Bus and Storage).
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource suffix (appName-env)')
param suffix string

@description('Key Vault resource ID — used to store the ACS connection string')
param keyVaultId string

@description('Managed identity principal ID — needs KV Secrets Officer on the vault')
param managedIdentityPrincipalId string

@description('Sender email address shown in From: field (must match a verified domain)')
param senderAddress string = 'noreply@kaats.kiu.ai'

// ─────────────────────────────────────────────────────────────────────────────
// ACS resource
// ─────────────────────────────────────────────────────────────────────────────

resource acs 'Microsoft.Communication/communicationServices@2023-04-01' = {
  name: 'acs-${suffix}'
  location: 'global'  // ACS is a global resource
  tags: { component: 'communication', tier: 'platform' }
  properties: {
    dataLocation: 'United States'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Email Communication Service
// ─────────────────────────────────────────────────────────────────────────────

resource emailSvc 'Microsoft.Communication/emailServices@2023-04-01' = {
  name: 'email-${suffix}'
  location: 'global'
  tags: { component: 'communication' }
  properties: {
    dataLocation: 'United States'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Azure Managed Domain  (azurecomm.net subdomain — no DNS verification needed)
// Replace with a custom domain resource for production branded sending.
// ─────────────────────────────────────────────────────────────────────────────

resource managedDomain 'Microsoft.Communication/emailServices/domains@2023-04-01' = {
  parent: emailSvc
  name: 'AzureManagedDomain'
  location: 'global'
  properties: {
    domainManagement: 'AzureManaged'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Link email domain to ACS
// ─────────────────────────────────────────────────────────────────────────────

resource acsEmailLink 'Microsoft.Communication/communicationServices/linkedEmailServiceResourceId@2023-04-01' = if (false) {
  // Note: domain-linking is a preview feature. For now the connection string
  // is sufficient; link manually in the portal after domain verification.
  parent: acs
  name: 'emailLink'
  properties: {
    emailServiceId: emailSvc.id
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Store connection string in Key Vault
// ─────────────────────────────────────────────────────────────────────────────

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: last(split(keyVaultId, '/'))
}

resource acsSecretConnStr 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'acs-connection-string'
  properties: {
    value: listKeys(acs.id, acs.apiVersion).primaryConnectionString
  }
}

resource acsSecretSender 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'acs-sender-address'
  properties: {
    value: senderAddress
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output acsResourceId string = acs.id
output emailServiceId string = emailSvc.id
output managedDomainName string = managedDomain.name
output connectionStringSecretUri string = acsSecretConnStr.properties.secretUri
output senderAddressSecretUri string = acsSecretSender.properties.secretUri
