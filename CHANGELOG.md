# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2025-07-15

### Added 

- batch_scheduling_policy resource
- batch_compute resource 
- batch_queue resource
- batch_definition resource with update_image command
- batch_job resource

## [0.2.52] - 2025-07-03

### Added

- Added enhancement to ecs update_image to also update the specific container image.

### Fixed

- The aws_secrets resource was inconsistent with how other similar resources work. This is a breaking change that changes how you interact with aws secrets. [Please read more about how to properly use this resource in the wiki](https://cli.duplocloud.com/AwsSecret/). The create and update methods both changed and follow the same style of usage.

- ECS tasks failed when cpu/memory are not present in the task definition, which is allowed for EC2-hosted services.

## [0.2.51] - 2025-05-29

### Fixed

- Issue with wait breaking when job create.

## [0.2.50] - 2025-05-08

### Added

- Added DuploStillWaiting class to reflect scenarios where a command waits too long for a resource operation to complete.
- Added integration tests for k8 Secret resource.
- Added wait flag as an argument to DuploClient.

### Fixed

- Docs enhancements were added for the Host resource with integration tests.
- Added fields to the ecs service update task def to replace a bug
- Patching support and docs enhancements were added for an ASG resource.
- Patching support and docs enhancements were added for an Ingress resource.

## [0.2.49] - 2025-04-21

## [0.2.48] - 2025-04-21

### Fixed

- Patching support and docs enhancements were added for the ConfigMap resource.
- Patching support and docs enhancements were added for the K8S Secret resource.
- bulk_update_image to handle serviceimage input as a list of [name, image] pairs instead of a dict.
- Patching support and docs enhancements were added for the K8S Secret resource.

## [0.2.47] - 2025-04-07

### Fixed

- Patch config file into test_at_least_host so it doesn't depend on a specific local setup.
- Added a generic exception block to handle any unexpected errors that are not instances of DuploError.
- Existing ingress commands (create, update) with missing integration tests.

### Added

- Support init containers in the update_image subcommand for services.
- Added integration tests for missing tenant methods: list_users, billing, region, and dns_config.
- Added unit tests for missing service methods: create, delete, start, restart and stop.
- ECS run task for a task definition. `duploctl ecs run_task myapp`
- ECS update image will now update just a task definition and a corresponding service if there is one.
- A generic method for making sure a name is prefixed. This means you can give a short or long name and the cli will use either.
- Added integration tests for missing ASG methods: list, find, create, update, delete and scale.
- Added integration tests for AWS Secret methods: find, create, update and delete.
- Added configmap commands (find, delete, update) with integration tests.
- Added cloudfront commands (find, enable, update, get_status) and fixed existing commands (create, list, disable, delete) with integration tests.

## [0.2.46] - 2025-03-03

### Fixed

 - Fixed issue where AgentPlatform key needed to be copied up to the top level of the service object

## [0.2.45] - 2025-02-25

- Added enhancements to the start/stop service to select all services or specific ones.
- Added enhancement to update_image service to also update the sidecar container image.
- Added support for service rollback with a specific revision.

## [0.2.44] - 2025-01-22

### Added

  - Added support for updating the environment variables of a lambda.
  - Added support for SSM Parameter CRUD operations.
  - Added support for AWS Secrets Manager
  - Added support for configuring a load balancer for a service.
  - start, stop, restart for service with `--wait`

### Fixed

  - Fixed duploctl ecs update_image service bug

## [0.2.41] - 2024-12-06

### Added

- gcp jit command with example cli usage

## [0.2.40] - 2024-11-21

### Fixed

  - Removed potential cyclic dependencies in `docker-compose.yaml` by explicitly defining inherited sections

## [0.2.39] - 2024-11-12

### Fixed

  - Issue with wait breaking when a pod didn't have the `Name` key
  - Jobs were not failing gracefully when waiting for completion but faults were present for pods on the job

## [0.2.38] - 2024-10-28

### Added

  - much better local installer for gha actions
  - Update Kubeconfig now has a name argument to name the user/context anything you want.
  - Update Kubeconfig will always name the server after the Plan. This will share the same server for all tenants in the same plan. Also prevents unnecessary duplicates of the same server.
  - Update kubeconfig will update the sections instead of skipping if they already exist. For example you can switch to interactive mode.
  - Added more duplo component versions to the version command.

### Fixed

  - fixed the duplicating user section in the update kubeconfig command.
  - fixed the wait on bulk update image.

## [0.2.37] - 2024-10-18

### Fixed

  - Fixed handling of case in name/value keys in environment variables as backend permits both.
  - Fixes issue in service update argument where strategy required three dashes.
  - Gracefully handles situations where user attempts to merge with a service that has no existing env vars.
  - Fixed issue where the wait flag would cause an error when updating an image and the images were the same.
  - Fixed issue when updating an image and the image was the same, it would not report the last deployed by when and who

## [0.2.36] - 2024-09-25

### Fixed

- Fixed CronJob Update by adding missing logic to set `isAnyHostAllowed`. This is due to a the object returned from the `GET` request being slightly different to the object expected in the `PUT/POST` request.

## [0.2.35] - 2024-09-20

### Added

- Include generated Github release notes in the release description
- Install instructions in the docs
- Cleaned up pipeline and added test reporting into the PRs
- Configmaps and secrets can be created with data values `--from-file` and `--from-literal`. The result can be displayed with `--dry-run`. Both are a key=value pair but files can simply default the key to the filename.

### Fixed

- Fixed update_pod_label subcommand functionality for service.
- fixed many little issues with the docs like misspelled args, unneeded extra ones, and even missing types
- discovered why Args were not renaming based on the function arg.
- Case insensitive tenant name comparison.
- Fixed issue where a services otherDockerConfig was cleared on updates.
- Fixed issue where ecs update image was removing secrets,commands and env variables

## [0.2.33] - 2024-08-12

### Added

- Added an apply method on base classes. Now most resources can simply `apply` files.
- added tenant DNS config command to retrieve configuration
- added functionality to search for users by tenant
- moved command to add/remove users from tenant from user to tenant
- Added new function in service for updating pod label config.

### Updates

- performance improvements to load cli args only when needed
- The `command` method on all `DuploResources` returns a factory function with a parser already scoped into the functions argument annotations.
- Custom display in the docs for CLI Arguments
- Added docs for internals of the CLI for anyone wanting to contribute or extend.
- Comply with Github best practices, ie added Security, Code of conduct, License, issue/pr templates, etc. [Community Standards](https://github.com/duplocloud/duploctl/community)

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
