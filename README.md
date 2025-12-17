# Product Detection Model Training Pipeline

## 📋 Overview

This project is an **automated end-to-end machine learning pipeline** for training YOLO11 segmentation models on product detection datasets. It automates the entire workflow from dataset preparation to model deployment, making it ideal for scalable production environments.

### What This Project Does

1. **COCO to YOLO Conversion**: Converts COCO-format datasets (with instance segmentation annotations) to YOLO format
2. **Data Augmentation**: Applies sophisticated augmentation techniques using Albumentations to improve model robustness
3. **Model Training**: Trains YOLO11 segmentation models with GPU acceleration and early stopping
4. **TFLite Export**: Exports trained models to TensorFlow Lite format for mobile/edge deployment

### Use Cases

- **Retail Product Recognition**: Detect and segment products on shelves, in shopping carts, or warehouses
- **Inventory Management**: Automated stock counting and product identification
- **Quality Control**: Identify product defects or verify packaging
- **Mobile/Edge Deployment**: Run inference on smartphones, tablets, or edge devices using TFLite

---

## 🏗️ Architecture

```
Input: COCO Dataset (ZIP) + Base YOLO Model
    ↓
1. COCO → YOLO Conversion (train/val/test split)
    ↓
2. Data Augmentation (geometric + color transforms)
    ↓
3. YOLO11 Training (GPU-accelerated, early stopping)
    ↓
4. TFLite Export (optimized for mobile/edge)
    ↓
Output: Trained TFLite Model
```

---

## 🚀 Quick Start

### Prerequisites

- **Hardware**: NVIDIA GPU with CUDA support (recommended: 8GB+ VRAM)
- **Software**: 
  - Ubuntu 22.04 (or similar Linux)
  - NVIDIA Driver + CUDA 12.1+
  - Docker with NVIDIA Container Toolkit (for containerized training)
  - Python 3.10+ (for local training)

---

## 🐳 Docker Setup (Recommended)

### 1. Build the Docker Image

```bash
docker build -f Dockerfile.train.gpu -t product-detection-trainer:latest .
```

**What this does:**
- Creates a containerized environment with CUDA 12.1, cuDNN 8, and PyTorch
- Installs all required dependencies (Ultralytics, TensorFlow, OpenCV, etc.)
- Sets up the working directory and entrypoint

### 2. Prepare Your Data

Organize your data structure:
```
/path/to/data/
├── coco_dataset/
│   └── coco_dataset.zip  # Your COCO-format dataset
├── models/
│   └── yolo11n-seg.pt    # Base YOLO model
└── output/
    └── tflite_out/        # Where TFLite models will be saved
```

### 3. Run Training in Docker

#### Basic Run (with GPU):

```bash
docker run --gpus all \
  -v /path/to/data:/data \
  -v /path/to/workdir:/app/workdir \
  product-detection-trainer:latest \
  --coco-zip /data/coco_dataset/coco_dataset.zip \
  --base-model /data/models/yolo11n-seg.pt \
  --work-dir /app/workdir \
  --tflite-out-dir /data/output/tflite_out \
  --epochs 100 \
  --patience 50 \
  --batch 24 \
  --imgsz 640 \
  --device 0
```

#### Example with Actual Paths:

```bash
docker run --gpus all \
  -v /media/xpert-ai/Documents/NDEV:/data \
  -v /media/xpert-ai/Dev/NDEV/VMT/workdir_test:/app/workdir \
  product-detection-trainer:latest \
  --coco-zip "/data/Product detection/dataset/coco_dataset/coco_dataset.zip" \
  --base-model "/data/Image_object_dct/Model/yolo11n-seg.pt" \
  --work-dir /app/workdir \
  --tflite-out-dir "/data/Product detection/dataset/coco_dataset/tflite_out" \
  --epochs 100 \
  --patience 50 \
  --batch 24 \
  --imgsz 640 \
  --device 0
```

#### Quick Test (3 epochs for testing):

```bash
docker run --gpus all \
  -v /media/xpert-ai/Documents/NDEV:/data \
  -v /media/xpert-ai/Dev/NDEV/VMT/workdir_test:/app/workdir \
  product-detection-trainer:latest \
  --coco-zip "/data/Product detection/dataset/coco_dataset/coco_dataset.zip" \
  --base-model "/data/Image_object_dct/Model/yolo11n-seg.pt" \
  --work-dir /app/workdir \
  --tflite-out-dir "/data/Product detection/dataset/coco_dataset/tflite_out" \
  --epochs 3 \
  --patience 2 \
  --batch 4 \
  --imgsz 640 \
  --device 0
```

### 4. Docker Command Parameters Explained

| Parameter | Description | Example |
|-----------|-------------|---------|
| `--gpus all` | Enable GPU access in container | Required for GPU training |
| `-v <host>:<container>` | Mount volumes (host path : container path) | Share data between host and container |
| `--coco-zip` | Path to COCO dataset ZIP file | `/data/coco_dataset.zip` |
| `--base-model` | Path to base YOLO model (.pt file) | `/data/yolo11n-seg.pt` |
| `--work-dir` | Working directory for intermediate files | `/app/workdir` |
| `--tflite-out-dir` | Output directory for TFLite models | `/data/tflite_out` |
| `--epochs` | Number of training epochs | `100` (default) |
| `--patience` | Early stopping patience | `50` (default) |
| `--batch` | Batch size | `24` (adjust for GPU memory) |
| `--imgsz` | Image size for training | `640` |
| `--device` | GPU device ID or 'cpu' | `0` for first GPU |

---

