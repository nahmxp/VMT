
# **Guideline: Deploy Serverless Model Training on Azure**

This guide will walk you through setting up an **Azure Function** that triggers an ephemeral training job in a container or VM, mounts **Azure File Storage**, trains your model, and shuts down automatically. This pattern ensures **no idle compute costs**.

---

## **1. Prerequisites**

Before starting, make sure you have:

* An **Azure subscription**.
* **Azure CLI** installed and logged in.
* **Node.js / npm** installed (for Azure Functions Core Tools).
* **Python 3.10+** installed.
* Git and repo cloned for your project.
* Optionally, Docker installed if you plan to test containers locally.

---

## **2. Create a Resource Group**

Pick a resource group and location:

```bash
az group create \
  --name vmt-rg \
  --location southeastasia
```

This creates `vmt-rg` where all resources (storage, function, ACI/VM) will live.

---

## **3. Create Azure Storage Account**

1. Pick a **unique storage account name**:

```bash
STORAGE_NAME=vmtstorage$RANDOM
LOCATION=southeastasia
```

2. Create the storage account:

```bash
az storage account create \
  --name $STORAGE_NAME \
  --resource-group vmt-rg \
  --location $LOCATION \
  --sku Standard_LRS
```

3. Azure Files will be mounted inside your training container using this storage.

---

## **4. Create Azure Function App**

1. Pick a function name:

```bash
FUNC_NAME=vmt-train-$RANDOM
```

2. Register the Microsoft.Web namespace if not already done:

```bash
az provider register --namespace Microsoft.Web
```

3. Create a **Linux-based Function App** (required for Python):

```bash
az functionapp create \
  --resource-group vmt-rg \
  --consumption-plan-location southeastasia \
  --os-type linux \
  --runtime python \
  --runtime-version 3.10 \
  --functions-version 4 \
  --name $FUNC_NAME \
  --storage-account $STORAGE_NAME
```

* This sets up a serverless Python function ready to trigger training jobs.
* Azure automatically creates **Application Insights** for monitoring.

---

## **5. Prepare Azure Function Code**

1. Navigate to your function folder:

```bash
cd azure-function
```

2. Ensure your folder contains:

```
function_app.py  # main function logic
host.json       # function config
requirements.txt  # Python dependencies
```

3. Add a `local.settings.json` if needed for local testing (this is optional).

---

## **6. Install Azure Functions Core Tools**

If `func` CLI is not installed:

```bash
sudo npm install -g azure-functions-core-tools@4 --unsafe-perm true
func --version
```

* Must be **version 4.x** for Python 3.10+ and Azure Functions v4.

---

## **7. Deploy Function App**

From the function folder:

```bash
func azure functionapp publish $FUNC_NAME --python
```

* This triggers a **remote build** using Oryx.
* Dependencies in `requirements.txt` are installed inside the container.
* After deployment, the function URL will appear:

```
https://<FUNC_NAME>.azurewebsites.net/api/train
```

---

## **8. Trigger Training from Front-end**

Your function is HTTP-triggered. Example with JavaScript:

```javascript
async function triggerTraining() {
  const response = await fetch('https://<FUNC_NAME>.azurewebsites.net/api/train', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'yolo11n',
      epochs: 50,
      batch_size: 16
    })
  });

  const result = await response.json();
  console.log(result);
}
```

* Replace `<FUNC_NAME>` with your deployed function name.
* Function will start the container/VM, mount Azure File Storage, run training, and shut down automatically.

---

## **9. Notes / Caveats**

1. **Python version**: Ensure your local environment matches the Function App version (3.10). Otherwise, `ModuleNotFoundError` may occur.
2. **Resource limits**: Linux Consumption Plan has ~1.5 GB memory limit per container. Heavy GPU training may require **Azure VM or dedicated ACI**.
3. **Azure Files mount**: Make sure the container uses the storage connection string correctly. Your repo usually handles this.
4. **Security**: Protect the function URL with API keys or Azure AD authentication if exposed publicly.

---

## **10. Monitoring**

* View logs and function metrics in **Application Insights**:

```
https://portal.azure.com/#resource/subscriptions/<SUBSCRIPTION_ID>/resourceGroups/vmt-rg/providers/microsoft.insights/components/$FUNC_NAME/overview
```

* You can also check container/VM status in **Azure Portal → Container Instances** if using ACI.

---

✅ Following this guide, anyone can replicate your **serverless training setup**: press a front-end button → ephemeral container/VM spins up → mounts Azure Files → trains → shuts down automatically.

---

