# YOLO Training API - Azure Container Instances

> **Complete automated training pipeline**: Click a button → Train YOLO model on Azure GPU → Get TFLite model

## 🎯 What This Does

Your portal's **"Train" button** triggers:
1. **Azure Function API** receives HTTP POST request
2. **Azure Container Instance** (with GPU) is created automatically
3. **Azure Files** mounted (dataset, base model, output storage)
4. **Training script** ([app.py](app.py)) runs:
   - COCO → YOLO conversion
   - Dataset augmentation
   - YOLO11 model training
   - TFLite export
5. **TFLite model** saved to Azure Files
6. **Container destroyed** (cost optimization)

## 📋 Quick Start

### Prerequisites
- Azure subscription
- Azure CLI installed
- Docker installed
- COCO dataset ZIP file
- Base YOLO model (yolo11n-seg.pt)

### 1️⃣ Setup Infrastructure (5-10 min)

```bash
cd scripts
chmod +x setup-azure-infrastructure.sh
./setup-azure-infrastructure.sh
```

This creates:
- ✅ Resource Group
- ✅ Storage Account with File Shares (datasets, models, outputs)
- ✅ Azure Container Registry (ACR)
- ✅ Docker image built & pushed
- ✅ Azure Function App (API endpoint)
- ✅ Managed Identity with permissions

### 2️⃣ Upload Dataset & Model

```bash
chmod +x upload-files.sh
./upload-files.sh /path/to/coco_dataset.zip /path/to/yolo11n-seg.pt
```

### 3️⃣ Deploy Function App

```bash
chmod +x deploy-function.sh
./deploy-function.sh
```

### 4️⃣ Get API Key

```bash
source ../azure-config.env
az functionapp keys list \
  --resource-group $AZURE_RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --query "functionKeys.default" -o tsv
```

### 5️⃣ Test API

```bash
chmod +x test-api.sh
./test-api.sh
```

## 🌐 API Endpoints

### Base URL
```
https://yolotraining-api.azurewebsites.net
```

### Authentication
All endpoints require `?code={FUNCTION_KEY}` query parameter.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/train` | Start training job |
| GET | `/api/status/{job_id}` | Check training status |
| GET | `/api/logs/{job_id}` | Get container logs |
| DELETE | `/api/cleanup/{job_id}` | Delete container |

### Example: Start Training

```bash
curl -X POST "https://yolotraining-api.azurewebsites.net/api/train?code=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "coco_zip_path": "products_v1.zip",
    "base_model_path": "yolo11n-seg.pt",
    "epochs": 100,
    "patience": 50,
    "batch": 24,
    "imgsz": 640
  }'
```

**Response:**
```json
{
  "job_id": "abc12345",
  "status": "provisioning",
  "status_url": "https://yolotraining-api.azurewebsites.net/api/status/abc12345",
  "message": "Training job started successfully"
}
```

## 🎨 Frontend Integration

### JavaScript Example

```javascript
async function startTraining() {
  const apiUrl = "https://yolotraining-api.azurewebsites.net";
  const apiKey = "YOUR_FUNCTION_KEY";
  
  // Start training
  const response = await fetch(`${apiUrl}/api/train?code=${apiKey}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      coco_zip_path: "my_dataset.zip",
      base_model_path: "yolo11n-seg.pt",
      epochs: 100,
      patience: 50,
      batch: 24,
      imgsz: 640
    })
  });
  
  const data = await response.json();
  const jobId = data.job_id;
  
  // Poll for status
  const checkStatus = async () => {
    const statusRes = await fetch(`${apiUrl}/api/status/${jobId}?code=${apiKey}`);
    const statusData = await statusRes.json();
    
    if (statusData.status === "completed") {
      alert("Training completed! Model ready for download.");
    } else if (statusData.status === "failed") {
      alert("Training failed: " + statusData.message);
    } else {
      setTimeout(checkStatus, 30000); // Check every 30 seconds
    }
  };
  
  checkStatus();
}
```

### React Example

```jsx
import { useState } from 'react';

function TrainingButton() {
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState('idle');
  
  const apiUrl = process.env.REACT_APP_TRAINING_API_URL;
  const apiKey = process.env.REACT_APP_TRAINING_API_KEY;
  
  const startTraining = async () => {
    setStatus('starting');
    
    const response = await fetch(`${apiUrl}/api/train?code=${apiKey}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        coco_zip_path: 'my_dataset.zip',
        base_model_path: 'yolo11n-seg.pt',
        epochs: 100
      })
    });
    
    const data = await response.json();
    setJobId(data.job_id);
    setStatus('running');
    pollStatus(data.job_id);
  };
  
  const pollStatus = async (id) => {
    const interval = setInterval(async () => {
      const response = await fetch(`${apiUrl}/api/status/${id}?code=${apiKey}`);
      const data = await response.json();
      
      setStatus(data.status);
      
      if (data.status === 'completed' || data.status === 'failed') {
        clearInterval(interval);
      }
    }, 30000);
  };
  
  return (
    <div>
      <button onClick={startTraining} disabled={status === 'running'}>
        {status === 'idle' && 'Start Training'}
        {status === 'starting' && 'Starting...'}
        {status === 'running' && 'Training in progress...'}
        {status === 'completed' && '✓ Training Complete'}
        {status === 'failed' && '✗ Training Failed'}
      </button>
      {jobId && <p>Job ID: {jobId}</p>}
    </div>
  );
}
```

## 📂 Project Structure

```
.
├── app.py                          # Main training script
├── Dockerfile.train.gpu            # GPU-enabled Docker image
├── requirements.txt                # Python dependencies
├── yolo11n.pt                      # Base YOLO model
│
├── azure-function/                 # Azure Function API
│   ├── function_app.py            # API endpoints (train, status, logs)
│   ├── requirements.txt           # Function dependencies
│   ├── host.json                  # Function configuration
│   └── .env.template              # Environment variables template
│
├── scripts/                        # Setup & deployment scripts
│   ├── setup-azure-infrastructure.sh  # Create all Azure resources
│   ├── deploy-function.sh            # Deploy Function App
│   ├── upload-files.sh               # Upload data to Azure Files
│   ├── test-api.sh                   # Test API endpoints
│   └── api_client.py                 # Python client library
│
├── DEPLOYMENT_GUIDE.md             # Detailed setup guide
└── README.md                       # This file
```

## 🔧 Configuration

All configuration is in Azure Function App settings. Update via:

```bash
az functionapp config appsettings set \
  --resource-group yolotraining-rg \
  --name yolotraining-api \
  --settings DEFAULT_EPOCHS=150 DEFAULT_BATCH=32
