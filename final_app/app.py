#!/usr/bin/env python3
"""
Complete Vision Model Training Pipeline
Orchestrates the entire workflow from data fetching to model export
"""

import os
import sys
import json
import shutil
import argparse
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import required modules
import requests
from azure.storage.fileshare import ShareServiceClient
from tqdm import tqdm
import numpy as np
import cv2
import albumentations as A
from PIL import Image
from collections import defaultdict
import random


class PipelineConfig:
    """Configuration for the complete pipeline"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize with default config or load from file"""
        # Default configuration
        self.config = {
            # Vision API settings
            "vision_api": {
                "base_url": "https://visionapi.xpertcapture.com",
                "phone": "",
                "password": ""
            },
            
            # Azure Storage settings
            "azure_storage": {
                "connection_string": "",
                "share_name": "myshare",
                "search_dirs": None  # None = search all directories
            },
            
            # Dataset settings
            "dataset": {
                "coco_json_path": "coco_dataset.json",
                "coco_dataset_dir": "coco_dataset",
                "yolo_dataset_dir": "yolo_dataset",
                "augmented_dataset_dir": "augmented_dataset",
                "train_ratio": 0.7,
                "val_ratio": 0.2,
                "test_ratio": 0.1,
                "skip_existing_downloads": True
            },
            
            # Training settings
            "training": {
                "model_path": "./Model/yolo11m-seg.pt",
                "epochs": 10,
                "batch_size": 24,
                "imgsz": 640,
                "patience": 10,
                "workers": 0,
                "device": 0,
                "optimizer": "AdamW",
                "lr0": 0.001,
                "lrf": 0.01,
                "weight_decay": 0.0005,
                "dropout": 0.2,
                "mosaic": 1.0,
                "mixup": 0.15,
                "hsv_h": 0.015,
                "hsv_s": 0.7,
                "hsv_v": 0.4
            },
            
            # Export settings
            "export": {
                "format": "tflite",
                "output_dir": "exported_models"
            },
            
            # Pipeline control
            "pipeline": {
                "steps": {
                    "fetch_annotations": True,
                    "download_images": True,
                    "convert_to_yolo": True,
                    "augment_dataset": True,
                    "train_model": True,
                    "export_model": True
                }
            }
        }
        
        # Load from file if provided
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                loaded_config = yaml.safe_load(f)
                self._merge_config(loaded_config)

        self._apply_env_overrides()
    
    def _merge_config(self, loaded_config: dict):
        """Recursively merge loaded config with defaults"""
        def merge(target, source):
            for key, value in source.items():
                if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                    merge(target[key], value)
                else:
                    target[key] = value
        merge(self.config, loaded_config)

    def _apply_env_overrides(self):
        """Override sensitive config values from environment variables if present"""
        vision_phone = os.getenv("VISION_API_PHONE")
        vision_password = os.getenv("VISION_API_PASSWORD")
        azure_conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

        if vision_phone:
            self.config["vision_api"]["phone"] = vision_phone
        if vision_password:
            self.config["vision_api"]["password"] = vision_password
        if azure_conn:
            self.config["azure_storage"]["connection_string"] = azure_conn
    
    def save(self, path: str):
        """Save configuration to file"""
        with open(path, 'w') as f:
            yaml.safe_dump(self.config, f, default_flow_style=False, sort_keys=False)
        print(f"✓ Configuration saved to {path}")


