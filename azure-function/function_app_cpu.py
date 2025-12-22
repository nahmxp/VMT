"""
Azure Function - CPU Version (for Student Accounts)
Modified to work without GPU requirements
"""

import json
import logging
import os
import uuid
from datetime import datetime

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.mgmt.containerinstance.models import (
    AzureFileVolume,
    Container,
    ContainerGroup,
    ContainerGroupRestartPolicy,
    EnvironmentVariable,
    ImageRegistryCredential,
    OperatingSystemTypes,
    ResourceRequests,
    ResourceRequirements,
    Volume,
    VolumeMount,
)

app = func.FunctionApp()

# Configuration from environment variables
SUBSCRIPTION_ID = os.environ["AZURE_SUBSCRIPTION_ID"]
RESOURCE_GROUP = os.environ["AZURE_RESOURCE_GROUP"]
LOCATION = os.environ.get("AZURE_LOCATION", "eastus")

# Azure Container Registry
ACR_LOGIN_SERVER = os.environ["ACR_LOGIN_SERVER"]
ACR_USERNAME = os.environ.get("ACR_USERNAME")
ACR_PASSWORD = os.environ.get("ACR_PASSWORD")
TRAINING_IMAGE = os.environ["TRAINING_IMAGE"]

# Azure Files Storage
STORAGE_ACCOUNT_NAME = os.environ["STORAGE_ACCOUNT_NAME"]
STORAGE_ACCOUNT_KEY = os.environ["STORAGE_ACCOUNT_KEY"]
DATASET_SHARE_NAME = os.environ.get("DATASET_SHARE_NAME", "datasets")
MODEL_SHARE_NAME = os.environ.get("MODEL_SHARE_NAME", "models")
OUTPUT_SHARE_NAME = os.environ.get("OUTPUT_SHARE_NAME", "outputs")

# Training defaults (smaller for CPU testing)
DEFAULT_EPOCHS = int(os.environ.get("DEFAULT_EPOCHS", "5"))
DEFAULT_PATIENCE = int(os.environ.get("DEFAULT_PATIENCE", "3"))
DEFAULT_BATCH = int(os.environ.get("DEFAULT_BATCH", "8"))
DEFAULT_IMGSZ = int(os.environ.get("DEFAULT_IMGSZ", "320"))


logger = logging.getLogger(__name__)


def create_container_group(
    job_id: str,
    coco_zip_path: str,
    base_model_path: str,
    epochs: int,
    patience: int,
    batch: int,
    imgsz: int,
) -> ContainerGroup:
    """
    Create an Azure Container Instance with CPU for training.
    (Modified for student accounts - no GPU)
    """
    container_group_name = f"training-{job_id}"
    
    # Define volumes
    volumes = [
        Volume(
            name="datasets",
            azure_file=AzureFileVolume(
                share_name=DATASET_SHARE_NAME,
                storage_account_name=STORAGE_ACCOUNT_NAME,
                storage_account_key=STORAGE_ACCOUNT_KEY,
            ),
        ),
        Volume(
            name="models",
            azure_file=AzureFileVolume(
                share_name=MODEL_SHARE_NAME,
                storage_account_name=STORAGE_ACCOUNT_NAME,
                storage_account_key=STORAGE_ACCOUNT_KEY,
            ),
        ),
        Volume(
            name="outputs",
            azure_file=AzureFileVolume(
                share_name=OUTPUT_SHARE_NAME,
                storage_account_name=STORAGE_ACCOUNT_NAME,
                storage_account_key=STORAGE_ACCOUNT_KEY,
            ),
        ),
    ]
    
    # Define volume mounts
    volume_mounts = [
        VolumeMount(name="datasets", mount_path="/mnt/datasets", read_only=True),
        VolumeMount(name="models", mount_path="/mnt/models", read_only=True),
        VolumeMount(name="outputs", mount_path="/mnt/outputs", read_only=False),
    ]
    
    # Container command arguments (device=cpu instead of 0)
    command = [
        "--coco-zip", f"/mnt/datasets/{coco_zip_path}",
        "--base-model", f"/mnt/models/{base_model_path}",
        "--work-dir", "/app/workdir",
        "--tflite-out-dir", f"/mnt/outputs/tflite/{job_id}",
        "--epochs", str(epochs),
        "--patience", str(patience),
        "--batch", str(batch),
        "--imgsz", str(imgsz),
        "--device", "cpu",  # CPU instead of GPU
    ]
    
    # Environment variables
    environment_variables = [
        EnvironmentVariable(name="JOB_ID", value=job_id),
        EnvironmentVariable(name="STARTED_AT", value=datetime.utcnow().isoformat()),
    ]
    
    # CPU-only resource requirements (no GPU)
    resource_requirements = ResourceRequirements(
        requests=ResourceRequests(
            memory_in_gb=8,   # Reduced for student account
            cpu=2,            # 2 cores for testing
        )
    )
    
    # Container definition
    container = Container(
        name="trainer",
        image=TRAINING_IMAGE,
        resources=resource_requirements,
        command=command,
        volume_mounts=volume_mounts,
        environment_variables=environment_variables,
    )
    
    # Image registry credentials
    image_registry_credentials = None
    if ACR_USERNAME and ACR_PASSWORD:
        image_registry_credentials = [
            ImageRegistryCredential(
                server=ACR_LOGIN_SERVER,
                username=ACR_USERNAME,
                password=ACR_PASSWORD,
            )
        ]
    
    # Container group
    container_group = ContainerGroup(
        location=LOCATION,
        containers=[container],
        os_type=OperatingSystemTypes.linux,
        restart_policy=ContainerGroupRestartPolicy.never,
        volumes=volumes,
        image_registry_credentials=image_registry_credentials,
        tags={
            "job_id": job_id,
            "purpose": "yolo-training-cpu",
            "created_at": datetime.utcnow().isoformat(),
        },
    )
    
    return container_group_name, container_group


