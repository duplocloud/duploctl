#!/usr/bin/env bash

# make sure the first parameter is either patch, minor, or major
if [ "$1" != "patch" ] && [ "$1" != "minor" ] && [ "$1" != "major" ]; then
  echo "Usage: bump.sh [patch|minor|major]"
  exit 1
fi

# make sure the second parameter is a true or false value
if [ "$2" != "true" ] && [ "$2" != "false" ]; then
  echo "Usage: bump.sh [patch|minor|major] [true|false]"
  exit 1
fi

echo "Doing a $1 and pushing is $2"

unset GITHUB_TOKEN
gh auth status || gh auth login --hostname github.com --git-protocol ssh --web --skip-ssh-key

gh workflow run publish.yml \
    --ref main \
    -f "action=$1" \
    -f "push=$2" \
    -f "include_mac_arm64=true"

# while the JOB_ID is empty keep trying to get it every three seconds, but only try 7 times
while [ -z "$JOB_ID" ]; do
  ((count++)) && ((count == 10)) && break
  JOB_ID="$(gh run list --workflow publish.yml --status in_progress --json databaseId --jq '.[0].databaseId')"
  sleep 3
  echo "Waiting for the job to start...$count $JOB_ID"
done

echo "Found Job(${JOB_ID})"

gh run watch "$JOB_ID"

echo "Job($JOB_ID) finished"

gh run view "$JOB_ID"