class VisionAPIClient:
    """Client for Vision API authentication and data fetching"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
    
    def login(self, phone: str, password: str) -> bool:
        """Login to the Vision API"""
        url = f"{self.base_url}/api/v1/auth/login"
        payloads_to_try = [
            {"phone": phone, "password": password},
            {"username": phone, "password": password},
            {"email": phone, "password": password},
        ]
        
        for idx, payload in enumerate(payloads_to_try):
            try:
                response = requests.post(url, json=payload)
                
                if response.status_code == 422:
                    response = requests.post(url, data=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("success"):
                        result = data.get("result", {})
                        token_data = result.get("token", result)
                        
                        if not token_data or not token_data.get("access_token"):
                            data_field = data.get("data", {})
                            token_data = data_field.get("token", data_field)
                        
                        self.access_token = token_data.get("access_token") or token_data.get("accessToken")
                        self.refresh_token = token_data.get("refresh_token") or token_data.get("refreshToken")
                    else:
                        self.access_token = data.get("access_token") or data.get("accessToken")
                        self.refresh_token = data.get("refresh_token") or data.get("refreshToken")
                    
                    if self.access_token:
                        print(f"✓ Vision API login successful")
                        return True
                    else:
                        if idx < len(payloads_to_try) - 1:
                            continue
                        print(f"✗ Login failed: No access token in response")
                        return False
                        
            except requests.exceptions.RequestException as e:
                print(f"✗ Login error (attempt {idx + 1}): {e}")
                if idx < len(payloads_to_try) - 1:
                    continue
        
        return False
    
    def get_all_annotations(self) -> Optional[list]:
        """Fetch all image annotations from the API"""
        if not self.access_token:
            print("✗ No access token available")
            return None
        
        url = f"{self.base_url}/api/v1/image_annotations/getAll"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            annotations = []
            
            if data.get("success"):
                annotations = data.get("result", []) or data.get("data", [])
            else:
                if isinstance(data, list):
                    annotations = data
            
            print(f"✓ Fetched {len(annotations)} annotations from Vision API")
            return annotations if annotations else []
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Error fetching annotations: {e}")
            return None


class COCOBuilder:
    """Builder for COCO format JSON dataset"""
    
    def __init__(self):
        self.coco_data = {
            "info": {
                "description": "Vision API Dataset",
                "url": "https://visionapi.xpertcapture.com",
                "version": "1.0",
                "year": datetime.now().year,
                "contributor": "Xpert Vision API",
                "date_created": datetime.now().isoformat()
            },
            "licenses": [{"id": 1, "name": "Custom License", "url": ""}],
            "images": [],
            "annotations": [],
            "categories": []
        }
        
        self.category_map = {}
        self.image_map = {}
        self.annotation_id_counter = 1
        self.image_id_counter = 1
        self.category_id_counter = 1
    
    def add_category(self, category_name: str) -> int:
        """Add a category to the COCO dataset"""
        if category_name not in self.category_map:
            category_id = self.category_id_counter
            self.category_map[category_name] = category_id
            self.coco_data["categories"].append({
                "id": category_id,
                "name": category_name,
                "supercategory": "object"
            })
            self.category_id_counter += 1
        
        return self.category_map[category_name]
    
    def build_from_api_data(self, api_data):
        """Build COCO dataset from Vision API data"""
        if isinstance(api_data, list):
            self._build_from_annotation_list(api_data)
        elif isinstance(api_data, dict):
            images = api_data.get("images", [])
            annotations = api_data.get("annotations", [])
            
            print(f"\nBuilding COCO dataset...")
            print(f"  - {len(images)} images")
            print(f"  - {len(annotations)} annotations")
            
            for image_data in images:
                self._add_image_from_api(image_data)
            
            for idx, annotation in enumerate(annotations):
                if (idx + 1) % 100 == 0:
                    print(f"  Processing annotation {idx + 1}/{len(annotations)}...")
                self._add_annotation_from_api(annotation)
            
            print(f"\n✓ COCO dataset built successfully:")
            print(f"  - {len(self.coco_data['images'])} images")
            print(f"  - {len(self.coco_data['annotations'])} annotations")
            print(f"  - {len(self.coco_data['categories'])} categories")
    
    def _add_image_from_api(self, image_data: Dict):
        """Add image from Vision API format"""
        original_image_id = image_data.get("id")
        
        if original_image_id in self.image_map:
            return
        
        coco_image_id = self.image_id_counter
        self.image_map[original_image_id] = coco_image_id
        
        self.coco_data["images"].append({
            "id": coco_image_id,
            "file_name": image_data.get("file_name", ""),
            "width": image_data.get("width", 0),
            "height": image_data.get("height", 0),
            "license": 1,
            "coco_url": image_data.get("blobUrl", ""),
            "date_captured": image_data.get("created_at", "")
        })
        
        self.image_id_counter += 1
    
    def _add_annotation_from_api(self, annotation: Dict):
        """Add annotation from Vision API format"""
        category_name = annotation.get("category_name", "unknown")
        category_id = self.add_category(category_name)
        
        original_image_id = annotation.get("image_id")
        coco_image_id = self.image_map.get(original_image_id)
        
        if not coco_image_id:
            return
        
        # Parse bbox
        bbox_str = annotation.get("bbox", "[]")
        try:
            bbox = json.loads(bbox_str) if isinstance(bbox_str, str) else bbox_str
        except:
            bbox = [0, 0, 0, 0]
        
        # Parse segmentation
        seg_str = annotation.get("segmentation", "[]")
        try:
            segmentation = json.loads(seg_str) if isinstance(seg_str, str) else seg_str
            if not isinstance(segmentation, list) or len(segmentation) == 0:
                segmentation = []
        except:
            segmentation = []
        
        # Get area
        area_str = annotation.get("area", "0")
        try:
            area = float(area_str) if area_str else 0
        except:
            area = bbox[2] * bbox[3] if bbox else 0
        
        self.coco_data["annotations"].append({
            "id": self.annotation_id_counter,
            "image_id": coco_image_id,
            "category_id": category_id,
            "bbox": bbox,
            "area": area,
            "segmentation": segmentation if segmentation else [],
            "iscrowd": 0
        })
        
        self.annotation_id_counter += 1
    
    def _build_from_annotation_list(self, annotations: list):
        """Build from old format annotation list"""
        img_to_anns = defaultdict(list)
        
        for ann in annotations:
            img_id = ann.get("image_id")
            img_to_anns[img_id].append(ann)
        
        for img_id, anns in img_to_anns.items():
            if not anns:
                continue
            
            first_ann = anns[0]
            coco_image_id = self.image_id_counter
            self.image_map[img_id] = coco_image_id
            
            self.coco_data["images"].append({
                "id": coco_image_id,
                "file_name": first_ann.get("image_name", f"image_{img_id}.jpg"),
                "width": first_ann.get("width", 0),
                "height": first_ann.get("height", 0),
                "license": 1,
                "coco_url": first_ann.get("image_url", ""),
                "date_captured": first_ann.get("created_at", "")
            })
            
            self.image_id_counter += 1
            
            for ann in anns:
                category_name = ann.get("category_name", "unknown")
                category_id = self.add_category(category_name)
                
                annotation_obj = ann.get("annotation_data", {})
                bbox = annotation_obj.get("bbox", [0, 0, 0, 0])
                segmentation = annotation_obj.get("segmentation", [])
                
                area = bbox[2] * bbox[3] if bbox else 0
                
                self.coco_data["annotations"].append({
                    "id": self.annotation_id_counter,
                    "image_id": coco_image_id,
                    "category_id": category_id,
                    "bbox": bbox,
                    "area": area,
                    "segmentation": segmentation if segmentation else [],
                    "iscrowd": 0
                })
                
                self.annotation_id_counter += 1
    
    def save(self, output_path: str):
        """Save COCO JSON to file"""
        with open(output_path, 'w') as f:
            json.dump(self.coco_data, f, indent=2)
        print(f"✓ COCO JSON saved to {output_path}")


class AzureFileDownloader:
    """Handler for downloading files from Azure File Share"""
    
    def __init__(self, connection_string: str, share_name: str):
        self.connection_string = connection_string
        self.share_name = share_name
        self.service_client = ShareServiceClient.from_connection_string(connection_string)
        self.share_client = self.service_client.get_share_client(share_name)
    
    def list_directories(self, directory_path: str = "", recursive: bool = False) -> list:
        """List all directories in the file share"""
        try:
            directories = []
            directory_client = self.share_client.get_directory_client(directory_path)
            items = list(directory_client.list_directories_and_files())
            
            for item in items:
                if item['is_directory']:
                    dir_path = f"{directory_path}/{item['name']}" if directory_path else item['name']
                    directories.append(dir_path)
                    if recursive:
                        directories.extend(self.list_directories(dir_path, recursive=True))
            
            return directories
        except Exception as e:
            print(f"Error listing directories: {e}")
            return []
    
    def list_files(self, directory_path: str = "") -> list:
        """List all files in a directory"""
        try:
            directory_client = self.share_client.get_directory_client(directory_path)
            items = list(directory_client.list_directories_and_files())
            return [item['name'] for item in items if not item['is_directory']]
        except Exception as e:
            print(f"Error listing files in {directory_path}: {e}")
            return []
    
    def find_file(self, filename: str, search_directories: Optional[list] = None) -> Optional[str]:
        """Search for a file in the file share"""
        if search_directories is None:
            search_directories = [""] + self.list_directories("", recursive=True)
        
        for directory in search_directories:
            files = self.list_files(directory)
            if filename in files:
                return f"{directory}/{filename}" if directory else filename
        
        return None
    
    def download_file(self, file_path: str, local_path: str) -> bool:
        """Download a file from Azure File Share"""
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            file_client = self.share_client.get_file_client(file_path)
            
            with open(local_path, "wb") as file_handle:
                data = file_client.download_file()
                data.readinto(file_handle)
            
            return True
        except Exception as e:
            print(f"Error downloading {file_path}: {e}")
            return False


class COCODatasetDownloader:
    """Downloads images and creates COCO dataset structure"""
    
    def __init__(self, coco_json_path: str, output_dir: str, azure_downloader: AzureFileDownloader):
        self.coco_json_path = coco_json_path
        self.output_dir = Path(output_dir)
        self.azure_downloader = azure_downloader
        self.coco_data = None
    
    def load_coco_json(self) -> bool:
        """Load COCO JSON file"""
        try:
            with open(self.coco_json_path, 'r') as f:
                self.coco_data = json.load(f)
            print(f"✓ Loaded COCO JSON: {len(self.coco_data.get('images', []))} images")
            return True
        except Exception as e:
            print(f"✗ Error loading COCO JSON: {e}")
            return False
    
    def create_directory_structure(self):
        """Create the dataset directory structure"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "images").mkdir(exist_ok=True)
        print(f"✓ Created directory structure: {self.output_dir}")
    
    def download_images(self, search_directories: Optional[list] = None, skip_existing: bool = True) -> Dict:
        """Download images from Azure File Share"""
        if not self.coco_data:
            return {}
        
        images = self.coco_data.get('images', [])
        images_dir = self.output_dir / "images"
        
        stats = {'total': len(images), 'downloaded': 0, 'skipped': 0, 'failed': 0, 'not_found': 0}
        
        print(f"\nDownloading {stats['total']} images from Azure...")
        
        if search_directories is None:
            search_directories = [""] + self.azure_downloader.list_directories("", recursive=True)
        
        for image_data in tqdm(images, desc="Downloading images"):
            filename = image_data.get('file_name')
            local_path = images_dir / filename
            
            if skip_existing and local_path.exists():
                stats['skipped'] += 1
                continue
            
            azure_path = self.azure_downloader.find_file(filename, search_directories)
            
            if not azure_path:
                stats['not_found'] += 1
                continue
            
            if self.azure_downloader.download_file(azure_path, str(local_path)):
                stats['downloaded'] += 1
            else:
                stats['failed'] += 1
        
        return stats
    
    def save_coco_json(self):
        """Save COCO JSON to the dataset directory"""
        output_json = self.output_dir / "annotations.json"
        with open(output_json, 'w') as f:
            json.dump(self.coco_data, f, indent=2)
        print(f"✓ Saved annotations to {output_json}")



