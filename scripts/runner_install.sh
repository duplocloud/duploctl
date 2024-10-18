#!/usr/bin/env bash

# https://github.com/actions/runner/releases
# make sure to set the token
# export GH_RUNNER_TOKEN=

GH_RUNNER_API="https://api.github.com/repos/actions/runner/releases/latest"
GH_RUNNER_URL="https://github.com/actions/runner/releases"
GH_RUNNER_RELEASE="$(curl -s $GH_RUNNER_API)"
GH_RUNNER_VERSION="$(echo "$GH_RUNNER_RELEASE" | jq -r '.tag_name')"
GH_RUNNER_VERSION="${GH_RUNNER_VERSION:1}"
GH_RUNNER_PACKAGE="actions-runner-osx-arm64-${GH_RUNNER_VERSION}.tar.gz"
GH_RUNNER_DOWNLOAD="$GH_RUNNER_URL/download/v${GH_RUNNER_VERSION}/${GH_RUNNER_PACKAGE}"

# discover the sha from the release notes
GH_RUNNER_RELEASE_BODY="$(echo "$GH_RUNNER_RELEASE" | jq -r '.body')"
GH_RUNNER_SHA="$(echo "$GH_RUNNER_RELEASE_BODY" | grep "\- $GH_RUNNER_PACKAGE <")"
GH_RUNNER_SHA="${GH_RUNNER_SHA#*-->}"
GH_RUNNER_SHA="${GH_RUNNER_SHA%<\!--*}"

# Download, verify, and extract the runner
mkdir -p actions-runner 
cd actions-runner || exit
curl -o "$GH_RUNNER_PACKAGE" -L "$GH_RUNNER_DOWNLOAD"
echo "$GH_RUNNER_SHA  $GH_RUNNER_PACKAGE" | shasum -a 256 -c
tar xzf "./$GH_RUNNER_PACKAGE"

# configure and run
./config.sh \
  --url https://github.com/duplocloud/duploctl \
  --token "$GH_RUNNER_TOKEN" \
  --labels "self-hosted,macOS,arm64,darwin" \
  --name "${USER}-mac" \
  --unattended 
./run.sh
