"""
Simple Python client for the YOLO Training API
Usage: python api_client.py
"""

import json
import os
import time
from typing import Dict, Optional

import requests


class YOLOTrainingClient:
    """Client for interacting with the YOLO Training API."""
    
    def __init__(self, function_url: str, function_key: str):
        """
        Initialize the client.
        
        Args:
            function_url: Base URL of the Azure Function App
            function_key: Function key for authentication
        """
        self.function_url = function_url.rstrip("/")
        self.function_key = function_key
        
    def start_training(
        self,
        coco_zip_path: str,
        base_model_path: str,
        epochs: int = 100,
        patience: int = 50,
        batch: int = 24,
        imgsz: int = 640,
    ) -> Dict:
        """
        Start a new training job.
        
        Args:
            coco_zip_path: Path to COCO ZIP in Azure Files dataset share
            base_model_path: Path to base model in Azure Files model share
            epochs: Number of training epochs
            patience: Early stopping patience
            batch: Batch size
            imgsz: Image size
            
        Returns:
            Response dict with job_id, status, etc.
        """
        url = f"{self.function_url}/api/train?code={self.function_key}"
        
        payload = {
            "coco_zip_path": coco_zip_path,
            "base_model_path": base_model_path,
            "epochs": epochs,
            "patience": patience,
            "batch": batch,
            "imgsz": imgsz,
        }
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        return response.json()
    
    def get_status(self, job_id: str) -> Dict:
        """
        Get the status of a training job.
        
        Args:
            job_id: Training job ID
            
        Returns:
            Response dict with status, container_state, etc.
        """
        url = f"{self.function_url}/api/status/{job_id}?code={self.function_key}"
        
        response = requests.get(url)
        response.raise_for_status()
        
        return response.json()
    
    def get_logs(self, job_id: str, tail: int = 1000) -> str:
        """
        Get the logs of a training job.
        
        Args:
            job_id: Training job ID
            tail: Number of log lines to retrieve
            
        Returns:
            Log content as string
        """
        url = f"{self.function_url}/api/logs/{job_id}?code={self.function_key}&tail={tail}"
        
        response = requests.get(url)
        response.raise_for_status()
        
        return response.json()["logs"]
    
    def cleanup(self, job_id: str) -> Dict:
        """
        Delete a training container (cleanup).
        
        Args:
            job_id: Training job ID
            
        Returns:
            Response dict with confirmation message
        """
        url = f"{self.function_url}/api/cleanup/{job_id}?code={self.function_key}"
        
        response = requests.delete(url)
        response.raise_for_status()
        
        return response.json()
    
    def wait_for_completion(
        self,
        job_id: str,
        poll_interval: int = 30,
        timeout: Optional[int] = None,
        callback=None,
    ) -> Dict:
        """
        Wait for a training job to complete.
        
        Args:
            job_id: Training job ID
            poll_interval: Seconds between status checks
            timeout: Maximum seconds to wait (None = no timeout)
            callback: Optional function to call with each status update
            
        Returns:
            Final status dict
            
        Raises:
            TimeoutError: If timeout is reached
            RuntimeError: If training fails
        """
        start_time = time.time()
        
        while True:
            status_data = self.get_status(job_id)
            status = status_data["status"]
            
            if callback:
                callback(status_data)
            
            if status == "completed":
                return status_data
            elif status == "failed":
                raise RuntimeError(f"Training failed: {status_data.get('message')}")
            
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Training did not complete within {timeout} seconds")
            
            time.sleep(poll_interval)


def main():
    """Example usage of the YOLO Training Client."""
    
    # Configuration (replace with your values)
    FUNCTION_URL = os.environ.get("FUNCTION_APP_URL", "https://yolotraining-api.azurewebsites.net")
    FUNCTION_KEY = os.environ.get("FUNCTION_KEY", "your-function-key-here")
    
    # Initialize client
    client = YOLOTrainingClient(FUNCTION_URL, FUNCTION_KEY)
    
    print("YOLO Training API Client")
    print("=" * 50)
    
    # Start training
    print("\n1. Starting training job...")
    response = client.start_training(
        coco_zip_path="coco_dataset.zip",
        base_model_path="yolo11n-seg.pt",
        epochs=10,
        patience=5,
        batch=16,
        imgsz=640,
    )
    
    job_id = response["job_id"]
    print(f"   Job ID: {job_id}")
    print(f"   Status: {response['status']}")
    print(f"   Status URL: {response['status_url']}")
    
    # Monitor progress
    print(f"\n2. Monitoring training progress...")
    
    def status_callback(status_data):
        """Print status updates."""
        print(f"   [{time.strftime('%H:%M:%S')}] Status: {status_data['status']}")
    
    try:
        final_status = client.wait_for_completion(
            job_id,
            poll_interval=30,
            timeout=7200,  # 2 hours
            callback=status_callback,
        )
        
        print(f"\n3. Training completed successfully!")
        print(f"   Output path: {final_status['output_path']}")
        
        # Get final logs
        print(f"\n4. Getting final logs (last 50 lines)...")
        logs = client.get_logs(job_id, tail=50)
        print(logs)
        
        # Cleanup
        print(f"\n5. Cleaning up container...")
        cleanup_response = client.cleanup(job_id)
        print(f"   {cleanup_response['message']}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        
        # Get error logs
        try:
            print(f"\nGetting error logs...")
            logs = client.get_logs(job_id, tail=100)
            print(logs)
        except:
            pass


if __name__ == "__main__":
    main()
