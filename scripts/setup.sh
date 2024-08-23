#!/usr/bin/env bash

mkdir -p config dist dist/docs

pip install --editable '.[build,test,aws,docs]'

# for each folder in the plugins directory
for plugin in plugins/*; do
  # install only if the folder is a directory and a pyproject.toml file exists
  if [ -d "$plugin" ] && [ -f "$plugin/pyproject.toml" ]; then
    pip install --editable "$plugin"
  fi
done
