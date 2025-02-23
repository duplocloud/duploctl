FROM docker:dind

# Install required packages including AWS CLI from Alpine repositories
RUN apk add --no-cache \
    python3 \
    py3-pip \
    python3-dev \
    py3-virtualenv \
    supervisor \
    bash \
    curl \
    unzip \
    groff \
    less \
    aws-cli \
    jq

# Verify AWS CLI installation
RUN aws --version

# Create a virtual environment and install Python dependencies
RUN python3 -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install boto3

# Set the environment variable for the virtual environment
ENV PATH="/venv/bin:$PATH"

# Create app directory
RUN mkdir -p /app /var/log/supervisor /var/run/supervisor

# Copy files
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY build.sh /app/build.sh
COPY buildmonitor.py /app/buildmonitor.py
COPY agent-builder /app/agent-builder

# Make scripts executable
RUN chmod +x /app/build.sh /app/buildmonitor.py

# Set working directory
WORKDIR /app

# Start Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
