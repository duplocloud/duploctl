ARG PY_VERSION=3.11

# Stage 1: Build the package
FROM python:$PY_VERSION AS builder

# Set the working directory in the container
WORKDIR /app

# Copy the source code and pyproject.toml file to the container
COPY . .

# Install build dependencies (optional, if needed)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .[build]

# Build the package without using version control information
RUN python -m build --no-isolation

# Stage 2: Install the package
FROM python:$PY_VERSION-slim

# Set the working directory in the container
WORKDIR /app

# Copy the built package from the previous stage
COPY --from=builder /app/dist ./dist/

# Install the package using pip
RUN pip install --no-cache-dir ./dist/*.whl

# Set the entrypoint command for the container
ENTRYPOINT ["duploctl"]
