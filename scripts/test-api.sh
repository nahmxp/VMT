# Test the Training API
# This script demonstrates how to use the training API endpoints

# ============================================
# Configuration
# ============================================

# Load configuration from azure-config.env
if [ -f "azure-config.env" ]; then
  source azure-config.env
else
  echo "Error: azure-config.env not found. Run setup-azure-infrastructure.sh first."
  exit 1
fi

# Get function key
echo "Getting function key..."
FUNCTION_KEY=$(az functionapp keys list \
  --resource-group $AZURE_RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --query "functionKeys.default" -o tsv)

if [ -z "$FUNCTION_KEY" ]; then
  echo "Error: Could not retrieve function key"
  exit 1
fi

echo "Function URL: $FUNCTION_APP_URL"
echo "Function Key: ${FUNCTION_KEY:0:10}..."

# ============================================
# Test 1: Start Training
# ============================================

echo ""
echo "=========================================="
echo "Test 1: Start Training Job"
echo "=========================================="

RESPONSE=$(curl -s -X POST "$FUNCTION_APP_URL/api/train?code=$FUNCTION_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "coco_zip_path": "coco_dataset.zip",
    "base_model_path": "yolo11n-seg.pt",
    "epochs": 5,
    "patience": 3,
    "batch": 16,
    "imgsz": 640
  }')

echo "Response:"
echo "$RESPONSE" | jq .

# Extract job ID
JOB_ID=$(echo "$RESPONSE" | jq -r .job_id)

if [ "$JOB_ID" == "null" ] || [ -z "$JOB_ID" ]; then
  echo "Error: Failed to start training job"
  exit 1
fi

echo ""
echo "Training job started: $JOB_ID"

# ============================================
# Test 2: Check Status
# ============================================

echo ""
echo "=========================================="
echo "Test 2: Check Training Status"
echo "=========================================="

sleep 5  # Wait a bit for container to provision

STATUS_RESPONSE=$(curl -s "$FUNCTION_APP_URL/api/status/$JOB_ID?code=$FUNCTION_KEY")

echo "Status Response:"
echo "$STATUS_RESPONSE" | jq .

# ============================================
# Test 3: Monitor Progress
# ============================================

echo ""
echo "=========================================="
echo "Test 3: Monitor Training Progress"
echo "=========================================="

echo "Polling status every 30 seconds..."
echo "Press Ctrl+C to stop monitoring"
echo ""

while true; do
  STATUS=$(curl -s "$FUNCTION_APP_URL/api/status/$JOB_ID?code=$FUNCTION_KEY" | jq -r .status)
  TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
  
  echo "[$TIMESTAMP] Status: $STATUS"
  
  if [ "$STATUS" == "completed" ]; then
    echo ""
    echo "✓ Training completed successfully!"
    
    # Get final status
    FINAL_STATUS=$(curl -s "$FUNCTION_APP_URL/api/status/$JOB_ID?code=$FUNCTION_KEY")
    echo "Final Status:"
    echo "$FINAL_STATUS" | jq .
    
    break
  elif [ "$STATUS" == "failed" ]; then
    echo ""
    echo "✗ Training failed"
    
    # Get logs
    echo ""
    echo "Getting error logs..."
    curl -s "$FUNCTION_APP_URL/api/logs/$JOB_ID?code=$FUNCTION_KEY&tail=50" | jq -r .logs
    
    break
  fi
  
  sleep 30
done

# ============================================
# Test 4: Get Logs
# ============================================

echo ""
echo "=========================================="
echo "Test 4: Get Training Logs"
echo "=========================================="

LOGS=$(curl -s "$FUNCTION_APP_URL/api/logs/$JOB_ID?code=$FUNCTION_KEY&tail=100")

echo "Last 100 lines of logs:"
echo "$LOGS" | jq -r .logs

# ============================================
# Test 5: Cleanup (Optional)
# ============================================

echo ""
echo "=========================================="
echo "Test 5: Cleanup Container"
echo "=========================================="

read -p "Do you want to delete the container? (y/n) " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
  CLEANUP_RESPONSE=$(curl -s -X DELETE "$FUNCTION_APP_URL/api/cleanup/$JOB_ID?code=$FUNCTION_KEY")
  
  echo "Cleanup Response:"
  echo "$CLEANUP_RESPONSE" | jq .
  
  echo ""
  echo "Container deleted"
else
  echo "Container not deleted. You can delete it manually later with:"
  echo "curl -X DELETE '$FUNCTION_APP_URL/api/cleanup/$JOB_ID?code=$FUNCTION_KEY'"
fi

# ============================================
# Test 6: Download Model
# ============================================

echo ""
echo "=========================================="
echo "Test 6: Download Trained Model"
echo "=========================================="

if [ "$STATUS" == "completed" ]; then
  echo "Listing output files..."
  
  az storage file list \
    --account-name $STORAGE_ACCOUNT_NAME \
    --account-key $STORAGE_ACCOUNT_KEY \
    --share-name outputs \
    --path "tflite/$JOB_ID" \
    --output table
  
  echo ""
  echo "To download the model:"
  echo "az storage file download \\"
  echo "  --account-name $STORAGE_ACCOUNT_NAME \\"
  echo "  --share-name outputs \\"
  echo "  --path 'tflite/$JOB_ID/<model-file-name>.tflite' \\"
  echo "  --dest './trained_model.tflite'"
else
  echo "Training not completed yet, skipping download"
fi

echo ""
echo "=========================================="
echo "All tests completed!"
echo "=========================================="
