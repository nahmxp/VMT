#!/bin/bash
# Azure Infrastructure Setup Script for YOLO Training Pipeline
# This script creates all required Azure resources

set -e  # Exit on error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================
# Configuration Variables
# ============================================

# Edit these values for your setup
PROJECT_NAME="yolotraining"
LOCATION="eastus"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Resource names (will be prefixed with project name)
RESOURCE_GROUP="${PROJECT_NAME}-rg"
STORAGE_ACCOUNT="${PROJECT_NAME}storage"
ACR_NAME="${PROJECT_NAME}acr"
FUNCTION_APP_NAME="${PROJECT_NAME}-api"
APP_SERVICE_PLAN="${PROJECT_NAME}-plan"

# Azure Files share names
DATASET_SHARE="datasets"
MODEL_SHARE="models"
OUTPUT_SHARE="outputs"

# ============================================
# Step 1: Create Resource Group
# ============================================

echo_info "Creating Resource Group: $RESOURCE_GROUP"
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION"

# ============================================
# Step 2: Create Storage Account & File Shares
# ============================================

echo_info "Creating Storage Account: $STORAGE_ACCOUNT"
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2

# Get storage account key
STORAGE_KEY=$(az storage account keys list \
  --resource-group "$RESOURCE_GROUP" \
  --account-name "$STORAGE_ACCOUNT" \
  --query '[0].value' -o tsv)

echo_info "Creating Azure File Shares"
for share in "$DATASET_SHARE" "$MODEL_SHARE" "$OUTPUT_SHARE"; do
  az storage share create \
    --name "$share" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --quota 1024
  echo_info "  ✓ Created share: $share"
done

# ============================================
# Step 3: Create Azure Container Registry
# ============================================

echo_info "Creating Azure Container Registry: $ACR_NAME"
az acr create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true

# Get ACR credentials
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query passwords[0].value -o tsv)

echo_info "ACR created: $ACR_LOGIN_SERVER"

# ============================================
# Step 4: Build and Push Docker Image to ACR
# ============================================

echo_info "Building and pushing training Docker image to ACR"
cd "$(dirname "$0")/.."  # Go to project root

# Login to ACR
az acr login --name "$ACR_NAME"

# Build and push image
TRAINING_IMAGE="${ACR_LOGIN_SERVER}/yolo-trainer:latest"
docker build -f Dockerfile.train.gpu -t "$TRAINING_IMAGE" .
docker push "$TRAINING_IMAGE"

echo_info "Training image pushed: $TRAINING_IMAGE"

# ============================================
# Step 5: Create App Service Plan (Linux)
# ============================================

echo_info "Creating App Service Plan: $APP_SERVICE_PLAN"
az functionapp plan create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$APP_SERVICE_PLAN" \
  --location "$LOCATION" \
  --is-linux \
  --sku B1

# ============================================
# Step 6: Create Function App
# ============================================

echo_info "Creating Function App: $FUNCTION_APP_NAME"
az functionapp create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FUNCTION_APP_NAME" \
  --storage-account "$STORAGE_ACCOUNT" \
  --plan "$APP_SERVICE_PLAN" \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4

