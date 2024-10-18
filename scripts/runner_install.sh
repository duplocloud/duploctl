#!/usr/bin/env bash

# make sure to set these vars
# export GH_RUNNER_VERSION=
# export GH_RUNNER_SHA=
# export GH_RUNNER_TOKEN=

DOWNLOAD="https://github.com/actions/runner/releases/download"
PACKAGE="actions-runner-osx-arm64-${GH_RUNNER_VERSION}.tar.gz"

# Download, verify, and extract the runner
mkdir -p actions-runner && cd actions-runner
curl -o "$PACKAGE" -L "$DOWNLOAD/v${GH_RUNNER_VERSION}/${PACKAGE}"
echo "$GH_RUNNER_SHA  $PACKAGE" | shasum -a 256 -c
tar xzf "./$PACKAGE"

# configure and run
./config.sh \
  --url https://github.com/duplocloud/duploctl \
  --token "$GH_RUNNER_TOKEN" \
  --labels "self-hosted,macOS,arm64,darwin" \
  --name "${USER}-mac" \
  --unattended 
./run.sh
