# YOLO Training API - Complete Setup Guide

## 🎯 Overview

This guide walks you through setting up a complete Azure-based training pipeline where:
1. Your frontend portal has a **"Train" button**
2. Clicking it calls a **REST API endpoint**
3. The API creates an **Azure Container Instance** with GPU
4. The container **mounts Azure Files** (dataset, model, output)
5. Training runs automatically via [app.py](../app.py)
6. The **TFLite model is saved** to Azure Files
7. The **container is destroyed** after completion

### Architecture

```
Frontend Portal (Train Button)
    ↓ HTTP POST
Azure Function API (/api/train)
    ↓ Creates
Azure Container Instance (GPU-enabled)
    ├─ Mounts: Azure Files (datasets/, models/, outputs/)
    ├─ Runs: app.py (COCO → YOLO → Augment → Train → TFLite)
    └─ Saves: TFLite model to Azure Files
    ↓ Auto-destroys
Container cleaned up
```

---

## 📋 Prerequisites

Before starting, ensure you have:

1. **Azure Subscription** with permissions to create resources
2. **Azure CLI** installed ([Install Guide](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli))
3. **Docker** installed and running
4. **Azure Functions Core Tools** ([Install Guide](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local))
5. **Python 3.11+** (for local testing)
6. **A COCO-format dataset ZIP file**
7. **A base YOLO model** (e.g., `yolo11n-seg.pt`)

---

## 🚀 Step-by-Step Setup

### Step 1: Clone/Prepare Your Project

```bash
cd /path/to/your/project
# Ensure you have these files:
# - app.py
# - Dockerfile.train.gpu
# - requirements.txt
# - azure-function/function_app.py
# - scripts/setup-azure-infrastructure.sh
```

### Step 2: Login to Azure

```bash
az login
az account set --subscription "Your Subscription Name or ID"
```

### Step 3: Run Infrastructure Setup

This script creates all required Azure resources:
- Resource Group
- Storage Account with File Shares (datasets, models, outputs)
- Azure Container Registry (ACR)
- Docker image build & push to ACR
- Azure Function App (Python 3.11)
- Managed Identity with proper permissions

```bash
cd scripts
chmod +x setup-azure-infrastructure.sh
./setup-azure-infrastructure.sh
```

**What this script does:**
- Creates resource group `yolotraining-rg`
- Creates storage account `yolotrainingstorage`
- Creates 3 Azure File shares: `datasets`, `models`, `outputs`
- Creates ACR `yolotrainingacr`
- Builds and pushes Docker image to ACR
- Creates Function App `yolotraining-api`
- Configures all environment variables
- Saves configuration to `azure-config.env`

**Expected output:**
```
[INFO] Creating Resource Group: yolotraining-rg
[INFO] Creating Storage Account: yolotrainingstorage
[INFO] Creating Azure File Shares
[INFO]   ✓ Created share: datasets
[INFO]   ✓ Created share: models
[INFO]   ✓ Created share: outputs
[INFO] Creating Azure Container Registry: yolotrainingacr
[INFO] ACR created: yolotrainingacr.azurecr.io
[INFO] Building and pushing training Docker image to ACR
[INFO] Training image pushed: yolotrainingacr.azurecr.io/yolo-trainer:latest
...
[INFO] ============================================
[INFO] Azure Infrastructure Setup Complete!
[INFO] ============================================
```

⏱️ **Expected time:** 5-10 minutes

### Step 4: Upload Dataset and Model

Upload your COCO dataset ZIP and base YOLO model to Azure Files:

```bash
chmod +x upload-files.sh

# Upload dataset and model
./upload-files.sh /path/to/your/coco_dataset.zip /path/to/yolo11n-seg.pt
```

**Verify uploads:**
```bash
source ../azure-config.env

# List files in datasets share
az storage file list \
  --account-name $STORAGE_ACCOUNT_NAME \
  --account-key $STORAGE_ACCOUNT_KEY \
  --share-name datasets \
  --output table

# List files in models share
az storage file list \
  --account-name $STORAGE_ACCOUNT_NAME \
  --account-key $STORAGE_ACCOUNT_KEY \
  --share-name models \
  --output table
```

