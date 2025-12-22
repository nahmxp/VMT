# 🎓 Student Account Setup Guide - CPU Testing

> **For Azure Student Account ($100 credit, no GPU access)**

This guide will help you test the complete deployment pipeline using **CPU-only** containers (no GPU required).

---

## 📋 Prerequisites Check

### ✅ What You Need Locally

1. **Azure CLI**
   ```bash
   # Check if installed
   az --version
   
   # If not, install:
   # Linux/WSL:
   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
   
   # Mac:
   brew install azure-cli
   ```

2. **Docker**
   ```bash
   # Check if installed
   docker --version
   
   # If not, install from: https://docs.docker.com/get-docker/
   # Linux:
   sudo apt-get update
   sudo apt-get install docker.io
   sudo systemctl start docker
   sudo usermod -aG docker $USER  # Then logout/login
   ```

3. **Azure Functions Core Tools**
   ```bash
   # Check if installed
   func --version
   
   # If not, install:
   # Linux/WSL:
   wget -q https://packages.microsoft.com/config/ubuntu/20.04/packages-microsoft-prod.deb
   sudo dpkg -i packages-microsoft-prod.deb
   sudo apt-get update
   sudo apt-get install azure-functions-core-tools-4
   
   # Mac:
   brew tap azure/functions
   brew install azure-functions-core-tools@4
   ```

4. **Python 3.11** (for local testing)
   ```bash
   python3 --version
   ```

---

## 🔧 Part 1: Prepare CPU-Compatible Code

### Step 1: Create CPU Dockerfile

We'll create a CPU-only version for testing:

```bash
cd /media/Dev/NDEV/VMT
```

Create file `Dockerfile.train.cpu`:

```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git ffmpeg curl libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    python3 -m pip install -r /app/requirements.txt

COPY . /app

RUN mkdir -p /app/workdir /app/runs

ENTRYPOINT ["python3", "app.py"]
```

### Step 2: Modify Function App for CPU

We need to remove GPU requirements from the Function App.

**Changes needed in `azure-function/function_app.py`:**

Find this section (around line 115):
```python
# GPU resource (NVIDIA Tesla K80, T4, V100, etc.)
gpu_resource = GpuResource(count=1, sku="K80")  # Change SKU as needed

# Resource requirements
resource_requirements = ResourceRequirements(
    requests=ResourceRequests(
        memory_in_gb=16,
        cpu=4,
        gpu=gpu_resource,
    )
)
```

**Replace with** (CPU-only):
```python
# CPU-only resource requirements (for testing without GPU)
resource_requirements = ResourceRequirements(
    requests=ResourceRequests(
        memory_in_gb=8,   # Reduced for student account
        cpu=2,            # 2 cores for testing
    )
)
```

Also update the command (around line 70) to use CPU:
```python
# Container command arguments
command = [
    "--coco-zip", f"/mnt/datasets/{coco_zip_path}",
    "--base-model", f"/mnt/models/{base_model_path}",
    "--work-dir", "/app/workdir",
    "--tflite-out-dir", f"/mnt/outputs/tflite/{job_id}",
    "--epochs", str(epochs),
    "--patience", str(patience),
    "--batch", str(batch),
    "--imgsz", str(imgsz),
    "--device", "cpu",  # Changed from "0" to "cpu"
]
```

---

## ☁️ Part 2: Azure Setup (Step-by-Step)

### Step 1: Login to Azure

```bash
# Login to your Azure student account
az login

# Verify you're logged in
az account show

# You should see your student subscription
```

**Expected output:**
```json
{
  "name": "Azure for Students",
  "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "...",
  "state": "Enabled"
}
```

### Step 2: Check Available Regions

Student accounts have limited regions. Let's check:

```bash
# Check which regions support Container Instances
az provider show --namespace Microsoft.ContainerInstance \
  --query "resourceTypes[?resourceType=='containerGroups'].locations" -o table
```

**Recommended regions for students:**
- `eastus`
- `westus`
- `westeurope`
- `centralus`

### Step 3: Create Resource Group

```bash
# Set variables
export PROJECT_NAME="yolotest"
export LOCATION="eastus"  # Choose based on Step 2

# Create resource group
az group create \
  --name "${PROJECT_NAME}-rg" \
  --location "$LOCATION"
```

