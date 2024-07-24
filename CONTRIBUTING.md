# Contributing

Follow these steps to be proper.

## Direnv Setup  

Here is a good start for a decent `.envrc` file.  

```sh
source_up .envrc
layout python3
PATH_add ./scripts

export KUBECONFIG=config/kubeconfig.yaml
export AWS_CONFIG_FILE=config/aws
export DUPLO_HOME="config"
export DUPLO_CONFIG="config/duploconfig.yaml"
export DUPLO_CACHE="config/cache"
```

## Dependencies  

Install dependencies in editable mode so you can use step through debugging. 

```sh
pip install --editable '.[build,test,aws,docs]'
```

## Building Artifacts  

Build the package which creates the artifact in the build folder.  
```sh
python -m build
```

Building a plugin.
```sh
python -m build plugins/aws/ -o=dist
```

Create a single binary build for the cli using pyinstaller.  
```sh
./scripts/installer.spec
```

Build the Homebrew formula from a tagged release. Normally only the pipeline will run this script which does properly choose the right git tag before running. This ensures the pip dependencies are correct when building the formula.  
```sh
./scripts/formula.py v0.2.15
```

## Version Bump

Make sure you have the duplo git-bump installed and then run

```sh
git bump -v '[patch, major, minor]'
```

e.g. a small patch do this:

```sh
git bump -v patch
```

Doing this creates a proper semver which will trigger a new publish pipeline which in the background uses setuptools_scm to determine the version.

Get the current version:

```sh
python -m setuptools_scm
```

When building the artifact the setuptools scm tool will use the a snazzy semver logic to determine version.

_ref:_ [SetupTools SCM](https://pypi.org/project/setuptools-scm/)

## Add Wiki Doc For Subcommand

make sure to add a wiki document to the wiki folder for the subcommand. Follow the same pattern as the other subcommand readme's.

## Docker Image  

The docker image uses a couple of stages to do a few different tasks. Mainly the official image is the runner target. The bin target is for generating multiarch binaries. 

Build the main image locally for your machine.
```sh
docker compose build duploctl
```

Use buildx to build the multiarch binaries.
```sh
docker buildx bake duploctl-bin
```

## Building the Homebrew Formula  

The homebrew formula is built from the `scripts/formula.py` script. This script will use the current git tag to build the formula. 

First you need to get the frozen requirements for the formula. This is done by running the following command. This will do all local dependencies including dev only dependencies. The pipeline will make sure to only include the necessary dependencies.
```sh
pip freeze --exclude-editable > requirements.txt
```
Then generate the formula using the current git tag. 
```sh
./scripts/formula.py
```
