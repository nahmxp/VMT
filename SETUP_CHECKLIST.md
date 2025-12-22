# ✅ Step-by-Step Checklist

## 📦 Prerequisites (Do First!)

### On Your Local Machine:

- [ ] **Azure CLI installed**
  ```bash
  az --version
  # If not: curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
  ```

- [ ] **Docker installed and running**
  ```bash
  docker --version
  sudo systemctl status docker
  ```

- [ ] **Azure Functions Core Tools installed**
  ```bash
  func --version
  # If not: sudo apt-get install azure-functions-core-tools-4
  ```

- [ ] **Python 3.11+ installed**
  ```bash
  python3 --version
  ```

- [ ] **jq installed (for JSON formatting)**
  ```bash
  sudo apt-get install jq
  ```

---

## 🌐 Azure Setup Steps

### Part A: Authentication & Base Setup

- [ ] **Login to Azure**
  ```bash
  az login
  ```
  - Opens browser for authentication
  - Select your student account

- [ ] **Verify subscription**
  ```bash
  az account show
  ```
  - Should show "Azure for Students"
  - Credit remaining: check portal

- [ ] **Set project name**
  ```bash
  export PROJECT_NAME="yolotest"
  export LOCATION="eastus"
  ```

---

### Part B: Storage Resources

- [ ] **Create Resource Group**
  ```bash
  az group create --name "${PROJECT_NAME}-rg" --location "$LOCATION"
  ```
  ✅ Output: `"provisioningState": "Succeeded"`

- [ ] **Create Storage Account**
  ```bash
  export STORAGE_ACCOUNT="${PROJECT_NAME}storage$RANDOM"
  az storage account create \
    --name "$STORAGE_ACCOUNT" \
    --resource-group "${PROJECT_NAME}-rg" \
    --location "$LOCATION" \
    --sku Standard_LRS
  ```
  ⏱️ Takes: 1-2 minutes

- [ ] **Get Storage Key**
  ```bash
  export STORAGE_KEY=$(az storage account keys list \
    --resource-group "${PROJECT_NAME}-rg" \
    --account-name "$STORAGE_ACCOUNT" \
    --query '[0].value' -o tsv)
  echo "Storage Key: ${STORAGE_KEY:0:10}..."
  ```

- [ ] **Create 3 File Shares**
  ```bash
  # datasets
  az storage share create --name "datasets" \
    --account-name "$STORAGE_ACCOUNT" --account-key "$STORAGE_KEY" --quota 10
  
  # models
  az storage share create --name "models" \
    --account-name "$STORAGE_ACCOUNT" --account-key "$STORAGE_KEY" --quota 5
  
  # outputs
  az storage share create --name "outputs" \
    --account-name "$STORAGE_ACCOUNT" --account-key "$STORAGE_KEY" --quota 5
  ```
  ✅ Each should return: `"created": true`

---

### Part C: Container Registry

- [ ] **Create ACR**
  ```bash
  export ACR_NAME="${PROJECT_NAME}acr$RANDOM"
  az acr create \
    --resource-group "${PROJECT_NAME}-rg" \
    --name "$ACR_NAME" \
    --sku Basic \
    --admin-enabled true
  ```
  ⏱️ Takes: 2-3 minutes

- [ ] **Get ACR Credentials**
  ```bash
  export ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
  export ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
  export ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query passwords[0].value -o tsv)
  
  echo "ACR: $ACR_LOGIN_SERVER"
  ```
  ✅ Should show: `yolotestacr####.azurecr.io`

---

### Part D: Function App

- [ ] **Create App Service Plan**
  ```bash
  az functionapp plan create \
    --resource-group "${PROJECT_NAME}-rg" \
    --name "${PROJECT_NAME}-plan" \
    --location "$LOCATION" \
    --is-linux \
    --sku B1
  ```
  ⏱️ Takes: 1-2 minutes

- [ ] **Create Function App**
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
  ⏱️ Takes: 2-3 minutes

