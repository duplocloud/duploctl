# Must declare base image ARG before FROM
ARG BASE_IMAGE="938690564755.dkr.ecr.us-east-1.amazonaws.com/duplo-langchain:v1.0052"
FROM $BASE_IMAGE

# Add optional AWS credential arguments
ARG AWS_ACCESS_KEY_ID=""
ARG AWS_SECRET_ACCESS_KEY=""
ARG AWS_SESSION_TOKEN=""
ARG AWS_DEFAULT_REGION="us-east-1"

# Install basic requirements
RUN apt-get update && \
    apt-get install -y \
    curl \
    unzip \
    jq \
    python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install AWS CLI based on architecture
RUN arch=$(uname -m) && \
    case "$arch" in \
        "x86_64") ARCH="x86_64" ;; \
        "aarch64") ARCH="aarch64" ;; \
        *) echo "Unsupported architecture: $arch" && exit 1 ;; \
    esac && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-$ARCH.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf awscliv2.zip aws

# Create app directory
RUN mkdir -p /app

# Copy builddefinition.json into the image
COPY builddefinition.json /app/
COPY builddefinition.json /app/agent_build.json

# Copy and set up the BUILD_JSON parsing script
COPY parse_build_json.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/parse_build_json.sh

# Set environment variables and process BUILD_JSON
ARG BUILD_JSON
RUN if [ ! -z "$BUILD_JSON" ]; then \
    echo "Processing BUILD_JSON..." && \
    /usr/local/bin/parse_build_json.sh; \
fi

# Set AWS credentials as environment variables only if provided
RUN if [ ! -z "$AWS_ACCESS_KEY_ID" ] && [ ! -z "$AWS_SECRET_ACCESS_KEY" ]; then \
    echo "Using provided AWS credentials"; \
else \
    echo "No AWS credentials provided, will use IAM role if available"; \
fi

# Set the working directory
WORKDIR /app
