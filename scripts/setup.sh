#!/usr/bin/env bash

# Create necessary directories
mkdir -p config dist dist/docs

# Optional: Create Python virtual environment
# Set DUPLO_USE_VENV=1 to enable venv creation in .venv directory
# This is automatically enabled in devcontainer environments
if [ "${DUPLO_USE_VENV}" = "1" ]; then
  echo "Creating Python virtual environment in .venv..."
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  echo "Virtual environment activated: $(which python)"
fi

# Install duploctl in editable mode with all dev dependencies
pip install --editable '.[build,test,aws,docs]'

# Install any plugins found in the plugins directory
for plugin in plugins/*; do
  # Install only if the folder is a directory and a pyproject.toml file exists
  if [ -d "$plugin" ] && [ -f "$plugin/pyproject.toml" ]; then
    echo "Installing plugin: $plugin"
    pip install --editable "$plugin"
  fi
done

echo "Setup complete!"