@app.route(route="train", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def trigger_training(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP trigger to start a training job."""
    logger.info("Training trigger function received request")
    
    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON in request body"}),
            status_code=400,
            mimetype="application/json",
        )
    
    # Validate required fields
    coco_zip_path = req_body.get("coco_zip_path")
    base_model_path = req_body.get("base_model_path")
    
    if not coco_zip_path or not base_model_path:
        return func.HttpResponse(
            json.dumps({
                "error": "Missing required fields: coco_zip_path, base_model_path"
            }),
            status_code=400,
            mimetype="application/json",
        )
    
    # Get parameters with defaults
    epochs = req_body.get("epochs", DEFAULT_EPOCHS)
    patience = req_body.get("patience", DEFAULT_PATIENCE)
    batch = req_body.get("batch", DEFAULT_BATCH)
    imgsz = req_body.get("imgsz", DEFAULT_IMGSZ)
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())[:8]
    
    logger.info(f"Creating CPU training job {job_id}")
    
    try:
        credential = DefaultAzureCredential()
        aci_client = ContainerInstanceManagementClient(credential, SUBSCRIPTION_ID)
        
        container_group_name, container_group = create_container_group(
            job_id=job_id,
            coco_zip_path=coco_zip_path,
            base_model_path=base_model_path,
            epochs=epochs,
            patience=patience,
            batch=batch,
            imgsz=imgsz,
        )
        
        logger.info(f"Deploying container group: {container_group_name}")
        poller = aci_client.container_groups.begin_create_or_update(
            RESOURCE_GROUP,
            container_group_name,
            container_group,
        )
        
        result = poller.result()
        
        function_app_url = os.environ.get("FUNCTION_APP_URL", "https://your-function-app.azurewebsites.net")
        status_url = f"{function_app_url}/api/status/{job_id}"
        
        response_data = {
            "job_id": job_id,
            "status": result.provisioning_state.lower(),
            "container_group_name": container_group_name,
            "status_url": status_url,
            "message": "CPU training job started successfully",
            "note": "This is CPU-only training (slower but works on student accounts)",
            "parameters": {
                "coco_zip_path": coco_zip_path,
                "base_model_path": base_model_path,
                "epochs": epochs,
                "patience": patience,
                "batch": batch,
                "imgsz": imgsz,
                "device": "cpu"
            },
        }
        
        return func.HttpResponse(
            json.dumps(response_data),
            status_code=202,
            mimetype="application/json",
        )
        
    except Exception as e:
        logger.error(f"Failed to create training job: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({
                "error": "Failed to create training job",
                "details": str(e),
            }),
            status_code=500,
            mimetype="application/json",
        )


@app.route(route="status/{job_id}", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def get_training_status(req: func.HttpRequest) -> func.HttpResponse:
    """Get the status of a training job."""
    job_id = req.route_params.get("job_id")
    
    if not job_id:
        return func.HttpResponse(
            json.dumps({"error": "Missing job_id"}),
            status_code=400,
            mimetype="application/json",
        )
    
    container_group_name = f"training-{job_id}"
    
    try:
        credential = DefaultAzureCredential()
        aci_client = ContainerInstanceManagementClient(credential, SUBSCRIPTION_ID)
        
        container_group = aci_client.container_groups.get(
            RESOURCE_GROUP,
            container_group_name,
        )
        
        container_state = None
        exit_code = None
        
        if container_group.containers and container_group.containers[0].instance_view:
            current_state = container_group.containers[0].instance_view.current_state
            if current_state:
                container_state = current_state.state
                exit_code = current_state.exit_code
        
        response_data = {
            "job_id": job_id,
            "provisioning_state": container_group.provisioning_state,
            "container_state": container_state,
            "exit_code": exit_code,
            "output_path": f"/mnt/outputs/tflite/{job_id}",
            "created_at": container_group.tags.get("created_at") if container_group.tags else None,
        }
        
        if container_group.provisioning_state == "Succeeded":
            if container_state == "Terminated":
                if exit_code == 0:
                    response_data["status"] = "completed"
                    response_data["message"] = "Training completed successfully"
                else:
                    response_data["status"] = "failed"
                    response_data["message"] = f"Training failed with exit code {exit_code}"
            else:
                response_data["status"] = "running"
                response_data["message"] = "Training in progress"
        elif container_group.provisioning_state == "Failed":
            response_data["status"] = "failed"
            response_data["message"] = "Container provisioning failed"
        else:
            response_data["status"] = "provisioning"
            response_data["message"] = "Container is being provisioned"
        
        return func.HttpResponse(
            json.dumps(response_data),
            status_code=200,
            mimetype="application/json",
        )
        
    except Exception as e:
        logger.error(f"Failed to get status for job {job_id}: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({
                "error": "Failed to get training status",
                "details": str(e),
            }),
            status_code=500,
            mimetype="application/json",
        )


@app.route(route="logs/{job_id}", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def get_training_logs(req: func.HttpRequest) -> func.HttpResponse:
    """Get the logs of a training job."""
    job_id = req.route_params.get("job_id")
    tail = req.params.get("tail", "1000")
    
    if not job_id:
        return func.HttpResponse(
            json.dumps({"error": "Missing job_id"}),
            status_code=400,
            mimetype="application/json",
        )
    
    try:
        tail = int(tail)
    except ValueError:
        tail = 1000
    
    container_group_name = f"training-{job_id}"
    
    try:
        credential = DefaultAzureCredential()
        aci_client = ContainerInstanceManagementClient(credential, SUBSCRIPTION_ID)
        
        logs = aci_client.containers.list_logs(
            RESOURCE_GROUP,
            container_group_name,
            "trainer",
            tail=tail,
        )
        
        response_data = {
            "job_id": job_id,
            "logs": logs.content,
            "tail": tail,
        }
        
        return func.HttpResponse(
            json.dumps(response_data),
            status_code=200,
            mimetype="application/json",
        )
        
    except Exception as e:
        logger.error(f"Failed to get logs for job {job_id}: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({
                "error": "Failed to get training logs",
                "details": str(e),
            }),
            status_code=500,
            mimetype="application/json",
        )


@app.route(route="cleanup/{job_id}", methods=["DELETE"], auth_level=func.AuthLevel.FUNCTION)
def cleanup_training_job(req: func.HttpRequest) -> func.HttpResponse:
    """Delete a training container group."""
    job_id = req.route_params.get("job_id")
    
    if not job_id:
        return func.HttpResponse(
            json.dumps({"error": "Missing job_id"}),
            status_code=400,
            mimetype="application/json",
        )
    
    container_group_name = f"training-{job_id}"
    
    try:
        credential = DefaultAzureCredential()
        aci_client = ContainerInstanceManagementClient(credential, SUBSCRIPTION_ID)
        
        logger.info(f"Deleting container group: {container_group_name}")
        poller = aci_client.container_groups.begin_delete(
            RESOURCE_GROUP,
            container_group_name,
        )
        poller.wait()
        
        response_data = {
            "job_id": job_id,
            "message": "Training job cleaned up successfully",
        }
        
        return func.HttpResponse(
            json.dumps(response_data),
            status_code=200,
            mimetype="application/json",
        )
        
    except Exception as e:
        logger.error(f"Failed to cleanup job {job_id}: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({
                "error": "Failed to cleanup training job",
                "details": str(e),
            }),
            status_code=500,
            mimetype="application/json",
        )
