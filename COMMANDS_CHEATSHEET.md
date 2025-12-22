# 🎓 Student Account - Quick Command Sheet

## Copy-Paste Commands (In Order)

### 1️⃣ Set Variables (Edit these first!)
```bash
export PROJECT_NAME="yolotest"
export LOCATION="eastus"  # or westus, westeurope
```

### 2️⃣ Create Resource Group
```bash
az group create --name "${PROJECT_NAME}-rg" --location "$LOCATION"
```

### 3️⃣ Create Storage Account
```bash
export STORAGE_ACCOUNT="${PROJECT_NAME}storage$RANDOM"
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "${PROJECT_NAME}-rg" \
  --location "$LOCATION" \
  --sku Standard_LRS
```

### 4️⃣ Get Storage Key
```bash
export STORAGE_KEY=$(az storage account keys list \
  --resource-group "${PROJECT_NAME}-rg" \
  --account-name "$STORAGE_ACCOUNT" \
  --query '[0].value' -o tsv)
```

### 5️⃣ Create File Shares
```bash
for share in datasets models outputs; do
  az storage share create \
    --name "$share" \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --quota 10
done
```

### 6️⃣ Create Container Registry
```bash
export ACR_NAME="${PROJECT_NAME}acr$RANDOM"
az acr create \
  --resource-group "${PROJECT_NAME}-rg" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true
```

### 7️⃣ Get ACR Credentials
```bash
export ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
export ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
export ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query passwords[0].value -o tsv)
```

### 8️⃣ Build & Push Docker Image
```bash
cd /media/Dev/NDEV/VMT
docker build -f Dockerfile.train.cpu -t yolo-trainer-cpu:latest .
docker tag yolo-trainer-cpu:latest $ACR_LOGIN_SERVER/yolo-trainer:latest
az acr login --name "$ACR_NAME"
docker push $ACR_LOGIN_SERVER/yolo-trainer:latest
```

### 9️⃣ Create Function App Plan
```bash
az functionapp plan create \
  --resource-group "${PROJECT_NAME}-rg" \
  --name "${PROJECT_NAME}-plan" \
  --location "$LOCATION" \
  --is-linux \
  --sku B1
```

### 🔟 Create Function App
```bash
export FUNCTION_APP="${PROJECT_NAME}-api"
az functionapp create \
  --resource-group "${PROJECT_NAME}-rg" \
  --name "$FUNCTION_APP" \
  --storage-account "$STORAGE_ACCOUNT" \
  --plan "${PROJECT_NAME}-plan" \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4
```

### 1️⃣1️⃣ Enable Managed Identity & Assign Role
```bash
export FUNCTION_PRINCIPAL_ID=$(az functionapp identity assign \
  --resource-group "${PROJECT_NAME}-rg" \
  --name "$FUNCTION_APP" \
  --query principalId -o tsv)

export SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az role assignment create \
  --assignee "$FUNCTION_PRINCIPAL_ID" \
  --role "Contributor" \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/${PROJECT_NAME}-rg"
```

### 1️⃣2️⃣ Configure Function App Settings
```bash
export TRAINING_IMAGE="$ACR_LOGIN_SERVER/yolo-trainer:latest"
export FUNCTION_APP_URL="https://${FUNCTION_APP}.azurewebsites.net"

az functionapp config appsettings set \
  --resource-group "${PROJECT_NAME}-rg" \
  --name "$FUNCTION_APP" \
  --settings \
    AZURE_SUBSCRIPTION_ID="$SUBSCRIPTION_ID" \
    AZURE_RESOURCE_GROUP="${PROJECT_NAME}-rg" \
    AZURE_LOCATION="$LOCATION" \
    ACR_LOGIN_SERVER="$ACR_LOGIN_SERVER" \
    ACR_USERNAME="$ACR_USERNAME" \
    ACR_PASSWORD="$ACR_PASSWORD" \
    TRAINING_IMAGE="$TRAINING_IMAGE" \
    STORAGE_ACCOUNT_NAME="$STORAGE_ACCOUNT" \
    STORAGE_ACCOUNT_KEY="$STORAGE_KEY" \
    DATASET_SHARE_NAME="datasets" \
    MODEL_SHARE_NAME="models" \
    OUTPUT_SHARE_NAME="outputs" \
    FUNCTION_APP_URL="$FUNCTION_APP_URL" \
    DEFAULT_EPOCHS="5" \
    DEFAULT_PATIENCE="3" \
    DEFAULT_BATCH="8" \
    DEFAULT_IMGSZ="320"
```

