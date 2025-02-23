#!/bin/bash
set -ex

# Check if BUILD_JSON is provided
if [ -z "$BUILD_JSON" ]; then
    echo "Error: BUILD_JSON environment variable is not set"
    exit 1
fi

echo "Starting BUILD_JSON processing..."

# Extract and set environment variables from BUILD_JSON
echo "Extracting variables from BUILD_JSON..."

# BuildRequest variables
BUILD_ID=$(echo "$BUILD_JSON" | jq -r '.BuildId // empty')
TENANT_ID=$(echo "$BUILD_JSON" | jq -r '.BuildRequest.TenantId // empty')
AGENT_NAME=$(echo "$BUILD_JSON" | jq -r '.BuildRequest.AgentName // empty')

# AgentInfo variables
AGENT_TYPE=$(echo "$BUILD_JSON" | jq -r '.AgentInfo.AgentType // empty')
PROVIDER=$(echo "$BUILD_JSON" | jq -r '.AgentInfo.Provider // empty')
MODEL_ID=$(echo "$BUILD_JSON" | jq -r '.AgentInfo.Model_Id // empty')
TEMPERATURE=$(echo "$BUILD_JSON" | jq -r '.AgentInfo.Temperature // empty')
MAX_TOKEN=$(echo "$BUILD_JSON" | jq -r '.AgentInfo.Max_Token // empty')
TOOL_DEFINITIONS=$(echo "$BUILD_JSON" | jq -r '.AgentInfo.ToolDefinitions // empty | join(",")')
PREBUILT_PACKAGE=$(echo "$BUILD_JSON" | jq -r '.AgentInfo.PrebuiltPackage // empty')
AGENT_LAST_MODIFIED=$(echo "$BUILD_JSON" | jq -r '.AgentInfo.LastModified // empty')

# Create the final ENV file for the container
{
    [ ! -z "$BUILD_ID" ] && echo "BUILD_ID=$BUILD_ID"
    [ ! -z "$TENANT_ID" ] && echo "TENANT_ID=$TENANT_ID"
    [ ! -z "$AGENT_NAME" ] && echo "AGENT_NAME=$AGENT_NAME"
    [ ! -z "$AGENT_TYPE" ] && echo "AGENT_TYPE=$AGENT_TYPE"
    [ ! -z "$PROVIDER" ] && echo "PROVIDER=$PROVIDER"
    [ ! -z "$MODEL_ID" ] && echo "MODEL_ID=$MODEL_ID"
    [ ! -z "$TEMPERATURE" ] && echo "TEMPERATURE=$TEMPERATURE"
    [ ! -z "$MAX_TOKEN" ] && echo "MAX_TOKEN=$MAX_TOKEN"
    [ ! -z "$TOOL_DEFINITIONS" ] && echo "TOOL_DEFINITIONS=$TOOL_DEFINITIONS"
    [ ! -z "$PREBUILT_PACKAGE" ] && echo "PREBUILT_PACKAGE=$PREBUILT_PACKAGE"
    [ ! -z "$AGENT_LAST_MODIFIED" ] && echo "AGENT_LAST_MODIFIED=$AGENT_LAST_MODIFIED"
} > /.env

echo "Environment variables have been written to /.env"

# Process and install apps
echo "Processing apps..."
if [ ! -z "$BUILD_JSON" ]; then
    echo "$BUILD_JSON" | jq -c '.Tools[]' | while read -r tool; do
        tool_name=$(echo "$tool" | jq -r '.Name')
        install_script=$(echo "$tool" | jq -r '.Package.InstallScript // empty')
        storage_path=$(echo "$tool" | jq -r '.Package.StorageInfo.PackagePath // empty')
        
        echo "Processing tool: $tool_name"
        
        # Download and extract tool package if provided
        if [ ! -z "$storage_path" ]; then
            echo "Downloading tool from $storage_path"
            aws s3 cp "$storage_path" "/app/$(basename "$storage_path")"
        fi
        
        # Write BuildEnvVars values to [tool_name].py
        echo "$tool" | jq -c '.BuildEnvVars[]' | while read -r env_var; do
            value=$(echo "$env_var" | jq -r '.Value')
            echo "Writing to /app/${tool_name}.py"
            mkdir -p /app
            echo "$value" >> "/app/${tool_name}.py"
        done

        # Run install script if provided
        if [ ! -z "$install_script" ]; then
            echo "Running install script for $tool_name"
            cd /app
            eval "$install_script"
        fi
    done
fi

echo "BUILD_JSON processing completed"
