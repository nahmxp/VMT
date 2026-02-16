# Secrets setup (local only)

This repo no longer stores secrets. Configure them locally on each machine.

## Option A: Use environment variables
Set the following variables in your shell or your system environment:

- AZURE_STORAGE_CONNECTION_STRING
- VISION_API_PHONE
- VISION_API_PASSWORD

These override values in the pipeline config at runtime.

## Option B: Use a local config file
1. Copy final_app/config.example.yaml to final_app/config.yaml
2. Fill in your values locally

The file final_app/config.yaml is ignored by git.

## For create_coco_dataset.py
Provide the connection string via:
- AZURE_STORAGE_CONNECTION_STRING, or
- the --connection-string CLI argument

## Why this is required
GitHub blocks pushes that contain secrets. Keeping credentials local avoids push failures and keeps your account safe.