```

### Available Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `DEFAULT_EPOCHS` | 100 | Training epochs |
| `DEFAULT_PATIENCE` | 50 | Early stopping patience |
| `DEFAULT_BATCH` | 24 | Batch size |
| `DEFAULT_IMGSZ` | 640 | Image size |
| `AZURE_LOCATION` | eastus | Azure region |

## 🐳 Docker Image

Training runs in a GPU-enabled Docker container:
- Base: `nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04`
- Python 3.x with PyTorch (CUDA 12.1)
- Ultralytics YOLO, TensorFlow, OpenCV
- Albumentations for augmentation

Built and stored in Azure Container Registry automatically.

## 📊 Monitoring

### Check Training Status
```bash
curl "https://yolotraining-api.azurewebsites.net/api/status/JOB_ID?code=KEY"
```

### Get Logs
```bash
curl "https://yolotraining-api.azurewebsites.net/api/logs/JOB_ID?code=KEY&tail=100"
```

### Download Model
```bash
az storage file download \
  --account-name yolotrainingstorage \
  --share-name outputs \
  --path "tflite/JOB_ID/model.tflite" \
  --dest "./trained_model.tflite"
```

## 💰 Cost Estimation

**Per Training Job (100 epochs, ~3 hours):**
- Azure Container Instance (K80 GPU): ~$3.00
- Data transfer: ~$0.50
- **Total per training:** ~$3.50

**Monthly Fixed Costs:**
- Storage Account (1TB): ~$20.00
- Function App (B1): ~$13.00
- Container Registry: ~$5.00
- **Total fixed:** ~$38.00/month

## 🛠️ Troubleshooting

### GPU Quota Issues
Request GPU quota increase in Azure Portal or use different region.

### Out of Memory
Reduce batch size: `"batch": 16` or `"batch": 8`

### Dataset Not Found
Verify file uploaded:
```bash
az storage file list --account-name ACCOUNT --share-name datasets
```

### Function Timeout
Normal - function returns immediately. Check status via `/api/status/{job_id}`.

## 🔐 Security

- ✅ Managed Identity (no passwords)
- ✅ Function-level authentication
- ✅ Storage account keys in environment
- 🔧 Optional: VNet integration, Private Endpoints, Key Vault

## 📚 Documentation

- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete setup guide
- **[Azure Container Instances Docs](https://docs.microsoft.com/en-us/azure/container-instances/)**
- **[Azure Functions Python Guide](https://docs.microsoft.com/en-us/azure/azure-functions/functions-reference-python)**
- **[Ultralytics YOLO Docs](https://docs.ultralytics.com/)**

## 🎯 What to Give Your Frontend Developer

**API Endpoint:**
```
https://yolotraining-api.azurewebsites.net/api/train
```

**Function Key:**
```bash
az functionapp keys list --resource-group yolotraining-rg --name yolotraining-api
```

**API Documentation:**
- POST `/api/train` - Start training
- GET `/api/status/{job_id}` - Check status
- GET `/api/logs/{job_id}` - View logs
- DELETE `/api/cleanup/{job_id}` - Cleanup

**Example Code:** See "Frontend Integration" section above

## 🚀 Quick Command Reference

```bash
# Setup (one-time)
./scripts/setup-azure-infrastructure.sh
./scripts/upload-files.sh dataset.zip model.pt
./scripts/deploy-function.sh

# Test
./scripts/test-api.sh

# Start training
curl -X POST "https://API_URL/api/train?code=KEY" \
  -H "Content-Type: application/json" \
  -d '{"coco_zip_path":"dataset.zip","base_model_path":"model.pt"}'

# Check status
curl "https://API_URL/api/status/JOB_ID?code=KEY"

# Get logs
curl "https://API_URL/api/logs/JOB_ID?code=KEY"

# Download model
az storage file download --account-name STORAGE --share-name outputs \
  --path "tflite/JOB_ID/model.tflite" --dest "./model.tflite"
```

## ✅ Done!

Your training API is ready! Connect your frontend button to the API endpoint and you're all set. 🎉

---

**Need help?** Check [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed troubleshooting.