## 💻 Local Python Setup (Alternative)

### 1. Create Virtual Environment

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# OR
.venv\Scripts\activate     # Windows

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### 2. Install Dependencies

```bash
# Install PyTorch with CUDA support (adjust CUDA version as needed)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install other requirements
pip install -r requirements.txt
```

### 3. Run Training Locally

```bash
python app.py \
  --coco-zip "/path/to/coco_dataset.zip" \
  --base-model "/path/to/yolo11n-seg.pt" \
  --work-dir "./workdir_test" \
  --tflite-out-dir "/path/to/tflite_out" \
  --epochs 100 \
  --patience 50 \
  --batch 24 \
  --imgsz 640 \
  --device 0
```

---

## 📊 What Happens During Training

### Step 1: COCO to YOLO Conversion
- Reads COCO JSON annotations
- Converts bounding boxes/segmentation masks to YOLO format
- Splits data: 70% train, 20% validation, 10% test
- Creates `dataset.yaml` for YOLO training

### Step 2: Data Augmentation
- Applies transformations: rotation, flipping, brightness/contrast adjustment, blur, noise
- Multiplies dataset size (default: 3x augmentation)
- Saves augmented images and labels

### Step 3: Model Training
- Loads base YOLO11 segmentation model
- Fine-tunes on augmented dataset
- Uses early stopping to prevent overfitting
- Saves checkpoints: `best.pt` (best validation) and `last.pt` (final epoch)

### Step 4: TFLite Export
- Converts best PyTorch model to TensorFlow Lite
- Applies quantization for smaller model size
- Saves with timestamp: `model_segmented_YYYYMMDD_HHMMSS.tflite`

---

## 📁 Output Structure

After training, your working directory will contain:

```
workdir_test/
├── dataset/
│   └── yolo/                    # YOLO-format dataset
│       ├── train/images/
│       ├── train/labels/
│       ├── valid/images/
│       ├── valid/labels/
│       ├── test/images/
│       ├── test/labels/
│       ├── dataset.yaml
│       └── classes.txt
├── dataset/
│   └── yolo_aug/                # Augmented dataset
│       ├── train/images/
│       ├── train/labels/
│       ├── valid/images/
│       ├── valid/labels/
│       ├── test/images/
│       ├── test/labels/
│       └── data.yaml
└── runs/
    └── segment/
        └── train_YYYYMMDD_HHMMSS/
            ├── weights/
            │   ├── best.pt      # Best model checkpoint
            │   └── last.pt      # Last epoch checkpoint
            ├── args.yaml
            ├── results.png      # Training metrics
            └── confusion_matrix.png
```

---

## 🎯 Next Steps

### 1. **Evaluate Model Performance**
```bash
# Use YOLO's validation mode
yolo segment val model=workdir_test/runs/segment/train_*/weights/best.pt data=workdir_test/dataset/yolo_aug/data.yaml
```

### 2. **Test Inference**
```python
from ultralytics import YOLO

# Load trained model
model = YOLO('workdir_test/runs/segment/train_*/weights/best.pt')

# Run inference
results = model.predict('path/to/test/image.jpg', save=True)
```

### 3. **Deploy TFLite Model**
- Copy `.tflite` file from `tflite_out/` to your mobile app
- Use TensorFlow Lite interpreter for inference
- Example platforms: Android, iOS, Raspberry Pi, Edge TPU

### 4. **Improve Model**
- **More Data**: Add more training images to COCO dataset
- **More Epochs**: Increase `--epochs` for longer training
- **Larger Model**: Use `yolo11m-seg.pt` or `yolo11l-seg.pt` instead of `yolo11n-seg.pt`
- **Hyperparameter Tuning**: Adjust learning rate, augmentation strength, batch size

### 5. **Monitor Training**
- Check TensorBoard logs: `tensorboard --logdir workdir_test/runs`
- Review `results.png` for loss/accuracy curves
- Analyze confusion matrix for class-specific performance

### 6. **Production Deployment**
- Set up automated retraining pipeline (e.g., with new data weekly)
- Use Azure ML, AWS SageMaker, or Kubernetes for orchestration
- Implement A/B testing for model versions
- Monitor inference latency and accuracy in production

---

## 🔧 Troubleshooting

### Out of Memory (OOM) Errors
- Reduce `--batch` size (try 16, 8, or 4)
- Reduce `--imgsz` (try 512 or 416)
- Use smaller base model (`yolo11n-seg.pt` instead of `yolo11m-seg.pt`)

### CUDA Not Available
```bash
# Check NVIDIA driver
nvidia-smi

# Check PyTorch CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Reinstall PyTorch with correct CUDA version
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### Docker GPU Access Issues
```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Test GPU access
docker run --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
```

### Virtual Environment Activation (Linux)
```bash
# CORRECT: Use 'activate' script (no extension)
source .venv/bin/activate

# WRONG: Don't use .ps1 files on Linux
# .venv/bin/Activate.ps1  # This is for Windows PowerShell!
```

---

## 📚 Additional Resources

- [Ultralytics YOLO11 Docs](https://docs.ultralytics.com/)
- [TensorFlow Lite Guide](https://www.tensorflow.org/lite/guide)
- [Albumentations Docs](https://albumentations.ai/docs/)
- [COCO Dataset Format](https://cocodataset.org/#format-data)

---

## 📄 License

This project is for internal use. Ensure compliance with licenses of dependencies (Ultralytics, TensorFlow, etc.).

---

## 👥 Support

For issues or questions, contact the development team or refer to project documentation.

**Happy Training! 🚀**