**Expected output:**
```json
{
  "location": "eastus",
  "name": "yolotest-rg",
  "properties": {
    "provisioningState": "Succeeded"
  }
}
```

✅ **Resource Group created!**

### Step 4: Create Storage Account

```bash
# Storage account name (must be globally unique, lowercase, no hyphens)
export STORAGE_ACCOUNT="${PROJECT_NAME}storage$RANDOM"

az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "${PROJECT_NAME}-rg" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2
```

**Expected output:**
```json
{
  "provisioningState": "Succeeded",
  "name": "yoloteststorage12345"
}
```

✅ **Storage Account created!**

### Step 5: Create Azure File Shares

```bash
# Get storage key
export STORAGE_KEY=$(az storage account keys list \
  --resource-group "${PROJECT_NAME}-rg" \
  --account-name "$STORAGE_ACCOUNT" \
  --query '[0].value' -o tsv)

# Create file shares
az storage share create \
  --name "datasets" \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --quota 10  # 10 GB for testing

az storage share create \
  --name "models" \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --quota 5

az storage share create \
  --name "outputs" \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --quota 5
```

**Expected output:**
```json
{
  "created": true
}
```

✅ **File Shares created: datasets, models, outputs**

### Step 6: Create Azure Container Registry

```bash
# ACR name (must be globally unique, alphanumeric only)
export ACR_NAME="${PROJECT_NAME}acr$RANDOM"

az acr create \
  --resource-group "${PROJECT_NAME}-rg" \
  --name "$ACR_NAME" \
  --sku Basic \
  --admin-enabled true
```

**Expected output:**
```json
{
  "provisioningState": "Succeeded",
  "loginServer": "yolotestacr12345.azurecr.io"
}
```

✅ **Container Registry created!**

### Step 7: Get ACR Credentials

```bash
export ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
export ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
export ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query passwords[0].value -o tsv)

# Display credentials
echo "ACR Login Server: $ACR_LOGIN_SERVER"
echo "ACR Username: $ACR_USERNAME"
echo "ACR Password: $ACR_PASSWORD"
```

✅ **ACR Credentials obtained!**

---

## 🐳 Part 3: Build & Push Docker Image (Local)

### Step 1: Build CPU Docker Image Locally

```bash
cd /media/Dev/NDEV/VMT

# Build the CPU version
docker build -f Dockerfile.train.cpu -t yolo-trainer-cpu:latest .
```

**This will take 5-10 minutes.** You'll see:
```
Step 1/8 : FROM python:3.11-slim
Step 2/8 : ENV PYTHONUNBUFFERED=1
...
Successfully built abc123def456
Successfully tagged yolo-trainer-cpu:latest
```

✅ **Docker image built locally!**

### Step 2: Tag Image for ACR

```bash
docker tag yolo-trainer-cpu:latest $ACR_LOGIN_SERVER/yolo-trainer:latest
```

### Step 3: Login to ACR

```bash
az acr login --name "$ACR_NAME"
```

**Expected output:**
```
Login Succeeded
```

### Step 4: Push Image to ACR

```bash
docker push $ACR_LOGIN_SERVER/yolo-trainer:latest
```

**This will take 3-5 minutes.** You'll see:
```
The push refers to repository [yolotestacr12345.azurecr.io/yolo-trainer]
abc123: Pushed
def456: Pushed
latest: digest: sha256:... size: 1234
```

✅ **Image pushed to Azure Container Registry!**

---

## 🔧 Part 4: Create Function App

### Step 1: Create App Service Plan (Linux)

```bash
az functionapp plan create \
  --resource-group "${PROJECT_NAME}-rg" \
  --name "${PROJECT_NAME}-plan" \
  --location "$LOCATION" \
  --is-linux \
  --sku B1
```

**Cost:** ~$13/month (consumption model would be cheaper but B1 is more reliable)

✅ **App Service Plan created!**

### Step 2: Create Function App

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

**Expected output:**
```json
{
  "state": "Running",
  "defaultHostName": "yolotest-api.azurewebsites.net"
}
```

✅ **Function App created!**

### Step 3: Enable Managed Identity

