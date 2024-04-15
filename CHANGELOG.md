# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.25] - 2024-04-15

### Added

 - all actions use the duploctl[bot] app for commits

## [0.2.23] - 2024-04-14

### Fixed

 - jit timout is now 1 hr vs 6
 - pipeline commits using duploctl[bot] app instead of default token
 - full changelog bump and push working now with the duploctl[bot]

## [0.2.18] - 2024-04-11

### Added

 - A version bump script which includes changelog notes in GHA releases
 - shared setup action in piplines

### Fixed

 - azure services had an issue with the `--wait`
 - homebrew installation needs the `jsonpointer` library explicit in pyproject
 - broken pipeline for docker from updated action
 - simplifed the cleanup script for integration tests

## [0.2.16] - 2024-04-10

### Added 

 - Actual JIT expiration dates sent to kubectl and aws cli
 - CRUD for services and rds
 - jsonpatch args for updating services
 - `--wait` enabled on all updates to a service including `update_image`
 - better logging for wait operations
 - introduced v2 and v3 base resource classes
 - pod resource with get, list, and show logs
 - ingress resource with all crud operations
 - create and watch jobs with logs returned
 - rds resource with all crud operations and individual actions present in the ui
 - fully working integration tests with proper waiting
 - creating a host without an image will pick a sane default
 - display available host AMIs for a tenant

## [v0.2.15] - 2024-03-22

### Added

 - `--admin` flag for jit commands
 - tenant level jit commands

### Changed

 - jit commands are no longer admin by default, tenant level is now default
