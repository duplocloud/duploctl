ARG PY_VERSION=3.12

# Stage 1: Build the package
FROM python:$PY_VERSION AS builder

# Set the working directory in the container
WORKDIR /app

# Copy the source code, pyproject.toml, .git file to the container
COPY . .

# Install build dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .[build]

# Build the package
RUN python -m build --no-isolation

# Stage 2: Install the package in a slimmer container
FROM python:$PY_VERSION-slim

# Set the working directory in the container
WORKDIR /app

# Copy the built package from the previous stage
COPY --from=builder /app/dist ./dist/

# Install the package using pip
RUN pip install --no-cache-dir ./dist/*.whl && \
    rm -rf ./dist

# Set the entrypoint command for the container
ENTRYPOINT ["duploctl"]
