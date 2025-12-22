#!/bin/bash
# Deploy Azure Function App code

set -e

# Load configuration
if [ -f "azure-config.env" ]; then
  source azure-config.env
else
  echo "Error: azure-config.env not found. Run setup-azure-infrastructure.sh first."
  exit 1
fi

echo "Deploying Function App: $FUNCTION_APP_NAME"

cd azure-function

# Install Azure Functions Core Tools if not installed
if ! command -v func &> /dev/null; then
  echo "Azure Functions Core Tools not found. Please install from:"
  echo "https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local"
  exit 1
fi

# Deploy
func azure functionapp publish "$FUNCTION_APP_NAME" --python

echo ""
echo "Deployment complete!"
echo ""
echo "Function App URL: $FUNCTION_APP_URL"
echo ""
echo "Get your function key:"
echo "  az functionapp keys list --resource-group $AZURE_RESOURCE_GROUP --name $FUNCTION_APP_NAME"
