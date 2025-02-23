#!/bin/bash
set -ex

# Set DOCKER_HOST to use Unix socket
export DOCKER_HOST=unix:///var/run/docker.sock

# Wait for Docker daemon to be ready
timeout=60
counter=0
echo "Waiting for Docker daemon to be ready..."

while [ $counter -lt $timeout ]; do
    if docker version >/dev/null 2>&1; then
        echo "Docker daemon is ready!"
        break
    fi
    echo "Waiting... ($counter/$timeout)"
    counter=$((counter + 1))
    sleep 1
done

if [ $counter -eq $timeout ]; then
    echo "Timeout waiting for Docker daemon"
    echo "Docker socket status:"
    ls -l /var/run/docker.sock
    echo "Network status:"
    netstat -ln | grep -E '2375|2376'
    echo "Directory contents:"
    ls -la /app/agent-builder/
    echo "Docker daemon status:"
    ps aux | grep docker
    exit 1
fi

echo "Docker daemon is ready. Starting build process..."

# Verify required environment variables
if [ -z "$BUILD_STORAGE_PATH" ] || [ -z "$BUILD_SPEC_PATH" ]; then
    echo "Error: BUILD_STORAGE_PATH and BUILD_SPEC_PATH must be set"
    exit 1
fi

# Download file from S3
echo "Downloading file from S3..."
aws s3 cp "s3://${BUILD_STORAGE_PATH}/${BUILD_SPEC_PATH}" builddefinition.json
if [ $? -ne 0 ]; then
    echo "Failed to download file from S3"
    exit 1
fi

# Move builddefinition.json to agent-builder directory for Docker build context
mv builddefinition.json /app/agent-builder/
if [ $? -ne 0 ]; then
    echo "Failed to move builddefinition.json to agent-builder directory"
    exit 1
fi

# Read the entire JSON file content
BUILD_JSON=$(cat /app/agent-builder/builddefinition.json)

# Use environment variables for registry URL and region
REGISTRY_URL="${REGISTRY_URL:-938690564755.dkr.ecr.us-east-1.amazonaws.com}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ECR_REPO="${ECR_REPO:-duplo-langchain}"
BASE_IMAGE="${BASE_IMAGE:-938690564755.dkr.ecr.us-east-1.amazonaws.com/duplo-langchain:v1.0052}"

# Get the build date
BUILD_DATE=$(date -u +"%Y%m%d%H%M%S")
BASE_IMAGE_TAG=$(echo $BASE_IMAGE | cut -d':' -f2)

# Construct tag with base image tag and timestamp
IMAGE_TAG="${REGISTRY_URL}/${ECR_REPO}:${BASE_IMAGE_TAG}-${BUILD_DATE}"

# Authenticate with ECR
aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $REGISTRY_URL

cd /app/agent-builder
echo "Building image..."

# Build the image, passing through AWS credentials if they exist
BUILD_ARGS=(
    --build-arg BUILD_JSON="$BUILD_JSON"
    --build-arg BASE_IMAGE="$BASE_IMAGE"
)

# Check and setup AWS credentials if not provided
if [ -z "${AWS_ACCESS_KEY_ID}" ] || [ -z "${AWS_SECRET_ACCESS_KEY}" ]; then
    echo "AWS credentials not found in environment, attempting to fetch from instance metadata..."

    # Get credentials from instance metadata service
    TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    ROLE=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/)
    if [ ! -z "$ROLE" ]; then
        CREDENTIALS=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/$ROLE)
        export AWS_ACCESS_KEY_ID=$(echo $CREDENTIALS | jq -r .AccessKeyId)
        export AWS_SECRET_ACCESS_KEY=$(echo $CREDENTIALS | jq -r .SecretAccessKey)
        export AWS_SESSION_TOKEN=$(echo $CREDENTIALS | jq -r .Token)
        echo "Successfully retrieved AWS credentials from instance metadata"
    else
        echo "Warning: Could not retrieve AWS credentials from instance metadata"
    fi
fi

# Pass through AWS credentials if they exist in the parent container
if [ ! -z "${AWS_ACCESS_KEY_ID}" ]; then
    BUILD_ARGS+=(--build-arg AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}")
fi
if [ ! -z "${AWS_SECRET_ACCESS_KEY}" ]; then
    BUILD_ARGS+=(--build-arg AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}")
fi
if [ ! -z "${AWS_SESSION_TOKEN}" ]; then
    BUILD_ARGS+=(--build-arg AWS_SESSION_TOKEN="${AWS_SESSION_TOKEN}")
fi
if [ ! -z "${AWS_DEFAULT_REGION}" ]; then
    BUILD_ARGS+=(--build-arg AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION}")
fi

# Execute the build with all arguments
BUILD_CMD=("docker" "build")
BUILD_CMD+=("${BUILD_ARGS[@]}" "-t" "$IMAGE_TAG" ".")
"${BUILD_CMD[@]}" 2>&1 | tee /tmp/build.log

BUILD_EXIT_CODE=${PIPESTATUS[0]}

# Create build status file based on exit code
if [ $BUILD_EXIT_CODE -eq 0 ]; then
    echo "Success" > /tmp/build.status
    echo "Build successful, pushing image to ECR..."
    docker push $IMAGE_TAG
    PUSH_EXIT_CODE=$?
    if [ $PUSH_EXIT_CODE -ne 0 ]; then
        echo "Failed to push image to ECR"
        echo "Failure" > /tmp/build.status
        BUILD_EXIT_CODE=$PUSH_EXIT_CODE
    else
        echo "Successfully pushed image to ECR"
    fi
else
    echo "Failure" > /tmp/build.status
fi

echo "Build process completed with status: $(cat /tmp/build.status)"
exit $BUILD_EXIT_CODE
