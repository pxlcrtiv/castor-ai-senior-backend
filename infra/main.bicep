// Azure Container Apps + Azure OpenAI Service
// Castor AI Reconciliation Agent - Infrastructure
//
// This template deploys the agent behind a private VNet,
// ensuring all traffic stays within the corporate network.

targetScope = 'subscription'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Azure region for all resources')
param location string = 'eastus'

@description('Environment name (dev, staging, prod)')
@minLength(1)
param environmentName string = 'dev'

@description('Name of the resource group')
param resourceGroupName string = 'rg-castor-ai-${environmentName}'

@description('Azure OpenAI resource name')
param openAiName string = 'openai-castor-${environmentName}'

@description('Container App name')
param containerAppName string = 'ca-reconciler-${environmentName}'

@description('Container App Environment name')
param containerEnvName string = 'cae-castor-${environmentName}'

@description('VNet name')
param vnetName string = 'vnet-castor-${environmentName}'

@description('Azure OpenAI deployment name (model)')
param openAiDeployment string = 'gpt-4o'

// ---------------------------------------------------------------------------
// Resource Group
// ---------------------------------------------------------------------------

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
}

// ---------------------------------------------------------------------------
// Networking - Private VNet
// ---------------------------------------------------------------------------

module vnet 'modules/vnet.bicep' = {
  name: 'vnet-deploy'
  scope: rg
  params: {
    location: location
    vnetName: vnetName
    subnetName: 'snet-container-apps'
    addressPrefix: '10.0.0.0/16'
    subnetPrefix: '10.0.1.0/24'
  }
}

// ---------------------------------------------------------------------------
// Azure OpenAI Service (Private Endpoint)
// ---------------------------------------------------------------------------

module openAi 'modules/openai.bicep' = {
  name: 'openai-deploy'
  scope: rg
  params: {
    location: location
    resourceName: openAiName
    deploymentName: openAiDeployment
    modelVersion: '2024-08-06'
    subnetId: vnet.outputs.subnetId
  }
}

// ---------------------------------------------------------------------------
// Container Apps Environment
// ---------------------------------------------------------------------------

module containerEnv 'modules/container-env.bicep' = {
  name: 'container-env-deploy'
  scope: rg
  params: {
    location: location
    environmentName: containerEnvName
    vnetId: vnet.outputs.vnetId
    subnetId: vnet.outputs.subnetId
  }
}

// ---------------------------------------------------------------------------
// Container App (the agent)
// ---------------------------------------------------------------------------

module containerApp 'modules/container-app.bicep' = {
  name: 'container-app-deploy'
  scope: rg
  params: {
    location: location
    appName: containerAppName
    environmentName: containerEnv.name
    containerImage: 'castor-ai-reconciler:latest'
    openAiEndpoint: openAi.outputs.endpoint
    openAiKeyName: openAi.outputs.primaryKeyName
    openAiKey: openAi.outputs.primaryKey
  }

  dependsOn: [containerEnv]
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Container App FQDN')
output appFqdn string = containerApp.outputs.fqdn

@description('OpenAI endpoint (private)')
output openAiEndpoint string = openAi.outputs.endpoint
