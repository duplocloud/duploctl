# Contributing  

Follow these steps to be proper. 

## Version Bump  

Make sure you have the duplo git-bump installed and then run

```sh
git bump -v '[patch, major, minor]'
```
e.g. a small patch do this:
```sh
git bump -v patch
```

Doing this creates a proper semver which will trigger a new publish pipeline. 

## Build  

Build the package which creates the artifact in the dist folder. 
```
python -m build
```

## Semver with Setuptools SCM command  

Get the current version
```
python -m setuptools_scm
```

When building the artifact the setuptools scm tool will use the a snazzy semver logic to determine version. 

*ref:* [SetupTools SCM](https://pypi.org/project/setuptools-scm/)

## Add Wiki Doc For Subcommand

make sure to add a wiki document to the wiki folder for the subcommand. Follow the same pattern as the other subcommand readme's.