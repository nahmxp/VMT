#!/usr/bin/env python3
"""
Azure Function App - Training Trigger
This handles the API endpoint that frontend calls to start training
"""

import os
import logging
import azure.functions as func
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.identity import DefaultAzureCredential

app = func.FunctionApp()

@app.route(route="train", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def train_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """
    Trigger training by starting Azure Container Instance
    
    Request body:
    {
        "projectId": "123",
        "epochs": 10  (optional)
    }
    """
    logging.info('Training trigger received')
    
    try:
        # Parse request
        req_body = req.get_json()
        project_id = req_body.get('projectId')
        epochs = req_body.get('epochs', 10)
        
        if not project_id:
            return func.HttpResponse(
                "Missing projectId",
                status_code=400
            )
        
        # Azure credentials from environment
        subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
        resource_group = os.environ["RESOURCE_GROUP_NAME"]
        
        vision_phone = os.environ["VISION_PHONE"]
        vision_password = os.environ["VISION_PASSWORD"]
        azure_connection_string = os.environ["AZURE_CONNECTION_STRING"]
        
        storage_account_name = "sowrovju"
        storage_account_key = os.environ["AZURE_STORAGE_KEY"]
        
        # Create container instance
        credential = DefaultAzureCredential()
        client = ContainerInstanceManagementClient(credential, subscription_id)
        
        container_name = f"vision-trainer-{project_id}"
        
        container_group = {
            "location": "eastus",
            "containers": [{
                "name": container_name,
                "image": "yourname/vision-trainer:latest",  # Update with your image
                "resources": {
                    "requests": {
                        "cpu": 2,
                        "memory_in_gb": 8
                    }
                },
                "environment_variables": [
                    {"name": "VISION_PHONE", "value": vision_phone},
                    {"name": "VISION_PASSWORD", "secure_value": vision_password},
                    {"name": "AZURE_CONNECTION_STRING", "secure_value": azure_connection_string},
                    {"name": "PROJECT_ID", "value": project_id},
                    {"name": "EPOCHS", "value": str(epochs)}
                ],
                "volume_mounts": [{
                    "name": "azurefiles",
                    "mount_path": "/mnt/azure"
                }]
            }],
            "os_type": "Linux",
            "restart_policy": "Never",
            "volumes": [{
                "name": "azurefiles",
                "azure_file": {
                    "share_name": "myshare",
                    "storage_account_name": storage_account_name,
                    "storage_account_key": storage_account_key
                }
            }]
        }
        
        # Start container
        poller = client.container_groups.begin_create_or_update(
            resource_group_name=resource_group,
            container_group_name=container_name,
            container_group=container_group
        )
        
        logging.info(f'Container {container_name} starting...')
        
        return func.HttpResponse(
            f"Training started for project {project_id}",
            status_code=202,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        logging.error(f'Error starting training: {str(e)}')
        return func.HttpResponse(
            f"Error: {str(e)}",
            status_code=500
        )


@app.route(route="status/{container_name}", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def check_status(req: func.HttpRequest) -> func.HttpResponse:
    """
    Check training status
    """
    container_name = req.route_params.get('container_name')
    
    try:
        subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
        resource_group = os.environ["RESOURCE_GROUP_NAME"]
        
        credential = DefaultAzureCredential()
        client = ContainerInstanceManagementClient(credential, subscription_id)
        
        container = client.container_groups.get(
            resource_group_name=resource_group,
            container_group_name=container_name
        )
        
        status = container.containers[0].instance_view.current_state.state
        
        return func.HttpResponse(
            f'{{"status": "{status}"}}',
            status_code=200,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        return func.HttpResponse(
            f'{{"error": "{str(e)}"}}',
            status_code=404,
            headers={"Content-Type": "application/json"}
        )
