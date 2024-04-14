#!/usr/bin/env bash

base_tree="$(git rev-parse --verify HEAD)"

gh_token="$1"
repo="duplocloud/duploctl"
ghapi="https://api.github.com/repos/$repo/git"

tree="$(curl \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token $gh_token" \
  -H "Accept: application/vnd.github.v3+json" \
  "$ghapi/trees" \
  -d'{"base_tree": "'$base_tree'","tree":[{"path": "CHANGELOG.md","mode": "100644","type": "blob","content": "hello world"}]}')"

tree_sha="$(echo $tree | jq -r '.sha')"

commit="$(curl \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token $gh_token" \
  "$ghapi/commits" \
  -d '{"message": "Test GitHub Commit Message", "parents": ["'$base_tree'"], "tree":"'$tree_sha'"}')"

commit_sha="$(echo $commit | jq -r '.sha')"

curl \
  --no-progress-meter \
  -X PATCH \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token $gh_token" \
  "$ghapi/refs/heads/main" \
  -d '{"sha": "'$commit_sha'"}'
