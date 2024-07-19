#!/usr/bin/env bash

VERSION="2.317.0"
DOWNLOAD="https://github.com/actions/runner/releases/download"
PACKAGE="actions-runner-osx-arm64-${VERSION}.tar.gz"
SHA=70b765f32062de395a35676579e25ab433270d7367feb8da85dcfe42560feaba

# Download, verify, and extract the runner
mkdir actions-runner && cd actions-runner
curl -o $PACKAGE -L "$DOWNLOAD"/v${VERSION}/${PACKAGE}
echo "$SHA  $PACKAGE" | shasum -a 256 -c
tar xzf ./$PACKAGE

# configure and run
./config.sh --url https://github.com/duplocloud/duploctl --token "$GH_RUNNER_TOKEN"
./run.sh
