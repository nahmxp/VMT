# 🎯 START HERE - Complete Training API Solution

## What You Have Now

A **fully automated Azure-based training pipeline** where your portal's "Train" button triggers:
1. Azure Container Instance (GPU) creation
2. Automatic dataset/model mounting
3. Complete YOLO training pipeline
4. TFLite model export
5. Automatic cleanup

**Everything is ready to deploy!**

---

## 📁 Project Structure

```
VMT/
│
├── 🚀 quick-start.sh                    ← START HERE! (Interactive setup)
│
├── 📚 Documentation
│   ├── SOLUTION_SUMMARY.md             ← Architecture & overview
│   ├── DEPLOYMENT_GUIDE.md             ← Step-by-step instructions
│   └── API_README.md                   ← Quick API reference
│
├── 🐍 Training Code (Your existing code)
│   ├── app.py                          ← Main training script
│   ├── Dockerfile.train.gpu            ← GPU Docker image
│   └── requirements.txt                ← Python dependencies
│
├── ☁️ Azure Function (API)
│   └── azure-function/
│       ├── function_app.py             ← API endpoints
│       ├── requirements.txt            ← Function dependencies
│       ├── host.json                   ← Function config
│       └── .env.template               ← Environment variables
│
└── 🔧 Setup Scripts
    └── scripts/
        ├── setup-azure-infrastructure.sh   ← Creates all Azure resources
        ├── deploy-function.sh              ← Deploys Function App
        ├── upload-files.sh                 ← Upload datasets/models
        ├── test-api.sh                     ← Test API endpoints
        └── api_client.py                   ← Python client library
```

---

## 🚀 Quick Start (15 minutes)

### Option 1: Automated Setup (Recommended)

```bash
./quick-start.sh
```

This interactive script will:
1. ✅ Check prerequisites
2. ✅ Create all Azure resources
3. ✅ Upload your dataset & model
4. ✅ Deploy Function App
5. ✅ Give you API credentials
6. ✅ Optionally test the API

### Option 2: Manual Setup

```bash
# 1. Setup infrastructure (10 min)
cd scripts
./setup-azure-infrastructure.sh

# 2. Upload data (2 min)
./upload-files.sh /path/to/dataset.zip /path/to/model.pt

# 3. Deploy function (3 min)
./deploy-function.sh

# 4. Get API key
source ../azure-config.env
az functionapp keys list --resource-group $AZURE_RESOURCE_GROUP --name $FUNCTION_APP_NAME

# 5. Test
./test-api.sh
```

---

## 📋 Prerequisites

Before running `quick-start.sh`, ensure you have:

- [ ] **Azure subscription** with GPU quota
- [ ] **Azure CLI** installed ([Install](https://aka.ms/azure-cli))
- [ ] **Docker** installed ([Install](https://docs.docker.com/get-docker/))
- [ ] **Azure Functions Core Tools** ([Install](https://aka.ms/func-tools))
- [ ] **COCO dataset ZIP** file ready
- [ ] **Base YOLO model** (yolo11n-seg.pt) ready

---

## 🎯 What to Give Your Frontend Developer

After running setup, you'll get:

### 1. API Endpoint
```
https://yolotraining-api.azurewebsites.net/api/train
```

### 2. Function Key (Authentication)
```
xQPxK5qx8ZpGsW4... (saved in api-credentials.txt)
```

### 3. API Documentation
Share these files:
- `API_README.md` - Quick reference
- Frontend integration examples (see below)

### 4. Example Code

**JavaScript:**
```javascript
async function startTraining() {
  const response = await fetch(
    'https://yolotraining-api.azurewebsites.net/api/train?code=YOUR_KEY',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        coco_zip_path: 'my_dataset.zip',
        base_model_path: 'yolo11n-seg.pt',
        epochs: 100,
        patience: 50,
        batch: 24,
        imgsz: 640
      })
    }
  );
  
  const data = await response.json();
  return data.job_id;
}
```

**Status Polling:**
```javascript
async function pollStatus(jobId) {
  const response = await fetch(
    `https://yolotraining-api.azurewebsites.net/api/status/${jobId}?code=YOUR_KEY`
  );
  const data = await response.json();
  
  if (data.status === 'completed') {
    console.log('Training complete!');
  } else if (data.status === 'failed') {
    console.log('Training failed');
  } else {
    setTimeout(() => pollStatus(jobId), 30000); // Check every 30s
  }
}
```

---

## 🏗️ Architecture Overview

```
┌─────────────────┐
│ Frontend Portal │
│  [Train Button] │
└────────┬────────┘
         │ HTTP POST
         ▼
┌──────────────────────────────────┐
│ Azure Function API               │
│ /api/train                       │
│ /api/status/{id}                 │
│ /api/logs/{id}                   │
│ /api/cleanup/{id}                │
└────────┬─────────────────────────┘
         │ Creates ACI
         ▼
┌──────────────────────────────────┐
│ Azure Container Instance (GPU)   │
│ ┌──────────────────────────────┐ │
│ │ Mounts:                      │ │
│ │ • /mnt/datasets ← Azure Files│ │
│ │ • /mnt/models   ← Azure Files│ │
│ │ • /mnt/outputs  → Azure Files│ │
│ └──────────────────────────────┘ │
│                                  │
│ Runs: app.py                     │
│ • COCO → YOLO conversion         │
│ • Dataset augmentation           │
│ • Model training (GPU)           │
│ • TFLite export                  │
└────────┬─────────────────────────┘
         │ Saves model
         ▼
┌──────────────────────────────────┐
│ Azure Files (outputs)            │
│ tflite/{job_id}/model.tflite    │
└──────────────────────────────────┘
```

---

## 📊 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/train` | Start training job |
| GET | `/api/status/{job_id}` | Check training status |
| GET | `/api/logs/{job_id}` | View container logs |
| DELETE | `/api/cleanup/{job_id}` | Delete container |

---

## 💰 Cost Estimate

### Per Training Job (~3 hours)
- Container Instance (GPU K80): **$3.00**
- Data transfer: **$0.50**
- **Total:** ~**$3.50 per job**

### Monthly Fixed Costs
- Storage (1TB): $20.00
- Function App: $13.00
- Container Registry: $5.00
- **Total:** **$38.00/month**

**Example:** 10 jobs/month = $38 + (10 × $3.50) = **$73/month**

---

## 🧪 Testing

### Quick Test
```bash
./scripts/test-api.sh
```

### Manual Test
```bash
# Start training (5 epochs for quick test)
curl -X POST "https://API_URL/api/train?code=KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "coco_zip_path": "dataset.zip",
    "base_model_path": "yolo11n-seg.pt",
    "epochs": 5,
    "batch": 16
  }'

# Check status (replace JOB_ID)
curl "https://API_URL/api/status/JOB_ID?code=KEY"

# View logs
curl "https://API_URL/api/logs/JOB_ID?code=KEY&tail=100"
```

---

## 📚 Documentation Guide

| File | When to Use |
|------|-------------|
| **START_HERE.md** (this file) | First time setup |
| **SOLUTION_SUMMARY.md** | Architecture overview |
| **DEPLOYMENT_GUIDE.md** | Detailed step-by-step guide |
| **API_README.md** | Quick API reference |

---

## 🔧 Configuration

### Adjust Training Parameters
Edit API call:
```json
{
  "epochs": 150,      // Increase for more training
  "batch": 32,        // Increase for faster training (needs more GPU memory)
  "patience": 75,     // Early stopping patience
  "imgsz": 800        // Higher resolution (needs more GPU memory)
}
```

### Change GPU Type
Edit `azure-function/function_app.py`:
```python
gpu_resource = GpuResource(count=1, sku="V100")  # K80, P100, or V100
```

---

## 🛠️ Troubleshooting

### GPU Quota Error
**Problem:** "GPU quota exceeded in region"
**Solution:** Request quota increase or use different region

### Out of Memory
**Problem:** Container crashes with OOM
**Solution:** Reduce batch size to 16 or 8

### Dataset Not Found
**Problem:** "coco.json not found"
**Solution:** Verify upload: `az storage file list --account-name ACCOUNT --share-name datasets`

### More Help
See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) "Troubleshooting" section

---

## ✅ Checklist

Before sharing with frontend:
- [ ] Ran `./quick-start.sh` successfully
- [ ] API URL works (got 401 = good, it's asking for auth)
- [ ] Function key obtained
- [ ] Test training job completed
- [ ] `api-credentials.txt` created
- [ ] Shared API URL + Function Key with frontend dev
- [ ] Shared `API_README.md` with frontend dev

---

## 🎉 You're Done!

Your training API is **production-ready**!

**Give your frontend developer:**
1. ✅ API URL (from `api-credentials.txt`)
2. ✅ Function Key (from `api-credentials.txt`)
3. ✅ Documentation (`API_README.md`)
4. ✅ Example code (see "What to Give Your Frontend Developer" above)

**Frontend task:** Wire up the "Train" button to call `/api/train` endpoint.

**That's it!** 🚀

---

## 📞 Need Help?

1. **Architecture questions:** Read [SOLUTION_SUMMARY.md](SOLUTION_SUMMARY.md)
2. **Setup issues:** Check [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
3. **API usage:** See [API_README.md](API_README.md)
4. **Azure issues:** Check Azure Portal → Container Instances → Logs

---

## 🔄 Update Deployment

If you modify training code ([app.py](app.py)):

```bash
cd scripts

# Rebuild and push Docker image
source ../azure-config.env
docker build -f ../Dockerfile.train.gpu -t $TRAINING_IMAGE ..
docker push $TRAINING_IMAGE

# No need to redeploy Function App
```

If you modify API ([azure-function/function_app.py](azure-function/function_app.py)):

```bash
cd scripts
./deploy-function.sh
```

---

**Ready to deploy? Run:**
```bash
./quick-start.sh
```