### Step 5: Deploy Function App Code

Deploy the Azure Function API:

```bash
chmod +x deploy-function.sh
./deploy-function.sh
```

**What this does:**
- Packages the [function_app.py](../azure-function/function_app.py)
- Deploys to Azure Function App
- Installs Python dependencies

**Expected output:**
```
Deploying Function App: yolotraining-api
...
Deployment successful.
Remote build succeeded!

Function App URL: https://yolotraining-api.azurewebsites.net
```

⏱️ **Expected time:** 2-3 minutes

### Step 6: Get Function Key (API Key)

Your API requires authentication. Get the function key:

```bash
source azure-config.env

az functionapp keys list \
  --resource-group $AZURE_RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --query "functionKeys" -o json
```

**Output example:**
```json
{
  "default": "xQPxK5qx8ZpGsW4..."
}
```

Save this key - you'll need it for API calls.

### Step 7: Test the API

Test the training API endpoint:

```bash
FUNCTION_KEY="your-function-key-from-step-6"
FUNCTION_URL="https://yolotraining-api.azurewebsites.net"

curl -X POST "$FUNCTION_URL/api/train?code=$FUNCTION_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "coco_zip_path": "coco_dataset.zip",
    "base_model_path": "yolo11n-seg.pt",
    "epochs": 10,
    "patience": 5,
    "batch": 16,
    "imgsz": 640
  }'
```

**Expected response:**
```json
{
  "job_id": "a7b3c9d2",
  "status": "provisioning",
  "container_group_name": "training-a7b3c9d2",
  "status_url": "https://yolotraining-api.azurewebsites.net/api/status/a7b3c9d2",
  "message": "Training job started successfully",
  "parameters": {
    "coco_zip_path": "coco_dataset.zip",
    "base_model_path": "yolo11n-seg.pt",
    "epochs": 10,
    "patience": 5,
    "batch": 16,
    "imgsz": 640
  }
}
```

### Step 8: Check Training Status

Monitor training progress using the job ID:

```bash
JOB_ID="a7b3c9d2"  # From previous response

# Check status
curl "$FUNCTION_URL/api/status/$JOB_ID?code=$FUNCTION_KEY"

# Get logs
curl "$FUNCTION_URL/api/logs/$JOB_ID?code=$FUNCTION_KEY&tail=100"
```

**Status response example:**
```json
{
  "job_id": "a7b3c9d2",
  "provisioning_state": "Succeeded",
  "container_state": "Running",
  "status": "running",
  "message": "Training in progress",
  "output_path": "/mnt/outputs/tflite/a7b3c9d2"
}
```

**When training completes:**
```json
{
  "job_id": "a7b3c9d2",
  "status": "completed",
  "exit_code": 0,
  "message": "Training completed successfully",
  "output_path": "/mnt/outputs/tflite/a7b3c9d2"
}
```

### Step 9: Retrieve Trained Model

After training completes, download the TFLite model:

```bash
source azure-config.env
JOB_ID="a7b3c9d2"

# List files in output directory
az storage file list \
  --account-name $STORAGE_ACCOUNT_NAME \
  --account-key $STORAGE_ACCOUNT_KEY \
  --share-name outputs \
  --path "tflite/$JOB_ID" \
  --output table

# Download the TFLite model
az storage file download \
  --account-name $STORAGE_ACCOUNT_NAME \
  --account-key $STORAGE_ACCOUNT_KEY \
  --share-name outputs \
  --path "tflite/$JOB_ID/best_20231220_143022.tflite" \
  --dest "./trained_model.tflite"
```

### Step 10: Cleanup (Optional)

Delete the container after training:

```bash
curl -X DELETE "$FUNCTION_URL/api/cleanup/$JOB_ID?code=$FUNCTION_KEY"
```

**Note:** Containers are configured with `restart_policy=never`, so they won't restart after completion. However, they remain in your resource group until explicitly deleted.

---

## 🌐 Frontend Integration

### API Endpoint for Your Frontend

Give this information to your frontend developer:

**Base URL:**
```
https://yolotraining-api.azurewebsites.net
```

**API Key (Function Key):**
```
xQPxK5qx8ZpGsW4... (from Step 6)
```

### API Endpoints

#### 1. Start Training
```http
POST /api/train?code={FUNCTION_KEY}
Content-Type: application/json

{
  "coco_zip_path": "my_dataset/products_v1.zip",
  "base_model_path": "yolo11n-seg.pt",
  "epochs": 100,
  "patience": 50,
  "batch": 24,
  "imgsz": 640
}
```

**Response (202 Accepted):**
```json
{
  "job_id": "abc12345",
  "status": "provisioning",
  "status_url": "https://yolotraining-api.azurewebsites.net/api/status/abc12345",
  "message": "Training job started successfully"
}
```

#### 2. Check Status
```http
GET /api/status/{job_id}?code={FUNCTION_KEY}
```

**Response (200 OK):**
```json
{
  "job_id": "abc12345",
  "status": "running",  // provisioning, running, completed, failed
  "container_state": "Running",
  "message": "Training in progress"
}
```

#### 3. Get Logs
```http
GET /api/logs/{job_id}?code={FUNCTION_KEY}&tail=100
```

**Response (200 OK):**
```json
{
  "job_id": "abc12345",
  "logs": "[2023-12-20 14:30:22 UTC] Step 1/4: COCO → YOLO conversion\n...",
  "tail": 100
}
```

#### 4. Cleanup Container
```http
DELETE /api/cleanup/{job_id}?code={FUNCTION_KEY}
```

**Response (200 OK):**
```json
{
  "job_id": "abc12345",
  "message": "Training job cleaned up successfully"
}
```

### Frontend Implementation Example (JavaScript)

```javascript
// Training button click handler
async function startTraining() {
  const apiUrl = "https://yolotraining-api.azurewebsites.net";
  const apiKey = "xQPxK5qx8ZpGsW4...";  // Store securely!
  
  const response = await fetch(`${apiUrl}/api/train?code=${apiKey}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      coco_zip_path: "products_dataset.zip",
      base_model_path: "yolo11n-seg.pt",
      epochs: 100,
      patience: 50,
      batch: 24,
      imgsz: 640
    })
  });
  
  const data = await response.json();
  console.log("Training started:", data);
  
  // Start polling for status
  pollTrainingStatus(data.job_id, apiUrl, apiKey);
}

// Poll training status
async function pollTrainingStatus(jobId, apiUrl, apiKey) {
  const checkStatus = async () => {
    const response = await fetch(`${apiUrl}/api/status/${jobId}?code=${apiKey}`);
    const data = await response.json();
    
    console.log("Status:", data.status);
    
    if (data.status === "completed") {
      console.log("Training completed successfully!");
      // Notify user, download model, etc.
    } else if (data.status === "failed") {
      console.error("Training failed:", data.message);
    } else {
      // Continue polling
      setTimeout(checkStatus, 30000);  // Check every 30 seconds
    }
  };
  
  checkStatus();
}
```

---

## 🔧 Configuration

### Environment Variables

All configuration is managed via Azure Function App settings. To update:

```bash
source azure-config.env

az functionapp config appsettings set \
  --resource-group $AZURE_RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --settings \
    DEFAULT_EPOCHS=150 \
    DEFAULT_BATCH=32
```

### Adjust GPU SKU

By default, the API uses K80 GPUs. To use a different GPU:

Edit [function_app.py](../azure-function/function_app.py):
```python
gpu_resource = GpuResource(count=1, sku="V100")  # Options: K80, P100, V100
```

Redeploy:
```bash
cd scripts
./deploy-function.sh
```

### Increase Container Resources

Edit [function_app.py](../azure-function/function_app.py):
```python
resource_requirements = ResourceRequirements(
    requests=ResourceRequests(
        memory_in_gb=32,  # Increase from 16
        cpu=8,            # Increase from 4
        gpu=gpu_resource,
    )
)
```

---

## 📊 Monitoring

### View Container Logs in Azure Portal

1. Go to Azure Portal → Resource Groups → `yolotraining-rg`
2. Find container instance: `training-{job_id}`
3. Click "Containers" → "Logs"

### View Function App Logs

```bash
source azure-config.env