- [ ] **Enable Managed Identity**
  ```bash
  export FUNCTION_PRINCIPAL_ID=$(az functionapp identity assign \
    --resource-group "${PROJECT_NAME}-rg" \
    --name "$FUNCTION_APP" \
    --query principalId -o tsv)
  echo "Identity: $FUNCTION_PRINCIPAL_ID"
  ```

- [ ] **Assign Permissions**
  ```bash
  export SUBSCRIPTION_ID=$(az account show --query id -o tsv)
  az role assignment create \
    --assignee "$FUNCTION_PRINCIPAL_ID" \
    --role "Contributor" \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/${PROJECT_NAME}-rg"
  ```

- [ ] **Configure Function Settings**
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

---

## 🐳 Local Docker Steps

- [ ] **Navigate to project**
  ```bash
  cd /media/Dev/NDEV/VMT
  ```

- [ ] **Build CPU Docker image**
  ```bash
  docker build -f Dockerfile.train.cpu -t yolo-trainer-cpu:latest .
  ```
  ⏱️ Takes: 10-15 minutes (downloads packages)
  ✅ Should end with: `Successfully built`

- [ ] **Tag image for ACR**
  ```bash
  docker tag yolo-trainer-cpu:latest $ACR_LOGIN_SERVER/yolo-trainer:latest
  ```

- [ ] **Login to ACR**
  ```bash
  az acr login --name "$ACR_NAME"
  ```
  ✅ Should show: `Login Succeeded`

- [ ] **Push image to ACR**
  ```bash
  docker push $ACR_LOGIN_SERVER/yolo-trainer:latest
  ```
  ⏱️ Takes: 5-10 minutes (uploads ~2GB)

---

## 📦 Data Upload

- [ ] **Download/Prepare YOLO model**
  ```bash
  # If you don't have it, download:
  curl -L -o yolo11n-seg.pt \
    https://github.com/ultralytics/assets/releases/download/v8.2.0/yolo11n-seg.pt
  ```

- [ ] **Upload dataset to Azure Files**
  ```bash
  az storage file upload \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --share-name "datasets" \
    --source "/path/to/your/coco_dataset.zip" \
    --path "test_dataset.zip"
  ```
  ⏱️ Time depends on file size

- [ ] **Upload model to Azure Files**
  ```bash
  az storage file upload \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --share-name "models" \
    --source "yolo11n-seg.pt" \
    --path "yolo11n-seg.pt"
  ```

- [ ] **Verify uploads**
  ```bash
  az storage file list \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --share-name "datasets" \
    --output table
  
  az storage file list \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --share-name "models" \
    --output table
  ```
  ✅ Should see your files listed

---

## 🚀 Function App Deployment

- [ ] **Navigate to function directory**
  ```bash
  cd /media/Dev/NDEV/VMT/azure-function
  ```

- [ ] **IMPORTANT: Use CPU version**
  ```bash
  cp function_app_cpu.py function_app.py
  ```

- [ ] **Deploy to Azure**
  ```bash
  func azure functionapp publish "$FUNCTION_APP" --python
  ```
  ⏱️ Takes: 3-5 minutes
  ✅ Should show: "Deployment successful"

- [ ] **Get Function Key**
  ```bash
  export FUNCTION_KEY=$(az functionapp keys list \
    --resource-group "${PROJECT_NAME}-rg" \
    --name "$FUNCTION_APP" \
    --query "functionKeys.default" -o tsv)
  
  echo "======================================"
  echo "API URL: $FUNCTION_APP_URL"
  echo "Function Key: $FUNCTION_KEY"
  echo "======================================"
  ```
  ✅ Save these credentials!

---

## 🧪 Testing