### 1️⃣3️⃣ Upload Files
```bash
# Upload dataset
az storage file upload \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --share-name "datasets" \
  --source "/path/to/your/dataset.zip" \
  --path "test_dataset.zip"

# Upload model
az storage file upload \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --share-name "models" \
  --source "/path/to/yolo11n-seg.pt" \
  --path "yolo11n-seg.pt"
```

### 1️⃣4️⃣ Deploy Function App (Use CPU version!)
```bash
cd /media/Dev/NDEV/VMT/azure-function

# IMPORTANT: Copy CPU version over the original
cp function_app_cpu.py function_app.py

# Deploy
func azure functionapp publish "$FUNCTION_APP" --python
```

### 1️⃣5️⃣ Get Function Key
```bash
export FUNCTION_KEY=$(az functionapp keys list \
  --resource-group "${PROJECT_NAME}-rg" \
  --name "$FUNCTION_APP" \
  --query "functionKeys.default" -o tsv)

echo "=========================="
echo "API URL: $FUNCTION_APP_URL"
echo "Function Key: $FUNCTION_KEY"
echo "=========================="
```

### 1️⃣6️⃣ Test API
```bash
# Start training
curl -X POST "$FUNCTION_APP_URL/api/train?code=$FUNCTION_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "coco_zip_path": "test_dataset.zip",
    "base_model_path": "yolo11n-seg.pt",
    "epochs": 5,
    "batch": 8,
    "imgsz": 320
  }' | jq .

# Get job ID from response, then check status:
export JOB_ID="abc12345"  # Replace with actual job ID

# Check status
curl "$FUNCTION_APP_URL/api/status/$JOB_ID?code=$FUNCTION_KEY" | jq .

# View logs
curl "$FUNCTION_APP_URL/api/logs/$JOB_ID?code=$FUNCTION_KEY&tail=50" | jq -r .logs
```

---

## 💾 Save All Variables
```bash
cat > ~/azure-yolo-vars.sh << EOF
export PROJECT_NAME="$PROJECT_NAME"
export LOCATION="$LOCATION"
export STORAGE_ACCOUNT="$STORAGE_ACCOUNT"
export STORAGE_KEY="$STORAGE_KEY"
export ACR_NAME="$ACR_NAME"
export ACR_LOGIN_SERVER="$ACR_LOGIN_SERVER"
export ACR_USERNAME="$ACR_USERNAME"
export ACR_PASSWORD="$ACR_PASSWORD"
export FUNCTION_APP="$FUNCTION_APP"
export FUNCTION_APP_URL="$FUNCTION_APP_URL"
export FUNCTION_KEY="$FUNCTION_KEY"
export SUBSCRIPTION_ID="$SUBSCRIPTION_ID"
EOF

# Later, reload with:
source ~/azure-yolo-vars.sh
```

---

## 🧹 Clean Up Everything
```bash
az group delete --name "${PROJECT_NAME}-rg" --yes --no-wait
```

---

## 🆘 Quick Troubleshooting

### Check if resources exist
```bash
az resource list --resource-group "${PROJECT_NAME}-rg" --output table
```

### View Function App logs
```bash
az functionapp log tail --name "$FUNCTION_APP" --resource-group "${PROJECT_NAME}-rg"
```

### List containers
```bash
az container list --resource-group "${PROJECT_NAME}-rg" --output table
```

### Get container logs
```bash
az container logs --resource-group "${PROJECT_NAME}-rg" --name "training-JOB_ID"
```

### Check storage files
```bash
az storage file list \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --share-name "datasets" \
  --output table
```

---

## ⏱️ Expected Times
- Azure setup: 20 minutes
- Docker build: 10 minutes  
- Docker push: 5 minutes
- Function deploy: 5 minutes
- **Total setup: ~40 minutes**
- **Training (CPU, 5 epochs): 30-60 minutes**