# Enable system-assigned managed identity
echo_info "Enabling managed identity for Function App"
FUNCTION_PRINCIPAL_ID=$(az functionapp identity assign \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FUNCTION_APP_NAME" \
  --query principalId -o tsv)

# Assign Contributor role to managed identity (for creating ACI)
echo_info "Assigning Contributor role to Function App managed identity"
az role assignment create \
  --assignee "$FUNCTION_PRINCIPAL_ID" \
  --role "Contributor" \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"

# ============================================
# Step 7: Configure Function App Settings
# ============================================

echo_info "Configuring Function App settings"

FUNCTION_APP_URL="https://${FUNCTION_APP_NAME}.azurewebsites.net"

az functionapp config appsettings set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FUNCTION_APP_NAME" \
  --settings \
    AZURE_SUBSCRIPTION_ID="$SUBSCRIPTION_ID" \
    AZURE_RESOURCE_GROUP="$RESOURCE_GROUP" \
    AZURE_LOCATION="$LOCATION" \
    ACR_LOGIN_SERVER="$ACR_LOGIN_SERVER" \
    ACR_USERNAME="$ACR_USERNAME" \
    ACR_PASSWORD="$ACR_PASSWORD" \
    TRAINING_IMAGE="$TRAINING_IMAGE" \
    STORAGE_ACCOUNT_NAME="$STORAGE_ACCOUNT" \
    STORAGE_ACCOUNT_KEY="$STORAGE_KEY" \
    DATASET_SHARE_NAME="$DATASET_SHARE" \
    MODEL_SHARE_NAME="$MODEL_SHARE" \
    OUTPUT_SHARE_NAME="$OUTPUT_SHARE" \
    FUNCTION_APP_URL="$FUNCTION_APP_URL" \
    DEFAULT_EPOCHS="100" \
    DEFAULT_PATIENCE="50" \
    DEFAULT_BATCH="24" \
    DEFAULT_IMGSZ="640"

# ============================================
# Step 8: Upload Sample Files to Azure Files
# ============================================

echo_info "Uploading sample base model to Azure Files"

# Check if yolo11n.pt exists
if [ -f "yolo11n.pt" ]; then
  az storage file upload \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --share-name "$MODEL_SHARE" \
    --source "yolo11n.pt" \
    --path "yolo11n-seg.pt"
  echo_info "  ✓ Uploaded yolo11n.pt to models share"
else
  echo_warn "  yolo11n.pt not found in current directory, skipping upload"
fi

# ============================================
# Summary
# ============================================

echo ""
echo_info "============================================"
echo_info "Azure Infrastructure Setup Complete!"
echo_info "============================================"
echo ""
echo_info "Resource Group: $RESOURCE_GROUP"
echo_info "Storage Account: $STORAGE_ACCOUNT"
echo_info "ACR: $ACR_LOGIN_SERVER"
echo_info "Training Image: $TRAINING_IMAGE"
echo_info "Function App: $FUNCTION_APP_NAME"
echo_info "Function URL: $FUNCTION_APP_URL"
echo ""
echo_info "Next Steps:"
echo_info "1. Deploy Function App code:"
echo_info "   cd azure-function && func azure functionapp publish $FUNCTION_APP_NAME"
echo ""
echo_info "2. Upload your COCO dataset ZIP to Azure Files:"
echo_info "   az storage file upload --account-name $STORAGE_ACCOUNT \\"
echo_info "     --share-name $DATASET_SHARE --source /path/to/dataset.zip"
echo ""
echo_info "3. Test the API endpoint:"
echo_info "   curl -X POST '$FUNCTION_APP_URL/api/train?code=YOUR_FUNCTION_KEY' \\"
echo_info "     -H 'Content-Type: application/json' \\"
echo_info "     -d '{\"coco_zip_path\":\"dataset.zip\",\"base_model_path\":\"yolo11n-seg.pt\"}'"
echo ""
echo_info "============================================"

# Save configuration to file
CONFIG_FILE="azure-config.env"
cat > "$CONFIG_FILE" << EOF
# Azure Configuration
# Generated on $(date)

AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID
AZURE_RESOURCE_GROUP=$RESOURCE_GROUP
AZURE_LOCATION=$LOCATION

ACR_LOGIN_SERVER=$ACR_LOGIN_SERVER
ACR_USERNAME=$ACR_USERNAME
ACR_PASSWORD=$ACR_PASSWORD
TRAINING_IMAGE=$TRAINING_IMAGE

STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT
STORAGE_ACCOUNT_KEY=$STORAGE_KEY
DATASET_SHARE_NAME=$DATASET_SHARE
MODEL_SHARE_NAME=$MODEL_SHARE
OUTPUT_SHARE_NAME=$OUTPUT_SHARE

FUNCTION_APP_NAME=$FUNCTION_APP_NAME
FUNCTION_APP_URL=$FUNCTION_APP_URL
EOF

echo_info "Configuration saved to: $CONFIG_FILE"
