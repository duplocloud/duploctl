#!/usr/bin/env bash

rm -rf \
  dist build \
  .coverage .pytest_cache .tmp \
  *.egg-info src/*.egg-info **/__pycache__ \
  .direnv

find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf
