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

Get the current version:

```sh
python -m setuptools_scm
```

When building the artifact the setuptools scm tool will use the a snazzy semver logic to determine version.

_ref:_ [SetupTools SCM](https://pypi.org/project/setuptools-scm/)

When Ready to publish a new version live, go to the [publish.yml](https://github.com/duplocloud/duploctl/actions/workflows/publish.yml) workflow and run the workflow manually. This will bump the version, build the artifact, and push the new version to pypi. 

## Docker Image  

The docker image uses a couple of stages to do a few different tasks. Mainly the official image is the runner target. The bin target is for generating multiarch binaries. 

Build the main image locally for your machine.
```sh
docker compose build duploctl
```

Use buildx to build the multiarch binaries. This will output the binaries to the `dist` folder.
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

## Changelog  

Make sure to take note of your changes in the changelog. This is done by updating the `CHANGELOG.md` file. Add any new details under the `## [Unreleased]` section. When a new version is published, the word `Unreleased` will be replaced with the version number and the date. The section will also be the detailed release notes under releases in Github. The checks on the PR will fail if you don't add any notes in the changelog.

## Documentation 

The wiki is a static generated website using mkdocs. All of the resource docs are pulled out from the pydoc strings in the code. The convention for docs in code is [Google style docstrings](https://google.github.io/styleguide/pyguide.html).

Here is an example of the docstring format. 

```python
def my_function(param1, param2) -> dict:
    """This is a function that does something.

    Usage: CLI Usage
      ```sh
      duploctl ...
      ```

    Args:
      param1: The first parameter.
      param2: The second parameter.

    Returns:
      message: The return value.

    Raises:
        DuploError: If the value is not correct.
    """
    return {}
```

To work on the wiki you need to install the dependencies. You probably already did this if you ran the editable install command above, this includes the optional doc dependencies. 

```sh
pip install --editable '.[docs]'
```

To serve the wiki locally you can run the following command. This will start a local server and watch for changes.

```sh
mkdocs serve
```

## Step Through Debugging  

Assuming you are using VSCode, make sure you have a `.vscode/launch.json` file with the following configuration. Change the `args` to the command you want to debug, this is equivelent to running from the command line. 

```json
{
    "version": "0.2.0",
    "configurations": [
        {
          "name": "duploctl",
          "type": "debugpy",
          "console": "integratedTerminal",
          "request": "launch",
          "justMyCode": true,
          "cwd": "${workspaceFolder}",
          "program": "src/duplocloud/cli.py",
          "args": [
            "version",
            "--interactive", 
            "--wait",
            "--admin"
          ],
          "env": {
            "DUPLO_HOST": "https://myportal.duplocloud.net",
            "DUPLO_TENANT": "toolstest",
            "DUPLO_CONFIG": "${workspaceFolder}/config/duploconfig.yaml"
          }
        }
    ]
}
```

## Self Hosted Mac Arm64 Runner  

Due to limitations of GHA, there are no darwin/Arm64 machines to compile the installer for. This means you must install the self hosted runner on your own machine. 

First Get a token from here: [GHA New Runner Page](https://github.com/duplocloud/duploctl/settings/actions/runners/new). 
Set this variable in your `.envrc` file. 

```sh
export GH_RUNNER_TOKEN="your-token-here"
```

Next you need to run the following command to make a dir and chown it so the setup-python step is happy. 
[See issue here](https://github.com/actions/setup-python/blob/2f078955e4d0f34cc7a8b0108b2eb7bbe154438e/docs/advanced-usage.md#macos)  

```sh
sudo mkdir -p /Users/runner /Users/runner/hostedtoolcache
sudo chown -R "$(id -un)" /Users/runner
```

Then run the following command to install the runner and activate it. 

```sh 
./scripts/runner_install.sh
```
