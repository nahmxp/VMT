#!/usr/bin/env python3.10
"""
COCO Dataset Creator with Azure Files
Downloads images from Azure File Share and creates a complete COCO dataset folder structure
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import argparse
from azure.storage.fileshare import ShareServiceClient, ShareFileClient
from tqdm import tqdm


class AzureFileDownloader:
    """Handler for downloading files from Azure File Share"""
    
    def __init__(self, connection_string: str, share_name: str):
        """
        Initialize Azure File Share client
        
        Args:
            connection_string: Azure storage connection string
            share_name: Name of the file share
        """
        self.connection_string = connection_string
        self.share_name = share_name
        self.service_client = ShareServiceClient.from_connection_string(connection_string)
        self.share_client = self.service_client.get_share_client(share_name)
        
    def list_directories(self, directory_path: str = "", recursive: bool = False) -> List[str]:
        """
        List all directories in the file share
        
        Args:
            directory_path: Path to list directories from
            recursive: If True, list all subdirectories recursively
            
        Returns:
            List of directory paths
        """
        try:
            directories = []
            directory_client = self.share_client.get_directory_client(directory_path)
            items = list(directory_client.list_directories_and_files())
            
            for item in items:
                if item['is_directory']:
                    dir_path = f"{directory_path}/{item['name']}" if directory_path else item['name']
                    directories.append(dir_path)
                    
                    if recursive:
                        # Recursively get subdirectories
                        subdirs = self.list_directories(dir_path, recursive=True)
                        directories.extend(subdirs)
            
            return directories
        except Exception as e:
            print(f"Error listing directories: {e}")
            return []
    
    def list_files(self, directory_path: str = "") -> List[str]:
        """
        List all files in a directory
        
        Args:
            directory_path: Path to the directory
            
        Returns:
            List of file names
        """
        try:
            directory_client = self.share_client.get_directory_client(directory_path)
            items = list(directory_client.list_directories_and_files())
            files = [item['name'] for item in items if not item['is_directory']]
            return files
        except Exception as e:
            print(f"Error listing files in {directory_path}: {e}")
            return []
    
    def find_file(self, filename: str, search_directories: Optional[List[str]] = None) -> Optional[str]:
        """
        Search for a file in the file share
        
        Args:
            filename: Name of the file to find
            search_directories: List of directories to search in (None = search all)
            
        Returns:
            Full path to the file if found, None otherwise
        """
        if search_directories is None:
            # Get all directories
            search_directories = [""] + self.list_directories()
        
        for directory in search_directories:
            files = self.list_files(directory)
            if filename in files:
                return f"{directory}/{filename}" if directory else filename
        
        return None
    
    def download_file(self, file_path: str, local_path: str) -> bool:
        """
        Download a file from Azure File Share
        
        Args:
            file_path: Path to the file in Azure
            local_path: Local path to save the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Download file
            file_client = self.share_client.get_file_client(file_path)
            
            with open(local_path, "wb") as file_handle:
                data = file_client.download_file()
                data.readinto(file_handle)
            
            return True
        except Exception as e:
            print(f"  ✗ Error downloading {file_path}: {e}")
            return False


class COCODatasetBuilder:
    """Builder for creating COCO dataset folder structure"""
    
    def __init__(self, coco_json_path: str, output_dir: str, azure_downloader: AzureFileDownloader):
        """
        Initialize COCO dataset builder
        
        Args:
            coco_json_path: Path to the COCO JSON file
            output_dir: Output directory for the dataset
            azure_downloader: Azure file downloader instance
        """
        self.coco_json_path = coco_json_path
        self.output_dir = Path(output_dir)
        self.azure_downloader = azure_downloader
        self.coco_data = None
        
    def load_coco_json(self) -> bool:
        """
        Load COCO JSON file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.coco_json_path, 'r') as f:
                self.coco_data = json.load(f)
            
            num_images = len(self.coco_data.get('images', []))
            num_annotations = len(self.coco_data.get('annotations', []))
            num_categories = len(self.coco_data.get('categories', []))
            
            print(f"✓ Loaded COCO JSON:")
            print(f"  - {num_images} images")
            print(f"  - {num_annotations} annotations")
            print(f"  - {num_categories} categories")
            
            return True
        except Exception as e:
            print(f"✗ Error loading COCO JSON: {e}")
            return False
    
    def create_directory_structure(self):
        """Create the dataset directory structure"""
        # Create main directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create images directory
        images_dir = self.output_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        print(f"✓ Created directory structure:")
        print(f"  - {self.output_dir}")
        print(f"  - {images_dir}")
    
    def download_images(self, search_directories: Optional[List[str]] = None, skip_existing: bool = True) -> Dict:
        """
        Download images from Azure File Share
        
        Args:
            search_directories: List of directories to search for images
            skip_existing: Skip downloading if file already exists locally
            
        Returns:
            Dictionary with download statistics
        """
        if not self.coco_data:
            print("✗ COCO data not loaded")
            return {}
        
        images = self.coco_data.get('images', [])
        images_dir = self.output_dir / "images"
        
        stats = {
            'total': len(images),
            'downloaded': 0,
            'skipped': 0,
            'failed': 0,
            'not_found': 0
        }
        
        print(f"\n[Downloading Images]")
        print(f"Searching in directories: {search_directories if search_directories else 'All directories'}")
        print("-" * 60)
        
        # Get list of directories to search
        if search_directories is None:
            print("Scanning Azure File Share for directories (recursive)...")
            search_directories = [""] + self.azure_downloader.list_directories("", recursive=True)
            print(f"Found {len(search_directories)} directories to search")
        
        for image_data in tqdm(images, desc="Downloading images"):
            filename = image_data.get('file_name')
            local_path = images_dir / filename
            
            # Skip if file exists
            if skip_existing and local_path.exists():
                stats['skipped'] += 1
                continue
            
            # Find file in Azure
            azure_path = self.azure_downloader.find_file(filename, search_directories)
            
            if not azure_path:
                print(f"  ✗ File not found in Azure: {filename}")
                stats['not_found'] += 1
                continue
            
            # Download file
            if self.azure_downloader.download_file(azure_path, str(local_path)):
                stats['downloaded'] += 1
            else:
                stats['failed'] += 1
        
        return stats
    
    def save_coco_json(self):
        """Save COCO JSON to the dataset directory"""
        output_json_path = self.output_dir / "annotations.json"
        
        try:
            with open(output_json_path, 'w') as f:
                json.dump(self.coco_data, f, indent=2)
            
            print(f"✓ Saved COCO JSON to: {output_json_path}")
            return True
        except Exception as e:
            print(f"✗ Error saving COCO JSON: {e}")
            return False
    
    def create_dataset_info(self):
        """Create a README file with dataset information"""
        readme_path = self.output_dir / "README.txt"
        
        num_images = len(self.coco_data.get('images', []))
        num_annotations = len(self.coco_data.get('annotations', []))
        categories = self.coco_data.get('categories', [])
        
        content = f"""COCO Dataset