# --- Replacement: Use exact logic from cnv.py ---
def coco_to_yolo(coco_json, output_dir, train_ratio=0.7, val_ratio=0.2, test_ratio=0.1):
    with open(coco_json, 'r') as f:
        coco = json.load(f)

    images = {img["id"]: img for img in coco["images"]}
    annotations = coco["annotations"]
    categories = {cat["id"]: cat["name"] for cat in coco["categories"]}
    category_mapping = {cat_id: idx for idx, cat_id in enumerate(categories.keys())}

    # Create YOLO dirs
    for split in ["train", "val", "test"]:
        os.makedirs(os.path.join(output_dir, "images", split), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "labels", split), exist_ok=True)

    # Split dataset
    image_ids = list(images.keys())
    random.shuffle(image_ids)
    n_images = len(image_ids)
    n_train = int(n_images * train_ratio)
    n_val = int(n_images * val_ratio)
    # Ensure all images are assigned: remainder goes to test
    n_test = n_images - n_train - n_val
    train_ids = set(image_ids[:n_train])
    val_ids = set(image_ids[n_train:n_train+n_val])
    test_ids = set(image_ids[n_train+n_val:n_train+n_val+n_test])

    img_to_anns = defaultdict(list)
    for ann in annotations:
        img_to_anns[ann["image_id"]].append(ann)


    for img_id, anns in tqdm(img_to_anns.items(), desc="Converting"):
        img_info = images[img_id]
        file_name = img_info["file_name"]

        # Robustly get width/height: if missing or zero, read from image file
        width = img_info.get("width", 0)
        height = img_info.get("height", 0)
        # Always look for images in 'images' subfolder
        img_path = Path(coco_json).parent / "images" / file_name
        if not width or not height:
            if img_path.exists():
                with Image.open(img_path) as im:
                    width, height = im.size
            else:
                print(f"Warning: Image file {img_path} not found to get dimensions. Skipping.")
                continue

        # Decide split
        if img_id in train_ids:
            split = "train"
        elif img_id in val_ids:
            split = "val"
        else:
            split = "test"

        # Copy image
        src_path = Path(coco_json).parent / "images" / file_name
        dst_path = Path(output_dir) / "images" / split / Path(file_name).name
        os.makedirs(dst_path.parent, exist_ok=True)
        if os.path.exists(src_path):
            shutil.copy(src_path, dst_path)

        # Write YOLO label
        label_path = Path(output_dir) / "labels" / split / (Path(file_name).stem + ".txt")
        with open(label_path, "w") as f:
            for ann in anns:
                cat_id = ann["category_id"]
                class_id = category_mapping[cat_id]

                # Handle polygons if available
                if "segmentation" in ann and isinstance(ann["segmentation"], list) and len(ann["segmentation"]) > 0:
                    poly = np.array(ann["segmentation"][0]).reshape(-1, 2)
                    poly[:, 0] /= width
                    poly[:, 1] /= height
                    poly_str = " ".join([f"{x:.6f} {y:.6f}" for x, y in poly])
                    f.write(f"{class_id} {poly_str}\n")
                else:
                    # Fallback to bbox
                    x, y, w, h = ann["bbox"]
                    cx, cy = (x + w / 2) / width, (y + h / 2) / height
                    nw, nh = w / width, h / height
                    f.write(f"{class_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}\n")

    # Create dataset.yaml
    yaml_dict = {
        "train": str(Path(output_dir) / "images/train"),
        "val": str(Path(output_dir) / "images/val"),
        "test": str(Path(output_dir) / "images/test"),
        "names": [categories[k] for k in sorted(categories.keys())]
    }
    with open(Path(output_dir) / "dataset.yaml", "w") as yf:
        yaml.dump(yaml_dict, yf, default_flow_style=False)

    print(f"\n✅ Conversion complete! Dataset saved in {output_dir}")