```bash
export FUNCTION_PRINCIPAL_ID=$(az functionapp identity assign \
  --resource-group "${PROJECT_NAME}-rg" \
  --name "$FUNCTION_APP" \
  --query principalId -o tsv)

echo "Function Managed Identity: $FUNCTION_PRINCIPAL_ID"
```

### Step 4: Assign Permissions

```bash
export SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Assign Contributor role for ACI creation
az role assignment create \
  --assignee "$FUNCTION_PRINCIPAL_ID" \
  --role "Contributor" \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/${PROJECT_NAME}-rg"
```

✅ **Permissions assigned!**

### Step 5: Configure Function App Settings

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

**Note:** We set smaller defaults for CPU testing:
- epochs: 5 (instead of 100)
- batch: 8 (instead of 24)
- imgsz: 320 (instead of 640)

✅ **Function App configured!**

---

## 📦 Part 5: Prepare Test Data (Local)

### Step 1: Create Minimal Test Dataset

For testing, we'll use a tiny dataset (10-20 images):

```bash
cd /media/Dev/NDEV/VMT

# If you don't have a COCO dataset, create a minimal one
# (or use your existing dataset but with fewer images)
```

### Step 2: Get Base Model

```bash
# Download YOLO11n-seg model (nano - smallest)
curl -L -o yolo11n-seg.pt \
  https://github.com/ultralytics/assets/releases/download/v8.2.0/yolo11n-seg.pt
```

### Step 3: Upload to Azure Files

```bash
# Upload dataset
az storage file upload \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --share-name "datasets" \
  --source "/path/to/your/coco_dataset.zip" \
  --path "test_dataset.zip"

# Upload model
az storage file upload \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --share-name "models" \
  --source "yolo11n-seg.pt" \
  --path "yolo11n-seg.pt"
```

**Verify uploads:**
```bash
# List datasets
az storage file list \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --share-name "datasets" \
  --output table

# List models
az storage file list \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --share-name "models" \
  --output table
```

✅ **Data uploaded!**

---

## 🚀 Part 6: Deploy Function App Code (Local)

### Step 1: Install Function Dependencies Locally

```bash
cd /media/Dev/NDEV/VMT/azure-function

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Deploy Function App

```bash
# Deploy to Azure
func azure functionapp publish "$FUNCTION_APP" --python
```

**This will take 3-5 minutes.** You'll see:
```
Getting site publishing info...
Uploading package...
Upload completed successfully.
Syncing triggers...
Functions in yolotest-api:
    cleanup - [DELETE] /api/cleanup/{job_id}
    logs - [GET] /api/logs/{job_id}
    status - [GET] /api/status/{job_id}
    train - [POST] /api/train
```

✅ **Function App deployed!**

---

## 🧪 Part 7: Test the API

### Step 1: Get Function Key

```bash
export FUNCTION_KEY=$(az functionapp keys list \
  --resource-group "${PROJECT_NAME}-rg" \
  --name "$FUNCTION_APP" \
  --query "functionKeys.default" -o tsv)

echo "Function Key: $FUNCTION_KEY"
```

### Step 2: Test Training Endpoint

```bash
# Start a test training job (small dataset, 5 epochs)
curl -X POST "$FUNCTION_APP_URL/api/train?code=$FUNCTION_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "coco_zip_path": "test_dataset.zip",
    "base_model_path": "yolo11n-seg.pt",
    "epochs": 5,
    "patience": 3,
    "batch": 8,
    "imgsz": 320
  }' | jq .
```

**Expected response:**
```json
{
  "job_id": "abc12345",
  "status": "provisioning",
  "container_group_name": "training-abc12345",
  "status_url": "https://yolotest-api.azurewebsites.net/api/status/abc12345",
  "message": "Training job started successfully"
}
```

✅ **Training started!**

### Step 3: Monitor Status

```bash
export JOB_ID="abc12345"  # Use your actual job ID

# Check status every 30 seconds
watch -n 30 "curl -s '$FUNCTION_APP_URL/api/status/$JOB_ID?code=$FUNCTION_KEY' | jq ."
```

### Step 4: View Logs

```bash
# Get logs
curl "$FUNCTION_APP_URL/api/logs/$JOB_ID?code=$FUNCTION_KEY&tail=100" | jq -r .logs
```

### Step 5: Check in Azure Portal

1. Go to https://portal.azure.com
2. Navigate to Resource Groups → `yolotest-rg`
3. Find Container Instance: `training-{job_id}`
4. Click "Containers" → "Logs" to see live output

---

## 💰 Cost Monitoring

### Check Current Spending

```bash
# Check resource costs
az consumption usage list \
  --start-date $(date -d "1 month ago" +%Y-%m-%d) \
  --end-date $(date +%Y-%m-%d) \
  --query "[?contains(instanceId, '${PROJECT_NAME}')]"