- [ ] **Test API health**
  ```bash
  curl "$FUNCTION_APP_URL/api/train?code=$FUNCTION_KEY"
  ```
  ✅ Should return: 401 or "Method not allowed" (means it's working, just needs POST)

- [ ] **Start training job**
  ```bash
  curl -X POST "$FUNCTION_APP_URL/api/train?code=$FUNCTION_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "coco_zip_path": "test_dataset.zip",
      "base_model_path": "yolo11n-seg.pt",
      "epochs": 5,
      "batch": 8,
      "imgsz": 320
    }' | jq .
  ```
  ✅ Should return job_id and status

- [ ] **Save job ID**
  ```bash
  export JOB_ID="abc12345"  # Replace with actual from response
  ```

- [ ] **Check status**
  ```bash
  curl "$FUNCTION_APP_URL/api/status/$JOB_ID?code=$FUNCTION_KEY" | jq .
  ```

- [ ] **View logs**
  ```bash
  curl "$FUNCTION_APP_URL/api/logs/$JOB_ID?code=$FUNCTION_KEY&tail=50" | jq -r .logs
  ```

- [ ] **Check in Azure Portal**
  - Go to: https://portal.azure.com
  - Navigate to: Resource Groups → `yolotest-rg`
  - Find: Container Instance `training-{job_id}`
  - View: Containers → Logs

- [ ] **Wait for completion** (30-60 minutes for CPU)
  ```bash
  # Keep checking status
  watch -n 30 "curl -s '$FUNCTION_APP_URL/api/status/$JOB_ID?code=$FUNCTION_KEY' | jq ."
  ```

- [ ] **Download trained model (after completion)**
  ```bash
  az storage file list \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --share-name "outputs" \
    --path "tflite/$JOB_ID" \
    --output table
  
  # Download the .tflite file
  az storage file download \
    --account-name "$STORAGE_ACCOUNT" \
    --account-key "$STORAGE_KEY" \
    --share-name "outputs" \
    --path "tflite/$JOB_ID/best_TIMESTAMP.tflite" \
    --dest "./trained_model.tflite"
  ```

---

## 💾 Save Configuration

- [ ] **Save all variables for future use**
  ```bash
  cat > ~/azure-yolo-config.sh << EOF
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
  export TRAINING_IMAGE="$TRAINING_IMAGE"
  EOF
  
  echo "Saved to ~/azure-yolo-config.sh"
  echo "Load with: source ~/azure-yolo-config.sh"
  ```

---

## 📊 Monitor Costs

- [ ] **Check current spending**
  - Visit: https://portal.azure.com
  - Go to: Cost Management + Billing
  - View: Current balance (should start at $100)

- [ ] **Set up cost alert** (Recommended!)
  - Go to: Cost Management
  - Create alert at: $50 spent
  - This will email you

---

## 🎉 Success Criteria

✅ **You've successfully deployed when:**
- [ ] All Azure resources created (no errors)
- [ ] Docker image pushed to ACR
- [ ] Function App deployed and running
- [ ] Test training job started
- [ ] Container created and running
- [ ] Logs visible
- [ ] Training completes
- [ ] TFLite model saved to outputs

---

## 🧹 Cleanup When Done

- [ ] **Delete all resources**
  ```bash
  az group delete --name "${PROJECT_NAME}-rg" --yes --no-wait
  ```
  ⚠️ This deletes EVERYTHING (storage, functions, containers, etc.)

---

## ⏱️ Total Time Estimate

| Phase | Time |
|-------|------|
| Prerequisites check | 5 min |
| Azure setup (A-D) | 20 min |
| Docker build + push | 20 min |
| Data upload | 5 min |
| Function deploy | 5 min |
| Testing | 5 min |
| **Setup Total** | **~60 min** |
| Training (CPU) | 30-60 min |

---

## 📝 Notes

- **Student Account Limits:**
  - CPU only (no GPU)
  - 2 cores max per container
  - Limited regions
  - $100 total credit

- **For Frontend Developer:**
  - API URL: `$FUNCTION_APP_URL`
  - Function Key: `$FUNCTION_KEY`
  - Endpoints: `/api/train`, `/api/status/{id}`, `/api/logs/{id}`

- **Documentation Files:**
  - [STUDENT_ACCOUNT_SETUP.md](STUDENT_ACCOUNT_SETUP.md) - Detailed guide
  - [COMMANDS_CHEATSHEET.md](COMMANDS_CHEATSHEET.md) - Quick commands
  - This file - Checklist

---

**🚀 Ready? Start with Prerequisites!**
