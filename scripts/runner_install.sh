#!/usr/bin/env bash

# https://github.com/actions/runner/releases
# make sure to set the token as an environment variable or pass it as an argument
GH_RUNNER_TOKEN="${1:-$GH_RUNNER_TOKEN}"

# discover the os
case "$(uname -s)" in
  Darwin)
    GH_RUNNER_OS="osx"
    GH_RUNNER_EXTRA_LABELS="macOS,darwin"
    ;;
  Linux)
    GH_RUNNER_OS="linux"
    GH_RUNNER_EXTRA_LABELS="nix"
    ;;
  CYGWIN*|MINGW32*|MSYS*)
    GH_RUNNER_OS="win"
    GH_RUNNER_EXTRA_LABELS="windows"
    ;;
  *)
    echo "Unsupported OS"
    exit 1
    ;;
esac

# discover the architecture
case "$(uname -m)" in
  arm64)
    GH_RUNNER_ARCH="arm64"
    ;;
  x86_64)
    GH_RUNNER_ARCH="x64"
    ;;
  *)
    echo "Unsupported ARCH"
    exit 1
    ;;
esac

# runner config details
GH_RUNNER="actions-runner"
GH_RUNNER_LABELS="self-hosted,$GH_RUNNER_ARCH,$GH_RUNNER_OS,$GH_RUNNER_EXTRA_LABELS"
GH_RUNNER_NAME="${USER}-${GH_RUNNER_OS}"

# get release and version details
GH_RUNNER_API="https://api.github.com/repos/actions/runner/releases/latest"
GH_RUNNER_RELEASE="$(curl -s $GH_RUNNER_API)"
GH_RUNNER_VERSION="$(echo "$GH_RUNNER_RELEASE" | jq -r '.tag_name')"
GH_RUNNER_VERSION="${GH_RUNNER_VERSION:1}"

# download package details
GH_RUNNER_URL="https://github.com/actions/runner/releases"
GH_RUNNER_PACKAGE="${GH_RUNNER}-${GH_RUNNER_OS}-$GH_RUNNER_ARCH-${GH_RUNNER_VERSION}.tar.gz"
GH_RUNNER_DOWNLOAD="$GH_RUNNER_URL/download/v${GH_RUNNER_VERSION}/${GH_RUNNER_PACKAGE}"

# discover the sha from the release notes
GH_RUNNER_RELEASE_BODY="$(echo "$GH_RUNNER_RELEASE" | jq -r '.body')"
GH_RUNNER_SHA="$(echo "$GH_RUNNER_RELEASE_BODY" | grep "\- $GH_RUNNER_PACKAGE <")"
GH_RUNNER_SHA="${GH_RUNNER_SHA#*-->}"
GH_RUNNER_SHA="${GH_RUNNER_SHA%<\!--*}"

# if the directory already exists, remove it, then create and enter it
echo "Preparing working directory in $GH_RUNNER"
rm -rf "$GH_RUNNER"
mkdir -p "$GH_RUNNER"
cd "$GH_RUNNER" || exit

# Download, verify, and extract the runner
echo "Installing runner"
curl -o "$GH_RUNNER_PACKAGE" -L "$GH_RUNNER_DOWNLOAD"
echo "$GH_RUNNER_SHA  $GH_RUNNER_PACKAGE" | shasum -a 256 -c
tar xzf "./$GH_RUNNER_PACKAGE"

# register the runner
./config.sh \
  --url https://github.com/duplocloud/duploctl \
  --token "$GH_RUNNER_TOKEN" \
  --labels $GH_RUNNER_LABELS \
  --name "$GH_RUNNER_NAME" \
  --runnergroup "default" \
  --unattended

cat <<EOF
Runner Confguration:
  name: $GH_RUNNER_NAME
  labels: $GH_RUNNER_LABELS
  version: $GH_RUNNER_VERSION
EOF

# cleanup
rm -f "$GH_RUNNER_PACKAGE"
