// Container App for the reconciliation agent

param location string
param appName string
param environmentName string
param containerImage string
param openAiEndpoint string
param openAiKeyName string
param openAiKey string

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    environmentId: resourceId('Microsoft.App/managedEnvironments', environmentName)
    configuration: {
      ingress: {
        external: false
        targetPort: 8000
        transport: 'http'
      }
    }
    template: {
      containers: [
        {
          name: 'reconciler'
          image: containerImage
          resources: {
            cpu: 1.0
            memory: '2Gi'
          }
          env: [
            { name: 'LLM_PROVIDER', value: 'openai' }
            { name: 'OPENAI_API_KEY', value: openAiKey }
            { name: 'OPENAI_BASE_URL', value: openAiEndpoint }
            { name: 'OPENAI_MODEL', value: 'gpt-4o' }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
      }
    }
  }
}

output fqdn string = containerApp.properties.configuration.ingress.fqdn
