#!/bin/bash
# Upload files to Azure File Shares

set -e

# Load configuration
if [ -f "azure-config.env" ]; then
  source azure-config.env
else
  echo "Error: azure-config.env not found. Run setup-azure-infrastructure.sh first."
  exit 1
fi

# Function to upload file
upload_file() {
  local file_path=$1
  local share_name=$2
  local dest_path=$3
  
  if [ ! -f "$file_path" ]; then
    echo "Error: File not found: $file_path"
    return 1
  fi
  
  echo "Uploading $file_path to $share_name/$dest_path"
  az storage file upload \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --account-key "$STORAGE_ACCOUNT_KEY" \
    --share-name "$share_name" \
    --source "$file_path" \
    --path "$dest_path"
  
  echo "✓ Upload complete"
}

# Upload dataset (example)
if [ ! -z "$1" ]; then
  DATASET_FILE=$1
  DATASET_NAME=$(basename "$DATASET_FILE")
  echo "Uploading dataset: $DATASET_FILE"
  upload_file "$DATASET_FILE" "$DATASET_SHARE_NAME" "$DATASET_NAME"
else
  echo "Usage: $0 <path-to-dataset.zip> [<path-to-model.pt>]"
  echo ""
  echo "Example:"
  echo "  $0 /path/to/coco_dataset.zip"
  echo "  $0 /path/to/coco_dataset.zip /path/to/yolo11n-seg.pt"
fi

# Upload model (optional)
if [ ! -z "$2" ]; then
  MODEL_FILE=$2
  MODEL_NAME=$(basename "$MODEL_FILE")
  echo "Uploading model: $MODEL_FILE"
  upload_file "$MODEL_FILE" "$MODEL_SHARE_NAME" "$MODEL_NAME"
fi

echo ""
echo "Files in datasets share:"
az storage file list \
  --account-name "$STORAGE_ACCOUNT_NAME" \
  --account-key "$STORAGE_ACCOUNT_KEY" \
  --share-name "$DATASET_SHARE_NAME" \
  --output table

echo ""
echo "Files in models share:"
az storage file list \
  --account-name "$STORAGE_ACCOUNT_NAME" \
  --account-key "$STORAGE_ACCOUNT_KEY" \
  --share-name "$MODEL_SHARE_NAME" \
  --output table