```

### Estimated Costs for Testing

| Resource | Cost |
|----------|------|
| Container Instance (CPU, 2 cores, 2 hours) | ~$0.50 |
| Storage (20 GB) | ~$0.40/month |
| Function App (B1) | ~$13/month |
| Container Registry (Basic) | ~$5/month |
| **Total for 1 test run** | **~$0.90** |
| **Monthly fixed** | **~$18/month** |

**You can do ~10 test runs within your $100 credit!**

---

## 🧹 Clean Up Resources

When you're done testing:

```bash
# Delete entire resource group
az group delete \
  --name "${PROJECT_NAME}-rg" \
  --yes \
  --no-wait

# This will delete:
# - Storage Account
# - File Shares
# - Container Registry
# - Function App
# - All containers
```

---

## 📋 Quick Command Reference

```bash
# Save all variables for later use
cat > ~/.azure-yolo-test.env << EOF
export PROJECT_NAME="yolotest"
export LOCATION="eastus"
export STORAGE_ACCOUNT="$STORAGE_ACCOUNT"
export STORAGE_KEY="$STORAGE_KEY"
export ACR_NAME="$ACR_NAME"
export ACR_LOGIN_SERVER="$ACR_LOGIN_SERVER"
export ACR_USERNAME="$ACR_USERNAME"
export ACR_PASSWORD="$ACR_PASSWORD"
export FUNCTION_APP="$FUNCTION_APP"
export FUNCTION_APP_URL="$FUNCTION_APP_URL"
export FUNCTION_KEY="$FUNCTION_KEY"
export TRAINING_IMAGE="$TRAINING_IMAGE"
EOF

# Load variables in future sessions
source ~/.azure-yolo-test.env
```

---

## ⏱️ Timeline Estimate

| Step | Time |
|------|------|
| Install prerequisites | 10-15 min |
| Azure setup (Steps 1-7) | 15-20 min |
| Build & push Docker image | 10-15 min |
| Create Function App | 10 min |
| Upload test data | 5 min |
| Deploy function code | 5 min |
| Test API | 5 min |
| **Total** | **60-75 minutes** |

**Training time (CPU):** 30-60 minutes for 5 epochs on small dataset

---

## ✅ Success Checklist

- [ ] All prerequisites installed
- [ ] Azure resources created
- [ ] Docker image built and pushed
- [ ] Function App deployed
- [ ] Test data uploaded
- [ ] API endpoint tested
- [ ] Training job started
- [ ] Status endpoint working
- [ ] Logs visible
- [ ] Model saved to outputs

---

## 🆘 Common Issues

### Issue: "Quota exceeded for resource"
**Solution:** Student accounts have limited quotas. Use smaller resources:
- CPU: 2 cores max
- Memory: 8GB max
- Storage: 20GB total

### Issue: "ACR name already taken"
**Solution:** ACR names must be globally unique. Add more randomness:
```bash
export ACR_NAME="${PROJECT_NAME}acr$(date +%s)"
```

### Issue: "Function deployment failed"
**Solution:** Check logs:
```bash
az functionapp log tail --name "$FUNCTION_APP" --resource-group "${PROJECT_NAME}-rg"
```

### Issue: "Container provisioning failed"
**Solution:** Check region availability. Try different region:
```bash
export LOCATION="westus"
```

---

## 🎯 Next Steps After Testing

Once you verify everything works with CPU:

1. **For Production:** Use GPU-enabled setup with paid subscription
2. **For Frontend:** Give them:
   - API URL: `$FUNCTION_APP_URL`
   - Function Key: `$FUNCTION_KEY`
   - API documentation

3. **Scale Up:** When ready, switch to GPU version by:
   - Using `Dockerfile.train.gpu`
   - Requesting GPU quota
   - Updating function_app.py to use GPU

---

**Ready to start? Begin with Part 1, Step 1!** 🚀
