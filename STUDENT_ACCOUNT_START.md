# 🎓 START HERE - Student Account Guide

> **You have:** Azure Student Account ($100 credit, no GPU)  
> **You want:** Test the training API deployment with CPU

---

## 📚 Which Document to Read?

### **For Step-by-Step Setup** (Recommended for first time):
👉 **[SETUP_CHECKLIST.md](SETUP_CHECKLIST.md)** - Checkbox format, clear order

### **For Command Reference** (Copy-paste all commands):
👉 **[COMMANDS_CHEATSHEET.md](COMMANDS_CHEATSHEET.md)** - All commands in sequence

### **For Detailed Explanations** (If you want to understand what's happening):
👉 **[STUDENT_ACCOUNT_SETUP.md](STUDENT_ACCOUNT_SETUP.md)** - Complete guide with explanations

---

## 🎯 Quick Summary

### What You'll Do:

1. **Local Setup (15 min)**
   - Install Azure CLI, Docker, Function Tools
   - Build Docker image (CPU version)
   - Push to Azure Container Registry

2. **Azure Setup (30 min)**
   - Create Storage Account + File Shares
   - Create Container Registry
   - Create Function App
   - Configure permissions

3. **Deploy & Test (15 min)**
   - Upload dataset & model
   - Deploy Function App code
   - Test API endpoint
   - Start training job

4. **Monitor (30-60 min)**
   - Watch training progress
   - View logs
   - Download trained model

**Total Time:** ~2 hours (including training)

---

## 📋 What You Need

### On Your Computer:
- [ ] Ubuntu/Linux (or WSL on Windows)
- [ ] Internet connection
- [ ] ~10GB free disk space
- [ ] COCO dataset ZIP file (your data)
- [ ] YOLO base model (we'll help you download)

### On Azure:
- [ ] Student account logged in
- [ ] $100 credit available

---

## 🚀 Quick Start (3 Steps)

### Step 1: Choose Your Path

**Option A - Full Guided Setup (Recommended)**
```bash
cd /media/Dev/NDEV/VMT
```

Open and follow: **[SETUP_CHECKLIST.md](SETUP_CHECKLIST.md)**  
✅ Check off each item as you complete it

**Option B - Copy-Paste Commands**
```bash
cd /media/Dev/NDEV/VMT
```

Open: **[COMMANDS_CHEATSHEET.md](COMMANDS_CHEATSHEET.md)**  
Copy-paste commands in order (edit variables first!)

### Step 2: Install Prerequisites

```bash
# Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Docker
sudo apt-get update && sudo apt-get install docker.io
sudo systemctl start docker
sudo usermod -aG docker $USER

# Azure Functions Core Tools
wget -q https://packages.microsoft.com/config/ubuntu/20.04/packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
sudo apt-get update
sudo apt-get install azure-functions-core-tools-4

# jq (JSON formatter)
sudo apt-get install jq

# Logout and login again for Docker permissions
```

### Step 3: Start Setup

```bash
# Login to Azure
az login

# Follow the checklist or command sheet!
```

---

## 📊 What Gets Created in Azure

| Resource | Purpose | Cost/Month |
|----------|---------|------------|
| Resource Group | Container for all resources | Free |
| Storage Account | Store datasets, models, outputs | ~$0.40 |
| 3 File Shares | datasets, models, outputs | Included |
| Container Registry | Store Docker images | ~$5.00 |
| Function App | API endpoints | ~$13.00 |
| App Service Plan | Host Function App | Included |
| Container Instance | Run training (per job) | ~$0.50/job |

**Monthly Fixed:** ~$18  
**Per Training Job:** ~$0.50  
**Total for 10 test jobs:** ~$23 (well within $100!)

---

## 🎯 Key Differences from Production Setup

### Student Account (What We're Doing):
- ✅ **CPU only** (no GPU access)
- ✅ **Smaller resources** (2 cores, 8GB RAM)
- ✅ **Slower training** (30-60 min for 5 epochs)
- ✅ **Lower cost** (~$0.50 per job)
- ✅ **Perfect for testing** deployment pipeline

### Production (What You'd Do Later):
- 🚀 GPU-enabled containers (K80, V100)
- 🚀 Larger resources (4 cores, 16GB RAM)
- 🚀 Faster training (2-3 hours for 100 epochs)
- 🚀 Higher cost (~$3.50 per job)
- 🚀 Better model quality

**But the API and workflow are IDENTICAL!** ✨

---

## 🗂️ File Structure

```
VMT/
├── 🎓 STUDENT_ACCOUNT_START.md        ← YOU ARE HERE
├── ✅ SETUP_CHECKLIST.md              ← Step-by-step with checkboxes
├── 📋 COMMANDS_CHEATSHEET.md          ← All commands in order
├── 📖 STUDENT_ACCOUNT_SETUP.md        ← Detailed explanations
│
├── 🐳 Dockerfile.train.cpu            ← CPU version (what we use)
├── 🐳 Dockerfile.train.gpu            ← GPU version (for later)
│
├── azure-function/
│   ├── function_app_cpu.py           ← API code (CPU version)
│   └── function_app.py               ← API code (GPU version)
│
└── 📚 Other Docs (for reference)
    ├── SOLUTION_SUMMARY.md
    ├── DEPLOYMENT_GUIDE.md
    └── API_README.md
```

---

## ⚠️ Important Notes

### 1. Use CPU Version Files
- **Docker:** Use `Dockerfile.train.cpu` ✅
- **Function:** Copy `function_app_cpu.py` to `function_app.py` ✅
- Don't use GPU versions - they won't work on student accounts!

### 2. Smaller Training Parameters
We use reduced values for testing:
- **Epochs:** 5 (not 100)
- **Batch:** 8 (not 24)
- **Image size:** 320 (not 640)
- **Device:** CPU (not GPU)

### 3. Training Will Be Slower
- CPU training: 30-60 minutes
- GPU training: 2-3 hours
- **This is normal!** We're just testing the pipeline.

### 4. Cost Monitoring
- Check Azure Portal regularly
- Set up cost alerts at $50
- Delete resources when done testing

---

## 🎯 Success Criteria

**You've successfully deployed when you can:**

1. ✅ Call API endpoint from command line
2. ✅ See container created in Azure Portal
3. ✅ View live logs during training
4. ✅ Training completes without errors
5. ✅ TFLite model saved to Azure Files
6. ✅ Download trained model

**Then give frontend developer:**
- API URL
- Function Key
- Example request code

---

## 🆘 If You Get Stuck

### Check These First:
1. **All prerequisites installed?**
   ```bash
   az --version && docker --version && func --version
   ```

2. **Logged into Azure?**
   ```bash
   az account show
   ```

3. **All variables set?**
   ```bash
   echo $PROJECT_NAME $LOCATION $STORAGE_ACCOUNT
   ```

### Common Issues:

**"ACR name already taken"**
```bash
export ACR_NAME="${PROJECT_NAME}acr$(date +%s)"
```

**"Docker permission denied"**
```bash
sudo usermod -aG docker $USER
# Then logout and login again
```

**"Function deployment failed"**
```bash
cd azure-function
cp function_app_cpu.py function_app.py  # Make sure using CPU version!
func azure functionapp publish "$FUNCTION_APP" --python
```

**"Container provisioning failed"**
- Check region availability
- Try different location: `export LOCATION="westus"`
- Check student account quotas

---

## 📞 Where to Get Help

1. **Check logs:**
   ```bash
   az functionapp log tail --name "$FUNCTION_APP" --resource-group "${PROJECT_NAME}-rg"
   ```

2. **View in Azure Portal:**
   - https://portal.azure.com
   - Find your resource group
   - Check container logs

3. **Review documentation:**
   - [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md) - Step-by-step
   - [STUDENT_ACCOUNT_SETUP.md](STUDENT_ACCOUNT_SETUP.md) - Detailed guide

---

## 🎉 Ready to Start?

### Choose Your Path:

**Want Checkboxes?**  
👉 Open [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md) and start checking off items!

**Want Copy-Paste Commands?**  
👉 Open [COMMANDS_CHEATSHEET.md](COMMANDS_CHEATSHEET.md) and run commands in order!

**Want Detailed Explanations?**  
👉 Open [STUDENT_ACCOUNT_SETUP.md](STUDENT_ACCOUNT_SETUP.md) and follow along!

---

### First Command (All Paths Start Here):

```bash
# Install prerequisites if not already done
az --version || curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login

# Set your project name
export PROJECT_NAME="yolotest"
export LOCATION="eastus"

# Then follow your chosen guide!
```

---

**🚀 Good luck! You've got this!**

The pipeline is already built - you just need to deploy it.  
Follow the checklist, and you'll have a working training API in ~2 hours!
