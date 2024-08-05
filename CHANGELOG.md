# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.32] - 2024-08-05

### Added 

 - remove_user_from_tenant command
 - Added support for tenant start/stop

### Updates 
 - changed handling of tenant arg in user resource
 - add reference yaml for users
 - changed client error handling to display docstrings on bad input


## [0.2.31] - 2024-07-29

### Added 

 - cloudfront resource with crud operations
 - a new plan resource to view
 - print token command when you just want the token

### Updates 
 - updated all of the resources to show up in the docs
 - arm64 linux binary is now available in the homebrew formula
 - auto generate markdown templates for resources when building the docs
 - updated docs for services.update_env to include usage

## [0.2.30] - 2024-07-11

### Added 

 - New aws plugin which can
   - generate boto3 clients using JIT
   - `update_website` command to push new code to an S3 bucket and invalidate the cloudfront cache
 - Tenant resource has a new `region` command to get just the current region for the tenant.
 - generating an aws profile without a name will default to "duplo"
 - publish linux/arm64 standalone binary

## [0.2.29] - 2024-06-07

### Added 

 - publish docs on main branch push

### Fixed 

 - Better error handling for the version command. It failed when the server didn't have the version endpoint.

## [0.2.28] - 2024-06-04
### Added 

 - Support for Storage Class
 - Support for PVC
 - Added support for create and delete user
 - start, stop, restart for hosts with `--wait`
 - Allow code to programmatically return the config from `update_kubeconfig` when save is false.
 - more docs for the wiki
 - A new check to make sure CHANGELOG.md is updated before merging a PR. 
 - version command now shows server version

### Fixed

  - Kubernetes commands with JIT were not getting the CA when using GCP. 

## [0.2.27] - 2024-04-22

### Fixed 

 - homebrew deployment uses pip freeze for it's dependencies so all subpackages exist as well

## [0.2.26] - 2024-04-17

### Added 

 - Support for `DUPLO_TENANT_ID` or `--tenant-id` as a global argument alternative to using the tenant name
 - `WARN` is default log level and `--wait` will show more logs when set to `DEBUG`
 - Support for AWS S3
 - Github Pages Site for documentation using mkdocs

### Fixed 

 - `--wait` flag for azures updates

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