az functionapp log tail \
  --resource-group $AZURE_RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME
```

### Check Azure Files

```bash
source azure-config.env

# List all output files
az storage file list \
  --account-name $STORAGE_ACCOUNT_NAME \
  --account-key $STORAGE_ACCOUNT_KEY \
  --share-name outputs \
  --path "tflite" \
  --output table
```

---

## 🛠️ Troubleshooting

### Issue: "Container provisioning failed"

**Cause:** Insufficient quota for GPU resources in your region.

**Solution:**
1. Request GPU quota increase: [Azure Support](https://portal.azure.com/#blade/Microsoft_Azure_Support/HelpAndSupportBlade)
2. Or use a different region (e.g., `eastus`, `westus2`, `northeurope`)

### Issue: "Cannot find COCO dataset"

**Cause:** Dataset path incorrect or not uploaded.

**Solution:**
```bash
# Verify file exists
source azure-config.env
az storage file list \
  --account-name $STORAGE_ACCOUNT_NAME \
  --share-name datasets \
  --output table

# Upload if missing
./scripts/upload-files.sh /path/to/dataset.zip
```

### Issue: "Training fails with OOM (Out of Memory)"

**Cause:** Batch size too large for GPU memory.

**Solution:** Reduce batch size in API call:
```json
{
  "batch": 16  // Reduce from 24
}
```

### Issue: "Function App times out"

**Cause:** Container creation takes longer than expected.

**Solution:** This is normal - the function returns immediately after starting container provisioning. Check status via `/api/status/{job_id}`.

---

## 💰 Cost Estimation

Approximate costs for 1 training job (100 epochs, ~2-4 hours):

| Resource | Usage | Cost (USD) |
|----------|-------|------------|
| Azure Container Instance (GPU K80) | 3 hours | ~$3.00 |
| Storage Account (1TB) | 1 month | ~$20.00 |
| Function App (B1 plan) | 1 month | ~$13.00 |
| Container Registry (Basic) | 1 month | ~$5.00 |
| Data Transfer | ~5GB | ~$0.50 |

**Total per training:** ~$3.50 (excluding monthly fixed costs)

**Monthly fixed costs:** ~$38.00

---

## 🔐 Security Best Practices

1. **Use Managed Identity:** Prefer managed identity over ACR username/password
2. **Secure API Keys:** Store function keys in Azure Key Vault or environment variables
3. **Network Isolation:** Use VNet integration for Function App and ACI
4. **Private Endpoints:** Enable private endpoints for Storage Account
5. **RBAC:** Use role-based access control instead of storage account keys

---

## 📚 Additional Resources

- [Azure Container Instances Documentation](https://docs.microsoft.com/en-us/azure/container-instances/)
- [Azure Functions Python Guide](https://docs.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Azure Files Documentation](https://docs.microsoft.com/en-us/azure/storage/files/)
- [Ultralytics YOLO Documentation](https://docs.ultralytics.com/)

---

## 🎉 You're Done!

Your training API is now ready! Your frontend developer can integrate the training button with the API endpoint.

**Final API URL to share:**
```
https://yolotraining-api.azurewebsites.net/api/train
```

**Function Key to share (securely):**
```
xQPxK5qx8ZpGsW4... (from az functionapp keys list)
```

---

## 📝 Quick Reference

```bash
# Start training
curl -X POST "https://yolotraining-api.azurewebsites.net/api/train?code=KEY" \
  -H "Content-Type: application/json" \
  -d '{"coco_zip_path":"dataset.zip","base_model_path":"yolo11n-seg.pt"}'

# Check status
curl "https://yolotraining-api.azurewebsites.net/api/status/JOB_ID?code=KEY"

# Get logs
curl "https://yolotraining-api.azurewebsites.net/api/logs/JOB_ID?code=KEY"

# Cleanup
curl -X DELETE "https://yolotraining-api.azurewebsites.net/api/cleanup/JOB_ID?code=KEY"
```
