# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
