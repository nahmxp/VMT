#!/bin/bash
# QUICK START - Run this to get started immediately!

echo "════════════════════════════════════════════════════════════════"
echo "  YOLO Training API - Quick Start"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

command -v az >/dev/null 2>&1 || {
  echo "❌ Azure CLI not found. Install from: https://aka.ms/azure-cli"
  exit 1
}
echo "✅ Azure CLI installed"

command -v docker >/dev/null 2>&1 || {
  echo "❌ Docker not found. Install from: https://docs.docker.com/get-docker/"
  exit 1
}
echo "✅ Docker installed"

command -v func >/dev/null 2>&1 || {
  echo "❌ Azure Functions Core Tools not found. Install from: https://aka.ms/func-tools"
  exit 1
}
echo "✅ Azure Functions Core Tools installed"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Step 1: Azure Login"
echo "════════════════════════════════════════════════════════════════"

az account show >/dev/null 2>&1 || {
  echo "Please log in to Azure..."
  az login
}

SUBSCRIPTION_NAME=$(az account show --query name -o tsv)
echo "✅ Logged in to Azure"
echo "   Subscription: $SUBSCRIPTION_NAME"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Step 2: Setup Azure Infrastructure"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "This will create:"
echo "  • Resource Group"
echo "  • Storage Account with File Shares"
echo "  • Azure Container Registry"
echo "  • Docker image (built & pushed)"
echo "  • Azure Function App (API)"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Setup cancelled."
  exit 0
fi

cd "$(dirname "$0")/scripts"
./setup-azure-infrastructure.sh

if [ $? -ne 0 ]; then
  echo "❌ Infrastructure setup failed"
  exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Step 3: Upload Dataset & Model"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "You need to upload:"
echo "  1. COCO dataset ZIP file"
echo "  2. Base YOLO model (e.g., yolo11n-seg.pt)"
echo ""

read -p "Do you have files to upload now? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
  read -p "Enter path to COCO dataset ZIP: " DATASET_PATH
  read -p "Enter path to YOLO model (optional, press Enter to skip): " MODEL_PATH
  
  if [ -n "$MODEL_PATH" ]; then
    ./upload-files.sh "$DATASET_PATH" "$MODEL_PATH"
  else
    ./upload-files.sh "$DATASET_PATH"
  fi
else
  echo "⚠️  Remember to upload files later using:"
  echo "   ./scripts/upload-files.sh /path/to/dataset.zip /path/to/model.pt"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Step 4: Deploy Function App"
echo "════════════════════════════════════════════════════════════════"
echo ""

./deploy-function.sh

if [ $? -ne 0 ]; then
  echo "❌ Function deployment failed"
  exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Step 5: Get API Credentials"
echo "════════════════════════════════════════════════════════════════"
echo ""

source ../azure-config.env

FUNCTION_KEY=$(az functionapp keys list \
  --resource-group $AZURE_RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --query "functionKeys.default" -o tsv)

echo "API URL: $FUNCTION_APP_URL"
echo "Function Key: $FUNCTION_KEY"
echo ""
echo "⚠️  SAVE THESE CREDENTIALS!"
echo ""

# Save to credentials file
cat > ../api-credentials.txt << EOF
YOLO Training API Credentials
=============================

API URL:
$FUNCTION_APP_URL/api/train

Function Key:
$FUNCTION_KEY

Endpoints:
• POST   /api/train           - Start training
• GET    /api/status/{job_id} - Check status
• GET    /api/logs/{job_id}   - View logs
• DELETE /api/cleanup/{job_id} - Cleanup

Example Request:
curl -X POST "$FUNCTION_APP_URL/api/train?code=$FUNCTION_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "coco_zip_path": "my_dataset.zip",
    "base_model_path": "yolo11n-seg.pt",
    "epochs": 100
  }'

Documentation:
• DEPLOYMENT_GUIDE.md - Complete setup guide
• API_README.md - API reference
• SOLUTION_SUMMARY.md - Architecture overview
EOF

echo "✅ Credentials saved to: api-credentials.txt"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Step 6: Test API (Optional)"
echo "════════════════════════════════════════════════════════════════"
echo ""

read -p "Do you want to run a test training job? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
  ./test-api.sh
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ SETUP COMPLETE!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Your training API is ready! 🎉"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Give your frontend developer:"
echo "   • API URL: $FUNCTION_APP_URL"
echo "   • Function Key: (see api-credentials.txt)"
echo "   • Documentation: API_README.md"
echo ""
echo "2. Frontend integration example:"
echo "   curl -X POST '$FUNCTION_APP_URL/api/train?code=FUNCTION_KEY' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"coco_zip_path\":\"dataset.zip\",\"base_model_path\":\"model.pt\"}'"
echo ""
echo "3. Monitor training:"
echo "   curl '$FUNCTION_APP_URL/api/status/JOB_ID?code=FUNCTION_KEY'"
echo ""
echo "📚 Documentation:"
echo "   • SOLUTION_SUMMARY.md - Start here!"
echo "   • DEPLOYMENT_GUIDE.md - Detailed setup"
echo "   • API_README.md - Quick reference"
echo ""
echo "════════════════════════════════════════════════════════════════"
