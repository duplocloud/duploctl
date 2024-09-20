#!/usr/bin/env bash

VERSION="2.319.1"
DOWNLOAD="https://github.com/actions/runner/releases/download"
PACKAGE="actions-runner-osx-arm64-${VERSION}.tar.gz"
SHA='af6a2fba35cc63415693ebfb969b4d7a9d59158e1f3587daf498d0df534bf56f'

# Download, verify, and extract the runner
mkdir -p actions-runner && cd actions-runner
curl -o $PACKAGE -L "$DOWNLOAD"/v${VERSION}/${PACKAGE}
echo "$SHA  $PACKAGE" | shasum -a 256 -c
tar xzf ./$PACKAGE

# configure and run
./config.sh --url https://github.com/duplocloud/duploctl --token "$GH_RUNNER_TOKEN"
./run.sh