class YOLOAugmenter:
    """Augments YOLO dataset with various transformations"""
    
    def __init__(self, input_dir: str, output_dir: str, input_yaml: str = "dataset.yaml"):
        print(f"[DEBUG] YOLOAugmenter __init__ called from: {__file__} with input_dir={input_dir}, output_dir={output_dir}, input_yaml={input_yaml}")
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.input_yaml = input_yaml

    @staticmethod
    def parse_yolo_label(line):
        parts = line.strip().split()
        cls = int(parts[0])
        coords = list(map(float, parts[1:]))
        if len(coords) == 4:
            return {"class": cls, "bbox": coords, "poly": None}
        else:
            poly = [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
            return {"class": cls, "bbox": None, "poly": poly}

    @staticmethod
    def save_yolo_label(path: Path, labels):
        with open(path, "w") as f:
            for lab in labels:
                cls = lab["class"]
                if lab["bbox"] is not None:
                    cx, cy, w, h = lab["bbox"]
                    f.write(f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
                elif lab["poly"] is not None:
                    poly_str = " ".join([f"{x:.6f} {y:.6f}" for x, y in lab["poly"]])
                    f.write(f"{cls} {poly_str}\n")

    @staticmethod
    def low_res(img, **kwargs):
        scale_factor = np.random.uniform(0.3, 0.5)
        h, w = img.shape[:2]
        new_h, new_w = max(1, int(h * scale_factor)), max(1, int(w * scale_factor))
        img_small = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        img_up = cv2.resize(img_small, (w, h), interpolation=cv2.INTER_LINEAR)
        return img_up

    def augment(self):
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)

        for split in ["train", "val", "test"]:
            (self.output_dir / split / "images").mkdir(parents=True, exist_ok=True)
            (self.output_dir / split / "labels").mkdir(parents=True, exist_ok=True)

        geo_augs = [
            ("hflip", A.HorizontalFlip(p=1.0)),
            ("vflip", A.VerticalFlip(p=1.0)),
            ("rot90", A.Rotate(limit=(90, 90), p=1.0)),
            ("rot180", A.Rotate(limit=(180, 180), p=1.0)),
            ("rot270", A.Rotate(limit=(270, 270), p=1.0)),
            ("shear_x15", A.Affine(shear={"x": 15, "y": 0}, p=1.0)),
            ("shear_x-15", A.Affine(shear={"x": -15, "y": 0}, p=1.0)),
            ("shear_y15", A.Affine(shear={"x": 0, "y": 15}, p=1.0)),
            ("shear_y-15", A.Affine(shear={"x": 0, "y": -15}, p=1.0)),
        ]

        fine_rotations = [
            (f"rot{i}", A.Rotate(limit=(i, i), p=1.0)) for i in range(12, 360, 12)
        ]

        zoom_outs = [
            (f"zoom_{scale}", A.Affine(scale=scale / 100.0, p=1.0)) for scale in range(90, 30, -10)
        ]

        geo_augs = geo_augs + fine_rotations + zoom_outs

        photo_augs = [
            ("brightness_contrast", A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.7)),
            ("hsv_shift", A.HueSaturationValue(hue_shift_limit=15, sat_shift_limit=20, val_shift_limit=15, p=0.7)),
            ("rgb_shift", A.RGBShift(r_shift_limit=15, g_shift_limit=15, b_shift_limit=15, p=0.5)),
            ("clahe", A.CLAHE(clip_limit=2.0, tile_grid_size=(8,8), p=0.3)),
            ("gamma", A.RandomGamma(gamma_limit=(80, 120), p=0.5)),
            ("motion_blur", A.MotionBlur(blur_limit=3, p=0.3)),
            ("gauss_noise", A.GaussNoise(p=0.3)),
            ("low_light", A.RandomBrightnessContrast(brightness_limit=(-0.6, -0.4), contrast_limit=(-0.4, -0.2), p=1.0)),
            ("overexposed", A.RandomBrightnessContrast(brightness_limit=(0.4, 0.6), contrast_limit=(0.2, 0.4), p=1.0)),
            ("reflection_reduce", A.Sequential([
                A.MedianBlur(blur_limit=5, p=1.0),
                A.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.1, p=1.0)
            ], p=1.0)),
            ("low_res", A.Lambda(image=self.low_res, p=1.0)),
        ]

        for split in ["train", "val", "test"]:
            img_dir = self.input_dir / split / "images"
            lbl_dir = self.input_dir / split / "labels"
            out_img_dir = self.output_dir / split / "images"
            out_lbl_dir = self.output_dir / split / "labels"

            img_files = sorted(list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png")) + list(img_dir.glob("*.jpeg")))
            print(f"[{split}] Found {len(img_files)} images in {img_dir}")

            for img_file in tqdm(img_files, desc=f"Augment {split}"):
                label_file = lbl_dir / (img_file.stem + ".txt")
                image = cv2.imread(str(img_file))
                if image is None:
                    print(f"Warning: Could not read {img_file}")
                    continue
                orig_h, orig_w = image.shape[:2]

                labels = []
                if label_file.exists():
                    with open(label_file, "r") as f:
                        for line in f:
                            if line.strip():
                                labels.append(self.parse_yolo_label(line))

                shutil.copy(str(img_file), str(out_img_dir / img_file.name))
                if label_file.exists():
                    shutil.copy(str(label_file), str(out_lbl_dir / label_file.name))

                keypoints, keypoints_cls, poly_splits, bboxes_pascal, bboxes_cls = [], [], [], [], []

                for lab in labels:
                    if lab["bbox"] is not None:
                        cx, cy, bw, bh = lab["bbox"]
                        x1 = (cx - bw/2) * orig_w
                        y1 = (cy - bh/2) * orig_h
                        x2 = (cx + bw/2) * orig_w
                        y2 = (cy + bh/2) * orig_h
                        bboxes_pascal.append([x1, y1, x2, y2])
                        bboxes_cls.append(lab["class"])
                    elif lab["poly"] is not None:
                        abs_poly = [(px * orig_w, py * orig_h) for px, py in lab["poly"]]
                        start = len(keypoints)
                        for pt in abs_poly:
                            keypoints.append(pt)
                            keypoints_cls.append(lab["class"])
                        poly_splits.append((lab["class"], start, len(abs_poly)))

                # Geometric augmentations
                if len(bboxes_pascal) > 0 or len(keypoints) > 0:
                    for name, aug in geo_augs:
                        transform = A.Compose(
                            [aug],
                            bbox_params=A.BboxParams(format="pascal_voc", label_fields=["bboxes_cls"]),
                            keypoint_params=A.KeypointParams(format="xy", remove_invisible=False, label_fields=["keypoints_cls"]),
                        )

                        transformed = transform(
                            image=image,
                            bboxes=bboxes_pascal,
                            bboxes_cls=bboxes_cls,
                            keypoints=keypoints,
                            keypoints_cls=keypoints_cls,
                        )

                        aug_img = transformed["image"]
                        new_h, new_w = aug_img.shape[:2]

                        new_labels = []
                        for bbox, cls in zip(transformed["bboxes"], transformed["bboxes_cls"]):
                            x1, y1, x2, y2 = bbox
                            cx = ((x1 + x2) / 2) / new_w
                            cy = ((y1 + y2) / 2) / new_h
                            bw = (x2 - x1) / new_w
                            bh = (y2 - y1) / new_h
                            new_labels.append({"class": cls, "bbox": [cx, cy, bw, bh], "poly": None})

                        if poly_splits:
                            for cls, start, length in poly_splits:
                                pts = transformed["keypoints"][start:start+length]
                                norm = [(max(min(x / new_w, 1.0), 0.0), max(min(y / new_h, 1.0), 0.0)) for x, y in pts]
                                if len(norm) >= 3:
                                    new_labels.append({"class": cls, "bbox": None, "poly": norm})
                                else:
                                    bbox_norm = self.polygon_to_bbox_norm([(x*new_w, y*new_h) for x,y in norm], new_w, new_h)
                                    new_labels.append({"class": cls, "bbox": bbox_norm, "poly": None})

                        cv2.imwrite(str(out_img_dir / f"{img_file.stem}_{name}.jpg"), aug_img)
                        self.save_yolo_label(out_lbl_dir / f"{img_file.stem}_{name}.txt", new_labels)

                # Photometric augmentations
                for name, aug in photo_augs:
                    transform = A.Compose([aug])
                    transformed = transform(image=image)
                    aug_img = transformed["image"]
                    new_h, new_w = aug_img.shape[:2]

                    cv2.imwrite(str(out_img_dir / f"{img_file.stem}_{name}.jpg"), aug_img)

                    new_labels = []
                    for bbox, cls in zip(bboxes_pascal, bboxes_cls):
                        x1, y1, x2, y2 = bbox
                        cx = ((x1 + x2) / 2) / new_w
                        cy = ((y1 + y2) / 2) / new_h
                        bw = (x2 - x1) / new_w
                        bh = (y2 - y1) / new_h
                        new_labels.append({"class": cls, "bbox": [cx, cy, bw, bh], "poly": None})

                    for cls, start, length in poly_splits:
                        pts = keypoints[start:start+length]
                        norm = [(x / new_w, y / new_h) for x, y in pts]
                        if len(norm) >= 3:
                            new_labels.append({"class": cls, "bbox": None, "poly": norm})
                        else:
                            bbox_norm = self.polygon_to_bbox_norm(pts, new_w, new_h)
                            new_labels.append({"class": cls, "bbox": bbox_norm, "poly": None})

                    self.save_yolo_label(out_lbl_dir / f"{img_file.stem}_{name}.txt", new_labels)

        # YAML Update
        input_yaml_path = self.input_dir / self.input_yaml
        output_yaml_path = self.output_dir / "data.yaml"
        if input_yaml_path.exists():
            with open(input_yaml_path, "r") as f:
                data_cfg = yaml.safe_load(f)
            data_cfg["train"] = str((self.output_dir / "train" / "images").resolve())
            data_cfg["valid"] = str((self.output_dir / "val" / "images").resolve())
            data_cfg["test"] = str((self.output_dir / "test" / "images").resolve())
            with open(output_yaml_path, "w") as f:
                yaml.safe_dump(data_cfg, f, sort_keys=False)
        else:
            print("⚠️ No dataset yaml found in input_dir.")

        print(f"\n✅ Augmentation complete! Augmented dataset saved in {self.output_dir}")

    @staticmethod
    def polygon_to_bbox_norm(poly_pts, img_w, img_h):
        xs = [p[0] for p in poly_pts]
        ys = [p[1] for p in poly_pts]
        x1, x2 = min(xs), max(xs)
        y1, y2 = min(ys), max(ys)
        cx = ((x1 + x2) / 2) / img_w
        cy = ((y1 + y2) / 2) / img_h
        bw = (x2 - x1) / img_w
        bh = (y2 - y1) / img_h
        return [cx, cy, bw, bh]
    def __init__(self, config: dict):
        self.config = config
    
    def train(self, data_yaml: str):
        """Train the YOLO model"""
        from ultralytics import YOLO
        
        print("\n" + "="*60)
        print("Starting YOLO Model Training")
        print("="*60)
        
        # Load model
        model_path = self.config.get("model_path", "./Model/yolo11m-seg.pt")
        print(f"\nLoading model: {model_path}")
        model = YOLO(model_path)
        
        # Train
        print(f"Training on: {data_yaml}")
        results = model.train(
            data=data_yaml,
            imgsz=self.config.get("imgsz", 640),
            batch=self.config.get("batch_size", 24),
            epochs=self.config.get("epochs", 10),
            patience=self.config.get("patience", 10),
            workers=self.config.get("workers", 0),
            device=self.config.get("device", 0),
            optimizer=self.config.get("optimizer", "AdamW"),
            lr0=self.config.get("lr0", 0.001),
            lrf=self.config.get("lrf", 0.01),
            weight_decay=self.config.get("weight_decay", 0.0005),
            dropout=self.config.get("dropout", 0.2),
            mosaic=self.config.get("mosaic", 1.0),
            mixup=self.config.get("mixup", 0.15),
            hsv_h=self.config.get("hsv_h", 0.015),
            hsv_s=self.config.get("hsv_s", 0.7),
            hsv_v=self.config.get("hsv_v", 0.4)
        )
        
        print("\n✓ Training complete!")
        return results


class ModelExporter:
    """Exports trained model to different formats"""
    
    def __init__(self, config: dict):
        self.config = config
    
    def export(self, model_path: str, format: str = "tflite"):
        """Export the model"""
        from ultralytics import YOLO
        
        print("\n" + "="*60)
        print(f"Exporting Model to {format.upper()}")
        print("="*60)
        
        model = YOLO(model_path)
        exported_model = model.export(format=format)
        
        # Move to export directory
        output_dir = Path(self.config.get("output_dir", "exported_models"))
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if exported_model:
            export_path = Path(exported_model)
            final_path = output_dir / export_path.name
            shutil.copy(exported_model, final_path)
            print(f"\n✓ Model exported to: {final_path}")
            return str(final_path)
        
        return None


class Pipeline:
    """Main pipeline orchestrator"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.start_time = datetime.now()
    
    def print_header(self, title: str):
        """Print formatted section header"""
        print("\n" + "="*60)
        print(f" {title}")
        print("="*60 + "\n")
    
    def run(self):
        """Run the complete pipeline"""
        self.print_header("VISION MODEL TRAINING PIPELINE")
        print(f"Started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        steps = self.config.config["pipeline"]["steps"]
        
        try:
            # Step 1: Fetch annotations from Vision API
            if steps.get("fetch_annotations", True):
                self.print_header("STEP 1: Fetch Annotations from Vision API")
                
                api_config = self.config.config["vision_api"]
                client = VisionAPIClient(api_config["base_url"])
                
                if not client.login(api_config["phone"], api_config["password"]):
                    raise Exception("Failed to login to Vision API")
                
                annotations = client.get_all_annotations()
                if annotations is None:
                    raise Exception("Failed to fetch annotations")
                
                # Build COCO JSON
                builder = COCOBuilder()
                builder.build_from_api_data(annotations)
                
                coco_json_path = self.config.config["dataset"]["coco_json_path"]
                builder.save(coco_json_path)
                
                print(f"\n✓ Step 1 Complete: COCO JSON created")
            else:
                print("\n⊗ Step 1 Skipped: fetch_annotations = False")
            
            # Step 2: Download images from Azure Files
            if steps.get("download_images", True):
                self.print_header("STEP 2: Download Images from Azure Files")
                
                azure_config = self.config.config["azure_storage"]
                dataset_config = self.config.config["dataset"]
                
                downloader = AzureFileDownloader(
                    azure_config["connection_string"],
                    azure_config["share_name"]
                )
                
                coco_downloader = COCODatasetDownloader(
                    dataset_config["coco_json_path"],
                    dataset_config["coco_dataset_dir"],
                    downloader
                )
                
                if not coco_downloader.load_coco_json():
                    raise Exception("Failed to load COCO JSON")
                
                coco_downloader.create_directory_structure()
                
                stats = coco_downloader.download_images(
                    search_directories=azure_config["search_dirs"],
                    skip_existing=dataset_config["skip_existing_downloads"]
                )
                
                print(f"\nDownload Statistics:")
                print(f"  Total: {stats['total']}")
                print(f"  Downloaded: {stats['downloaded']}")
                print(f"  Skipped: {stats['skipped']}")
                print(f"  Not found: {stats['not_found']}")
                print(f"  Failed: {stats['failed']}")
                
                coco_downloader.save_coco_json()
                
                print(f"\n✓ Step 2 Complete: Images downloaded")
            else:
                print("\n⊗ Step 2 Skipped: download_images = False")
            
            # Step 3: Convert COCO to YOLO format
            if steps.get("convert_to_yolo", True):
                self.print_header("STEP 3: Convert COCO to YOLO Format")
                
                dataset_config = self.config.config["dataset"]
                coco_json = str(Path(dataset_config["coco_dataset_dir"]) / "annotations.json")
                
                coco_to_yolo(
                    coco_json,
                    dataset_config["yolo_dataset_dir"],
                    dataset_config["train_ratio"],
                    dataset_config["val_ratio"],
                    dataset_config["test_ratio"]
                )
                
                print(f"\n✓ Step 3 Complete: COCO converted to YOLO")
            else:
                print("\n⊗ Step 3 Skipped: convert_to_yolo = False")
            
            # Step 4: Augment dataset
            if steps.get("augment_dataset", True):
                self.print_header("STEP 4: Augment YOLO Dataset")
                
                dataset_config = self.config.config["dataset"]
                
                augmenter = YOLOAugmenter(
                    dataset_config["yolo_dataset_dir"],
                    dataset_config["augmented_dataset_dir"]
                )
                
                augmenter.augment()
                
                print(f"\n✓ Step 4 Complete: Dataset augmented")
            else:
                print("\n⊗ Step 4 Skipped: augment_dataset = False")
            
            # Step 5: Train model
            if steps.get("train_model", True):
                self.print_header("STEP 5: Train YOLO Model")
                
                dataset_config = self.config.config["dataset"]
                training_config = self.config.config["training"]
                
                data_yaml = str(Path(dataset_config["augmented_dataset_dir"]) / "data.yaml")
                
                trainer = ModelTrainer(training_config)
                results = trainer.train(data_yaml)
                
                print(f"\n✓ Step 5 Complete: Model trained")
            else:
                print("\n⊗ Step 5 Skipped: train_model = False")
            
            # Step 6: Export model
            if steps.get("export_model", True):
                self.print_header("STEP 6: Export Trained Model")
                
                export_config = self.config.config["export"]
                
                # Find latest trained model
                runs_dir = Path("runs/segment")
                if runs_dir.exists():
                    train_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir() and d.name.startswith("train")])
                    if train_dirs:
                        latest_train = train_dirs[-1]
                        best_model = latest_train / "weights" / "best.pt"
                        
                        if best_model.exists():
                            exporter = ModelExporter(export_config)
                            exported_path = exporter.export(
                                str(best_model),
                                export_config.get("format", "tflite")
                            )
                            
                            print(f"\n✓ Step 6 Complete: Model exported")
                        else:
                            print(f"\n✗ Best model not found at: {best_model}")
                    else:
                        print(f"\n✗ No training runs found in {runs_dir}")
                else:
                    print(f"\n✗ Runs directory not found: {runs_dir}")
            else:
                print("\n⊗ Step 6 Skipped: export_model = False")
            
            # Pipeline complete
            end_time = datetime.now()
            duration = end_time - self.start_time
            
            self.print_header("PIPELINE COMPLETE")
            print(f"Started:  {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Duration: {duration}")
            print("\n✓ All steps completed successfully!")
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"\n✗ Pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Complete Vision Model Training Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  # Run full pipeline with default config
  python app.py
  
  # Generate default config file
  python app.py --save-config config.yaml
  
  # Run with custom config
  python app.py --config config.yaml
  
  # Skip certain steps
  python app.py --skip-augment --skip-training
        """
    )
    
    parser.add_argument("--config", help="Path to configuration YAML file")
    parser.add_argument("--save-config", help="Save default configuration to file and exit")
    
    # Skip options
    parser.add_argument("--skip-fetch", action="store_true", help="Skip fetching annotations")
    parser.add_argument("--skip-download", action="store_true", help="Skip downloading images")
    parser.add_argument("--skip-convert", action="store_true", help="Skip COCO to YOLO conversion")
    parser.add_argument("--skip-augment", action="store_true", help="Skip dataset augmentation")
    parser.add_argument("--skip-training", action="store_true", help="Skip model training")
    parser.add_argument("--skip-export", action="store_true", help="Skip model export")
    
    args = parser.parse_args()
    
    # Load or create config
    config = PipelineConfig(args.config)
    
    # Apply skip flags
    if args.skip_fetch:
        config.config["pipeline"]["steps"]["fetch_annotations"] = False
    if args.skip_download:
        config.config["pipeline"]["steps"]["download_images"] = False
    if args.skip_convert:
        config.config["pipeline"]["steps"]["convert_to_yolo"] = False
    if args.skip_augment:
        config.config["pipeline"]["steps"]["augment_dataset"] = False
    if args.skip_training:
        config.config["pipeline"]["steps"]["train_model"] = False
    if args.skip_export:
        config.config["pipeline"]["steps"]["export_model"] = False
    
    # Save config if requested
    if args.save_config:
        config.save(args.save_config)
        print(f"You can now edit {args.save_config} and run: python app.py --config {args.save_config}")
        return 0
    
    # Run pipeline
    pipeline = Pipeline(config)
    success = pipeline.run()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