============

Created: {Path(self.coco_json_path).stat().st_mtime}
Source: {self.coco_json_path}

Statistics:
-----------
- Images: {num_images}
- Annotations: {num_annotations}
- Categories: {len(categories)}

Categories:
-----------
"""
        for cat in categories:
            content += f"  {cat['id']}: {cat['name']}\n"
        
        content += f"""
Structure:
----------
{self.output_dir.name}/
├── images/           # Image files
├── annotations.json  # COCO format annotations
└── README.txt        # This file

Usage with YOLO:
----------------
from ultralytics import YOLO

model = YOLO('yolo11n.pt')
model.train(
    data='annotations.json',
    epochs=100,
    imgsz=640
)
"""
        
        with open(readme_path, 'w') as f:
            f.write(content)
        
        print(f"✓ Created dataset info: {readme_path}")
    
    def build(self, search_directories: Optional[List[str]] = None, skip_existing: bool = True):
        """
        Build complete COCO dataset
        
        Args:
            search_directories: List of Azure directories to search
            skip_existing: Skip downloading existing files
        """
        print("=" * 60)
        print("COCO Dataset Builder")
        print("=" * 60)
        
        # Load COCO JSON
        print("\n[1/4] Loading COCO JSON...")
        if not self.load_coco_json():
            return False
        
        # Create directory structure
        print("\n[2/4] Creating directory structure...")
        self.create_directory_structure()
        
        # Download images
        print("\n[3/4] Downloading images from Azure File Share...")
        stats = self.download_images(search_directories, skip_existing)
        
        print("\n" + "-" * 60)
        print("Download Statistics:")
        print(f"  Total images:      {stats['total']}")
        print(f"  Downloaded:        {stats['downloaded']}")
        print(f"  Skipped (exists):  {stats['skipped']}")
        print(f"  Not found:         {stats['not_found']}")
        print(f"  Failed:            {stats['failed']}")
        print("-" * 60)
        
        # Save COCO JSON
        print("\n[4/4] Saving COCO JSON...")
        self.save_coco_json()
        
        # Create README
        self.create_dataset_info()
        
        print("\n" + "=" * 60)
        print("✓ COCO Dataset created successfully!")
        print(f"  Location: {self.output_dir.absolute()}")
        print("=" * 60)
        
        return True


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Create COCO dataset with images from Azure File Share")
    parser.add_argument("--coco-json", default="coco_dataset.json", help="Path to COCO JSON file")
    parser.add_argument("--output", default="coco_dataset", help="Output directory for dataset")
    parser.add_argument("--connection-string", 
                       default=None,
                       help="Azure Storage connection string (or set AZURE_STORAGE_CONNECTION_STRING)")
    parser.add_argument("--share-name", default="myshare", help="Azure File Share name")
    parser.add_argument("--search-dirs", nargs='+', help="Specific directories to search in Azure (default: all)")
    parser.add_argument("--no-skip-existing", action="store_true", help="Re-download existing files")
    
    args = parser.parse_args()
    
    # Resolve connection string (CLI arg overrides env var)
    connection_string = args.connection_string or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise SystemExit(
            "Missing Azure Storage connection string. Set AZURE_STORAGE_CONNECTION_STRING or pass --connection-string."
        )

    # Initialize Azure downloader
    print("Connecting to Azure File Share...")
    azure_downloader = AzureFileDownloader(connection_string, args.share_name)
    print("✓ Connected to Azure File Share")
    
    # Initialize dataset builder
    builder = COCODatasetBuilder(args.coco_json, args.output, azure_downloader)
    
    # Build dataset
    builder.build(
        search_directories=args.search_dirs,
        skip_existing=not args.no_skip_existing
    )


if __name__ == "__main__":
    main()
