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
pip install --editable .[build,test]
```

If you are using zsh Run following to install dependencies:

```sh
pip3 install -e '.[build,test]'
```

## Building Artifacts  

Build the package which creates the artifact in the build folder.  
```sh
python -m build
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
