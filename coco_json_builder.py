#!/usr/bin/env python3
"""
COCO JSON Builder for Vision API
Fetches image annotations from Vision API and generates COCO format dataset for YOLO training
"""

import requests
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import argparse
from pathlib import Path


class VisionAPIClient:
    """Client for Vision API authentication and data fetching"""
    
    def __init__(self, base_url: str = "https://visionapi.xpertcapture.com"):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        
    def login(self, phone: str, password: str) -> bool:
        """
        Login to the Vision API
        
        Args:
            phone: Phone number for authentication
            password: Password for authentication
            
        Returns:
            True if login successful, False otherwise
        """
        url = f"{self.base_url}/api/v1/auth/login"
        
        # Try different payload formats
        payloads_to_try = [
            {"phone": phone, "password": password},
            {"username": phone, "password": password},
            {"email": phone, "password": password},
        ]
        
        for idx, payload in enumerate(payloads_to_try):
            try:
                # Try as JSON first
                response = requests.post(url, json=payload)
                
                if response.status_code == 422:
                    # Try as form data
                    response = requests.post(url, data=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Handle different response formats
                    if data.get("success"):
                        # Check result field first
                        result = data.get("result", {})
                        token_data = result.get("token", result)
                        
                        # Check data field (used by this API)
                        if not token_data or not token_data.get("access_token"):
                            data_field = data.get("data", {})
                            token_data = data_field.get("token", data_field)
                        
                        self.access_token = token_data.get("access_token") or token_data.get("accessToken")
                        self.refresh_token = token_data.get("refresh_token") or token_data.get("refreshToken")
                    else:
                        # Try direct access to tokens
                        self.access_token = data.get("access_token") or data.get("accessToken")
                        self.refresh_token = data.get("refresh_token") or data.get("refreshToken")
                    
                    if self.access_token:
                        print(f"✓ Login successful")
                        return True
                    else:
                        print(f"✗ Login failed: No access token in response")
                        print(f"  Response: {data}")
                        if idx < len(payloads_to_try) - 1:
                            continue
                        return False
                elif response.status_code == 422:
                    try:
                        error_detail = response.json()
                        print(f"✗ Validation error (attempt {idx + 1}): {error_detail}")
                    except:
                        print(f"✗ Validation error (attempt {idx + 1}): {response.text}")
                    if idx < len(payloads_to_try) - 1:
                        continue
                else:
                    response.raise_for_status()
                    
            except requests.exceptions.RequestException as e:
                print(f"✗ Login error (attempt {idx + 1}): {e}")
                if idx < len(payloads_to_try) - 1:
                    continue
                    
        return False
    
    def refresh_access_token(self) -> bool:
        """
        Refresh the access token using the refresh token
        
        Returns:
            True if refresh successful, False otherwise
        """
        if not self.refresh_token:
            print("✗ No refresh token available")
            return False
            
        url = f"{self.base_url}/api/v1/auth/refresh"
        headers = {"Authorization": f"Bearer {self.refresh_token}"}
        
        try:
            response = requests.post(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            if data.get("success"):
                result = data.get("result", {})
                self.access_token = result.get("access_token")
                print(f"✓ Token refreshed successfully")
                return True
            else:
                print(f"✗ Token refresh failed: {data.get('message')}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"✗ Token refresh error: {e}")
            return False
    
    def get_all_annotations(self) -> Optional[List[Dict]]:
        """
        Fetch all image annotations from the API
        
        Returns:
            List of annotation data or None if failed
        """
        if not self.access_token:
            print("✗ No access token available. Please login first.")
            return None
            
        url = f"{self.base_url}/api/v1/image_annotations/getAll"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.get(url, headers=headers)
            
            # Try to refresh token if unauthorized
            if response.status_code == 401:
                print("⟳ Access token expired, refreshing...")
                if self.refresh_access_token():
                    headers = {"Authorization": f"Bearer {self.access_token}"}
                    response = requests.get(url, headers=headers)
                else:
                    return None
            
            response.raise_for_status()
            
            data = response.json()
            
            # Handle different response formats
            annotations = []
            if data.get("success"):
                # Try result field
                annotations = data.get("result", [])
                # Try data field
                if not annotations:
                    annotations = data.get("data", [])
            else:
                # Direct list
                if isinstance(data, list):
                    annotations = data
                    
            print(f"✓ Fetched {len(annotations)} annotations")
            return annotations if annotations else []
                
        except requests.exceptions.RequestException as e:
            print(f"✗ Error fetching annotations: {e}")
            return None


class COCODatasetBuilder:
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
            "licenses": [
                {
                    "id": 1,
                    "name": "Custom License",
                    "url": ""
                }
            ],
            "images": [],
            "annotations": [],
            "categories": []
        }
        
        self.category_map = {}  # Maps category names to IDs
        self.image_map = {}  # Maps image IDs to COCO image IDs
        self.annotation_id_counter = 1
        self.image_id_counter = 1
        self.category_id_counter = 1
    
    def add_category(self, category_name: str) -> int:
        """
        Add a category to the COCO dataset
        
        Args:
            category_name: Name of the category
            
        Returns:
            Category ID
        """
        if category_name not in self.category_map:
            category_id = self.category_id_counter
            self.category_map[category_name] = category_id
            
            self.coco_data["categories"].append({
                "id": category_id,
                "name": category_name,
                "supercategory": "product"
            })
            
            self.category_id_counter += 1
            print(f"  Added category: {category_name} (ID: {category_id})")
            
        return self.category_map[category_name]
    
    def add_image(self, image_data: Dict) -> int:
        """
        Add an image to the COCO dataset
        
        Args:
            image_data: Image data from Vision API
            
        Returns:
            COCO image ID
        """
        original_image_id = image_data.get("image_id") or image_data.get("id")
        
        if original_image_id in self.image_map:
            return self.image_map[original_image_id]
        
        coco_image_id = self.image_id_counter
        self.image_map[original_image_id] = coco_image_id
        
        # Extract image information
        image_url = image_data.get("image_url", "")
        file_name = image_data.get("image_name") or os.path.basename(image_url)
        
        self.coco_data["images"].append({
            "id": coco_image_id,
            "file_name": file_name,
            "width": image_data.get("width", 0),
            "height": image_data.get("height", 0),
            "license": 1,
            "coco_url": image_url,
            "date_captured": image_data.get("created_at", "")
        })
        
        self.image_id_counter += 1
        return coco_image_id
    
    def add_annotation(self, annotation_data: Dict, image_id: int, category_id: int):
        """
        Add an annotation to the COCO dataset
        
        Args:
            annotation_data: Annotation data with bbox/segmentation
            image_id: COCO image ID
            category_id: Category ID
        """
        # Parse annotation data
        annotation_obj = annotation_data.get("annotation_data", {})
        
        # Handle bounding box
        bbox = None
        if "bbox" in annotation_obj:
            # COCO bbox format: [x, y, width, height]
            bbox_data = annotation_obj["bbox"]
            if isinstance(bbox_data, list) and len(bbox_data) == 4:
                bbox = bbox_data
            elif isinstance(bbox_data, dict):
                x = bbox_data.get("x", 0)
                y = bbox_data.get("y", 0)
                w = bbox_data.get("width", 0)
                h = bbox_data.get("height", 0)
                bbox = [x, y, w, h]
        
        # Handle segmentation (polygon)
        segmentation = []
        if "segmentation" in annotation_obj:
            seg_data = annotation_obj["segmentation"]
            if isinstance(seg_data, list):
                segmentation = seg_data if seg_data else []
        elif "polygon" in annotation_obj:
            poly_data = annotation_obj["polygon"]
            if isinstance(poly_data, list) and len(poly_data) > 0:
                # Convert polygon points to flat list [x1, y1, x2, y2, ...]
                if isinstance(poly_data[0], dict):
                    flat_poly = []
                    for point in poly_data:
                        flat_poly.extend([point.get("x", 0), point.get("y", 0)])
                    segmentation = [flat_poly]
                elif isinstance(poly_data[0], list):
                    segmentation = poly_data
                else:
                    segmentation = [poly_data]
        
        # Calculate area
        area = 0
        if bbox:
            area = bbox[2] * bbox[3]  # width * height
        
        # Create COCO annotation
        coco_annotation = {
            "id": self.annotation_id_counter,
            "image_id": image_id,
            "category_id": category_id,
            "bbox": bbox or [0, 0, 0, 0],
            "area": area,
            "iscrowd": 0
        }
        
        if segmentation:
            coco_annotation["segmentation"] = segmentation
        else:
            coco_annotation["segmentation"] = []
        
        self.coco_data["annotations"].append(coco_annotation)
        self.annotation_id_counter += 1
    
    def build_from_api_data(self, api_data: Dict):
        """
        Build COCO dataset from Vision API data
        
        Args:
            api_data: Response data from Vision API (contains images and annotations arrays)
        """
        # Handle if api_data is a list (old format) or dict (COCO format)
        if isinstance(api_data, list):
            # Old format - list of annotation objects
            self._build_from_annotation_list(api_data)
        elif isinstance(api_data, dict):
            # New format - COCO-like with images and annotations arrays
            images = api_data.get("images", [])
            annotations = api_data.get("annotations", [])
            categories = api_data.get("categories", [])
            
            print(f"\nBuilding COCO dataset from API data...")
            print(f"  - {len(images)} images")
            print(f"  - {len(annotations)} annotations")
            print(f"  - {len(categories)} categories (from API)")
            
            # Process images first
            for image_data in images:
                self._add_image_from_api(image_data)
            
            # Process annotations
            for idx, annotation in enumerate(annotations):
                if (idx + 1) % 100 == 0:
                    print(f"  Processing annotation {idx + 1}/{len(annotations)}...")
                self._add_annotation_from_api(annotation)
            
            print(f"\n✓ COCO dataset built successfully:")
            print(f"  - {len(self.coco_data['images'])} images")
            print(f"  - {len(self.coco_data['annotations'])} annotations")
            print(f"  - {len(self.coco_data['categories'])} categories")
        else:
            print("✗ Unknown API data format")
    
    def _add_image_from_api(self, image_data: Dict):
        """Add image from Vision API format"""
        original_image_id = image_data.get("id")
        
        if original_image_id in self.image_map:
            return
        
        coco_image_id = self.image_id_counter
        self.image_map[original_image_id] = coco_image_id
        
        file_name = image_data.get("file_name", "")
        blob_url = image_data.get("blobUrl", "")
        
        self.coco_data["images"].append({
            "id": coco_image_id,
            "file_name": file_name,
            "width": image_data.get("width", 0),
            "height": image_data.get("height", 0),
            "license": 1,
            "coco_url": blob_url,
            "date_captured": image_data.get("created_at", "")
        })
        
        self.image_id_counter += 1
    
    def _add_annotation_from_api(self, annotation: Dict):
        """Add annotation from Vision API format"""
        # Get or create category
        category_name = annotation.get("category_name", "unknown")
        category_id = self.add_category(category_name)
        
        # Get mapped image ID
        original_image_id = annotation.get("image_id")
        coco_image_id = self.image_map.get(original_image_id)
        
        if not coco_image_id:
            # Image not found, skip this annotation
            print(f"  Warning: Image ID {original_image_id} not found, skipping annotation {annotation.get('id')}")
            return
        
        # Parse bbox - comes as string "[x,y,w,h]"
        bbox_str = annotation.get("bbox", "[]")
        try:
            if isinstance(bbox_str, str):
                bbox = eval(bbox_str)  # Convert string to list
            else:
                bbox = bbox_str
        except:
            bbox = [0, 0, 0, 0]
        
        # Parse segmentation - comes as string "[[x1,y1,x2,y2,...]]"
        seg_str = annotation.get("segmentation", "[]")
        try:
            if isinstance(seg_str, str):
                segmentation = eval(seg_str)  # Convert string to list
            else:
                segmentation = seg_str
                
            # Ensure it's a list of lists
            if segmentation and not isinstance(segmentation[0], list):
                segmentation = [segmentation]
        except:
            segmentation = []
        
        # Get area
        area_str = annotation.get("area", "0")
        try:
            area = float(area_str) if isinstance(area_str, str) else area_str
        except:
            area = 0
        
        # Create COCO annotation
        coco_annotation = {
            "id": self.annotation_id_counter,
            "image_id": coco_image_id,
            "category_id": category_id,
            "bbox": bbox,
            "area": area,
            "segmentation": segmentation,
            "iscrowd": annotation.get("is_crowd", 0)
        }
        
        self.coco_data["annotations"].append(coco_annotation)
        self.annotation_id_counter += 1
    
    def _build_from_annotation_list(self, annotations: List[Dict]):
        """Build from old format - list of annotations with embedded image data"""
        print(f"\nBuilding COCO dataset from {len(annotations)} annotations...")
        
        for idx, annotation in enumerate(annotations):
            if (idx + 1) % 100 == 0:
                print(f"  Processing annotation {idx + 1}/{len(annotations)}...")
            
            # Get category/product information
            product_name = annotation.get("product_name") or annotation.get("category_name", "unknown")
            category_id = self.add_category(product_name)
            
            # Add image
            image_data = annotation.get("image", {})
            if not image_data:
                # Try to extract image info from annotation itself
                image_data = {
                    "image_id": annotation.get("image_id"),
                    "image_url": annotation.get("image_url", ""),
                    "image_name": annotation.get("image_name", ""),
                    "width": annotation.get("image_width", 0),
                    "height": annotation.get("image_height", 0),
                    "created_at": annotation.get("created_at", "")
                }
            
            coco_image_id = self.add_image(image_data)
            
            # Add annotation
            self.add_annotation(annotation, coco_image_id, category_id)
        
        print(f"\n✓ COCO dataset built successfully:")
        print(f"  - {len(self.coco_data['images'])} images")
        print(f"  - {len(self.coco_data['annotations'])} annotations")
        print(f"  - {len(self.coco_data['categories'])} categories")
    
    def save(self, output_path: str):
        """
        Save COCO dataset to JSON file
        
        Args:
            output_path: Path to save the JSON file
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.coco_data, f, indent=2)
        
        print(f"\n✓ COCO dataset saved to: {output_path}")
        print(f"  File size: {os.path.getsize(output_path) / 1024:.2f} KB")


def main():
    """Main function to run the COCO builder"""
    parser = argparse.ArgumentParser(description="Build COCO JSON dataset from Vision API")
    parser.add_argument("--phone", default="01972004488", help="Phone number for authentication")
    parser.add_argument("--password", default="1111", help="Password for authentication")
    parser.add_argument("--output", default="coco_dataset.json", help="Output JSON file path")
    parser.add_argument("--base-url", default="https://visionapi.xpertcapture.com", help="API base URL")
    parser.add_argument("--save-raw", action="store_true", help="Save raw API response to file")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("COCO Dataset Builder for Vision API")
    print("=" * 60)
    
    # Step 1: Authenticate
    print("\n[1/3] Authenticating...")
    client = VisionAPIClient(base_url=args.base_url)
    
    if not client.login(args.phone, args.password):
        print("\n✗ Authentication failed. Exiting.")
        return 1
    
    # Step 2: Fetch annotations
    print("\n[2/3] Fetching annotations from API...")
    annotations = client.get_all_annotations()
    
    if annotations is None:
        print("\n✗ Failed to fetch annotations. Exiting.")
        return 1
    
    if len(annotations) == 0:
        print("\n⚠ No annotations found in the API.")
        print("  The COCO dataset will be empty.")
        print("  This could mean:")
        print("    - No images have been annotated yet")
        print("    - The user account has no access to annotations")
        print("    - The annotations are in a different endpoint")
        
        # Create empty dataset
        builder = COCODatasetBuilder()
        builder.save(args.output)
        print("\n✓ Empty COCO dataset created.")
        return 0
    
    # Save raw API response if requested
    if args.save_raw:
        raw_output = args.output.replace(".json", "_raw.json")
        with open(raw_output, 'w') as f:
            json.dump(annotations, f, indent=2)
        print(f"✓ Raw API response saved to: {raw_output}")
    
    # Step 3: Build COCO dataset
    print("\n[3/3] Building COCO dataset...")
    builder = COCODatasetBuilder()
    builder.build_from_api_data(annotations)
    builder.save(args.output)
    
    print("\n" + "=" * 60)
    print("✓ COCO dataset generation completed successfully!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    exit(main())
