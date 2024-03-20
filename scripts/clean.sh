#!/usr/bin/env bash

rm -rf dist build *.egg-info .coverage .pytest_cache .tmp
find src -type d -name __pycache__ -exec rm -rf {} \;
find src -type d -name "*.egg-info" -exec rm -rf {} \;
